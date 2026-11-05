import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from comanda import criar_app, db as banco
from comanda.migracoes import inicializar_banco, resetar_banco
from comanda.modelo import ajustar_modelo, ajustar_modelo_manual, obter_resumo_modelo
from comanda.recomendacao import agrupar, cosseno, obter_clusters, recomendar


class ProjetoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = patch.object(banco, 'CAMINHO_BANCO', Path(self.tmp.name) / 'teste.db')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.app = criar_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def alterar(self, pedido, prato, incluido):
        return self.client.put(f'/api/pedidos/{pedido}/itens/{prato}', json={'incluido': incluido})

    def test_base_e_rotas(self):
        self.assertEqual(len(self.client.get('/api/pedidos').json), 100)
        cardapio = self.client.get('/api/pratos?pedido_id=1').json
        self.assertEqual(len(cardapio), 60)
        self.assertEqual(len({p['categoria_id'] for p in cardapio}), 10)
        self.assertIsInstance(cardapio[0]['incluido'], bool)
        self.assertEqual(self.client.get('/').status_code, 200)
        with self.client.get('/static/novo_pedido.js') as resposta:
            self.assertEqual(resposta.status_code, 200)
        grupos = self.client.get('/api/clusters').json
        self.assertEqual(len(grupos['grupos']), 3)
        self.assertEqual(sum(len(g['categorias']) for g in grupos['grupos']), 10)
        for c in grupos['categorias']:
            self.assertEqual(len(c['proximos']), 9)
            self.assertEqual(c['proximos'], sorted(c['proximos'], key=lambda x: (x['distancia'], x['id'])))

    def test_ranking_categorias_e_estado_vazio(self):
        with banco.conectar() as db:
            db.execute('DELETE FROM itens_pedido')
        resposta = self.client.get('/categorias')
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('Ainda não há pratos', resposta.get_data(as_text=True))
        with banco.conectar() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM pratos ORDER BY categoria_id,id')]
            db.executemany('INSERT INTO itens_pedido VALUES (?,?)', [(1, ids[0]), (2, ids[0]), (1, ids[-1])])
        from flask import template_rendered
        contextos = []
        def capturar(sender, template, context, **extra):
            contextos.append(context)
        with template_rendered.connected_to(capturar, self.app):
            resposta = self.client.get('/categorias')
        self.assertEqual(resposta.status_code, 200)
        contexto = contextos[0]
        self.assertEqual(contexto['total'], 3)
        self.assertEqual([c['quantidade'] for c in contexto['categorias']], [2, 1] + [0] * 8)
        self.assertAlmostEqual(contexto['categorias'][0]['percentual'], 200 / 3)
        self.assertEqual(contexto['categorias'][1]['largura'], 50)
        self.alterar(2, ids[0], False)
        self.assertIn('2 itens', self.client.get('/categorias').get_data(as_text=True))

    def test_persistencia_idempotencia_e_isolamento(self):
        antes_outro = self.client.get('/api/pratos?pedido_id=2').json
        cardapio = self.client.get('/api/pratos?pedido_id=1').json
        incluido = next(p['id'] for p in cardapio if p['incluido'])
        novo = next(p['id'] for p in cardapio if not p['incluido'])
        modelo = obter_resumo_modelo()
        for _ in range(2):
            self.assertEqual(self.alterar(1, incluido, False).status_code, 200)
            self.assertEqual(self.alterar(1, novo, True).status_code, 200)
        inicializar_banco()
        novo_client = self.app.test_client()
        depois = {p['id']: p['incluido'] for p in novo_client.get('/api/pratos?pedido_id=1').json}
        self.assertFalse(depois[incluido])
        self.assertTrue(depois[novo])
        self.assertEqual(antes_outro, novo_client.get('/api/pratos?pedido_id=2').json)
        self.assertEqual(modelo, obter_resumo_modelo())

    def test_sugestoes_excluem_itens_e_sao_deterministicas(self):
        incluidos = {p['id'] for p in self.client.get('/api/pratos?pedido_id=1').json if p['incluido']}
        r = recomendar(1)
        self.assertEqual(r, recomendar(1))
        self.assertEqual(len(r['sugestoes']), 10)
        self.assertFalse(incluidos.intersection(p['id'] for p in r['sugestoes']))
        self.assertLessEqual(len(r['pedidos_semelhantes']), 5)
        self.assertNotIn(1, [p['id'] for p in r['pedidos_semelhantes']])
        for p in r['sugestoes']:
            self.assertAlmostEqual(p['pontuacao'], (p['afinidade_categoria'] + p['pontuacao_colaborativa']) / 2)
        primeiro = r['sugestoes'][0]['id']
        self.alterar(1, primeiro, True)
        self.assertNotIn(primeiro, [p['id'] for p in recomendar(1)['sugestoes']])

    def test_pedido_vazio_e_cardapio_completo(self):
        with banco.conectar() as db:
            db.execute('DELETE FROM itens_pedido WHERE pedido_id=20')
            populares = [r[0] for r in db.execute('''SELECT p.id FROM pratos p
                LEFT JOIN itens_pedido i ON p.id=i.prato_id GROUP BY p.id
                ORDER BY COUNT(i.pedido_id) DESC,p.id LIMIT 10''')]
        r = recomendar(20)
        self.assertTrue(r['pedido_vazio'])
        self.assertEqual(r['pedidos_semelhantes'], [])
        self.assertEqual(populares, [p['id'] for p in r['sugestoes']])
        with banco.conectar() as db:
            db.execute('INSERT INTO itens_pedido SELECT 20,id FROM pratos')
        self.assertEqual(recomendar(20)['sugestoes'], [])

    def test_sem_vizinhos_e_categoria_sem_pedidos(self):
        with banco.conectar() as db:
            db.execute('DELETE FROM itens_pedido')
            db.execute('INSERT INTO itens_pedido VALUES (1,1)')
        r = recomendar(1)
        self.assertEqual(r['pedidos_semelhantes'], [])
        self.assertEqual(r['sugestoes'][0]['id'], 2)
        for p in r['sugestoes']:
            self.assertAlmostEqual(p['pontuacao'], p['afinidade_categoria'])
        grupos = obter_clusters()
        sem_pedidos = next(c for c in grupos['categorias'] if c['id'] == 2)
        self.assertTrue(all(c['distancia'] == 1 for c in sem_pedidos['proximos']))

    def test_colaboracao_com_resultado_conhecido(self):
        with banco.conectar() as db:
            db.execute('DELETE FROM itens_pedido')
            db.executemany('INSERT INTO itens_pedido VALUES (?,?)', [(1, 1), (2, 1), (2, 3), (3, 1), (3, 3)])
        r = recomendar(1)
        self.assertEqual(r['sugestoes'][0]['id'], 3)
        self.assertAlmostEqual(r['sugestoes'][0]['pontuacao_colaborativa'], 1)
        self.assertIn('#2 Bruno Almeida', ' '.join(r['sugestoes'][0]['motivos']))

    def test_validacao_api(self):
        for url, status in [('/api/pratos', 400), ('/api/pratos?pedido_id=x', 400),
                            ('/api/pratos?pedido_id=999', 404), ('/api/pedidos/999/sugestoes', 404)]:
            self.assertEqual(self.client.get(url).status_code, status)
        for dados in [{}, [], {'incluido': 1}, {'incluido': 'true'}, None]:
            self.assertEqual(self.client.put('/api/pedidos/1/itens/1', json=dados).status_code, 400)
        self.assertEqual(self.alterar(999, 1, True).status_code, 404)
        self.assertEqual(self.alterar(1, 999, True).status_code, 404)
        valido = {'pratos': [1, 8], 'pedidos_na_fila': 3}
        self.assertEqual(self.client.post('/api/prever', json=valido).status_code, 200)
        self.assertEqual(self.client.post('/api/prever', json={**valido, 'pedidos_na_fila': '3'}).status_code, 200)
        for chave, valor in [('pratos', []), ('pratos', [1, 1]), ('pratos', [999]), ('pratos', [True]),
                             ('pratos', [1.5]), ('pratos', 'x'), ('pratos', None),
                             ('pedidos_na_fila', -1), ('pedidos_na_fila', 51), ('pedidos_na_fila', 1.5),
                             ('pedidos_na_fila', True), ('pedidos_na_fila', float('nan')), ('pedidos_na_fila', None)]:
            with self.subTest(chave=chave, valor=valor):
                self.assertEqual(self.client.post('/api/prever', json={**valido, chave: valor}).status_code, 400)
        for dados in [[], {}, None]:
            self.assertEqual(self.client.post('/api/prever', json=dados).status_code, 400)

    def test_previsao_aplica_os_coeficientes(self):
        r = self.client.post('/api/prever', json={'pratos': [1, 2, 25], 'pedidos_na_fila': 4}).json
        with banco.conectar() as db:
            tempos = [t for (t,) in db.execute('SELECT tempo_prato_min FROM pratos WHERE id IN (1, 2, 25)')]
        self.assertEqual(r['entrada'], {'tempo_maior_prato': max(tempos), 'tempo_demais_pratos': sum(tempos) - max(tempos),
                                        'pedidos_na_fila': 4, 'quantidade_categorias': 2})
        self.assertEqual(r['tempo_base_itens'], sum(tempos))
        self.assertEqual(r['quantidade_itens'], 3)
        modelo = obter_resumo_modelo()
        esperado = modelo['intercepto'] + sum(modelo['coeficientes'][v] * n for v, n in r['entrada'].items())
        self.assertAlmostEqual(r['multipla']['previsao_bruta'], esperado)
        self.assertAlmostEqual(r['multipla']['previsao_minutos'], max(0, esperado))
        self.assertAlmostEqual(r['multipla']['previsao_bruta'], r['multipla']['previsao_numpy'])
        self.assertLess(r['multipla']['diferenca_numpy'], 1e-9)
        self.assertNotIn('simples', r)
        self.assertEqual(r['avisos'], [])

    def test_reset_completo_volta_aos_csvs(self):
        original = obter_resumo_modelo()
        self.client.put('/api/coeficientes', json={'intercepto': 1, 'tempo_maior_prato': 1, 'tempo_demais_pratos': 1,
                                                   'pedidos_na_fila': 1, 'quantidade_categorias': 1})
        self.client.post('/api/acompanhados', json={'pratos': [1], 'pedidos_na_fila': 1})
        self.alterar(1, 60, True)
        contagens = resetar_banco()
        self.assertEqual(contagens, {'pedidos': 100, 'pratos': 60, 'categorias': 10, 'itens_pedido': len(banco.ler_csv('itens_pedido.csv')),
                                     'coeficientes_personalizados': 0, 'pedidos_acompanhados': 0})
        self.assertFalse(next(p for p in self.client.get('/api/pratos?pedido_id=1').json if p['id'] == 60)['incluido'])
        self.assertEqual(obter_resumo_modelo(), original)
        with banco.conectar() as db:
            self.assertEqual([r[0] for r in db.execute('SELECT versao FROM migracoes ORDER BY 1')], [1, 2, 3])

    def test_migracao_2_atualiza_banco_antigo(self):
        caminho = Path(self.tmp.name) / 'antigo.db'
        with sqlite3.connect(caminho) as db:
            db.executescript('''
                CREATE TABLE pedidos (id INTEGER PRIMARY KEY, cliente TEXT NOT NULL,
                    pedidos_na_fila INTEGER NOT NULL, tempo_preparo_min REAL NOT NULL);
                CREATE TABLE categorias (id INTEGER PRIMARY KEY, nome TEXT NOT NULL);
                CREATE TABLE pratos (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, categoria_id INTEGER NOT NULL);
                CREATE TABLE itens_pedido (pedido_id INTEGER, prato_id INTEGER, PRIMARY KEY (pedido_id, prato_id));
                CREATE TABLE itens_originais (pedido_id INTEGER, prato_id INTEGER, PRIMARY KEY (pedido_id, prato_id));
                CREATE TABLE migracoes (versao INTEGER PRIMARY KEY);
                INSERT INTO migracoes VALUES (1);''')
            db.executemany('INSERT INTO pedidos VALUES (?,?,?,?)', [(int(r['pedido_id']), r['cliente'],
                int(r['pedidos_na_fila']), 0.0) for r in banco.ler_csv('pedidos.csv')])
            db.executemany('INSERT INTO categorias VALUES (?,?)', [(int(r['categoria_id']), r['nome']) for r in banco.ler_csv('categorias.csv')])
            db.executemany('INSERT INTO pratos VALUES (?,?,?)', [(int(r['prato_id']), r['nome'], int(r['categoria_id'])) for r in banco.ler_csv('pratos.csv')])
            itens = [(int(r['pedido_id']), int(r['prato_id'])) for r in banco.ler_csv('itens_pedido.csv')]
            db.executemany('INSERT INTO itens_originais VALUES (?,?)', itens)
            # Item editado pela interface: precisa sobreviver à migração.
            db.executemany('INSERT INTO itens_pedido VALUES (?,?)', itens[1:] + [(1, 60)])
        db.close()
        with patch.object(banco, 'CAMINHO_BANCO', caminho):
            inicializar_banco()
            inicializar_banco()
            with banco.conectar() as db:
                self.assertEqual(db.execute('SELECT tempo_prato_min FROM pratos WHERE id=1').fetchone()[0], 7)
                self.assertNotIn(0, [r[0] for r in db.execute('SELECT tempo_prato_min FROM pratos')])
                tempos = {int(r['pedido_id']): float(r['tempo_preparo_min']) for r in banco.ler_csv('pedidos.csv')}
                self.assertEqual(dict(db.execute('SELECT id, tempo_preparo_min FROM pedidos')), tempos)
                self.assertEqual({tuple(r) for r in db.execute('SELECT * FROM itens_pedido')}, set(itens[1:]) | {(1, 60)})
                self.assertEqual([r[0] for r in db.execute('SELECT versao FROM migracoes ORDER BY 1')], [1, 2, 3])

    def test_modelo_indisponivel_e_extrapolacao(self):
        r = self.client.post('/api/prever', json={'pratos': list(range(1, 61)), 'pedidos_na_fila': 50})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json['avisos'])
        with banco.conectar() as db:
            db.execute('DELETE FROM itens_originais')
        self.assertFalse(self.client.get('/api/modelo').json['disponivel'])
        self.assertEqual(self.client.post('/api/prever', json={'pratos': [1], 'pedidos_na_fila': 4}).status_code, 422)


class MatematicaTest(unittest.TestCase):
    def test_cosseno_e_clusters_conhecidos(self):
        vetores = [[1, 0, 0], [2, 0, 0], [0, 1, 0], [0, 2, 0], [0, 0, 1], [0, 0, 2]]
        sim = cosseno(vetores)
        self.assertAlmostEqual(sim[0, 1], 1)
        self.assertAlmostEqual(sim[0, 2], 0)
        self.assertEqual(agrupar(1 - sim, [1, 2, 3, 4, 5, 6]), [[1, 2], [3, 4], [5, 6]])
        self.assertTrue(np.isfinite(cosseno([[0, 0], [1, 0]])).all())

    def test_ligacao_media(self):
        d = np.array([[0, .1, .2, .9], [.1, 0, .8, .9], [.2, .8, 0, .4], [.9, .9, .4, 0]])
        self.assertEqual(agrupar(d, [1, 2, 3, 4], 2), [[1, 2], [3, 4]])

    def test_regressao_conhecida(self):
        x = np.array([[1, 0, 0], [2, 1, 0], [3, 0, 1], [4, 2, 3], [2, 3, 1]])
        y = 2 + x @ np.array([3, 4, 5])
        coef, r2 = ajustar_modelo(x, y)
        np.testing.assert_allclose(coef, [2, 3, 4, 5])
        manual, r2_manual = ajustar_modelo_manual(x, y)
        np.testing.assert_allclose(manual, [2, 3, 4, 5])
        self.assertAlmostEqual(r2_manual, 1)
        self.assertAlmostEqual(r2, 1)
        self.assertIsNone(ajustar_modelo(x, np.ones(5))[1])
        with self.assertRaises(ValueError):
            ajustar_modelo([[1, 1, 1]] * 5, [1] * 5)
        with self.assertRaises(ValueError):
            ajustar_modelo([[1, 2, 3]], [1])


if __name__ == '__main__':
    unittest.main()
