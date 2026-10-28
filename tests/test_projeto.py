import importlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import banco
from recomendacao import agrupar, cosseno, obter_clusters, recomendar
from regressao import ajustar_modelo, obter_resumo_modelo


class ProjetoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patch = patch.object(banco, 'CAMINHO_BANCO', Path(self.tmp.name) / 'teste.db')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.app = importlib.import_module('app').criar_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def marcar(self, uid, cid, visto):
        return self.client.put(f'/api/usuarios/{uid}/vistos/{cid}', json={'visto': visto})

    def test_base_e_rotas(self):
        self.assertEqual(len(self.client.get('/api/usuarios').json), 100)
        catalogo = self.client.get('/api/conteudos?usuario_id=1').json
        self.assertEqual(len(catalogo), 60)
        self.assertEqual(len({c['genero_id'] for c in catalogo}), 10)
        self.assertIsInstance(catalogo[0]['visto'], bool)
        self.assertEqual(self.client.get('/').status_code, 200)
        with self.client.get('/static/script.js') as resposta:
            self.assertEqual(resposta.status_code, 200)
        grupos = self.client.get('/api/clusters').json
        self.assertEqual(len(grupos['grupos']), 3)
        self.assertEqual(sum(len(g['generos']) for g in grupos['grupos']), 10)
        for g in grupos['generos']:
            self.assertEqual(len(g['proximos']), 9)
            self.assertEqual(g['proximos'], sorted(g['proximos'], key=lambda x:(x['distancia'], x['id'])))

    def test_persistencia_idempotencia_e_isolamento(self):
        antes_outro = self.client.get('/api/conteudos?usuario_id=2').json
        catalogo = self.client.get('/api/conteudos?usuario_id=1').json
        visto = next(c['id'] for c in catalogo if c['visto'])
        novo = next(c['id'] for c in catalogo if not c['visto'])
        modelo = obter_resumo_modelo()
        for _ in range(2):
            self.assertEqual(self.marcar(1, visto, False).status_code, 200)
            self.assertEqual(self.marcar(1, novo, True).status_code, 200)
        banco.inicializar_banco()
        novo_client = self.app.test_client()
        depois = {c['id']:c['visto'] for c in novo_client.get('/api/conteudos?usuario_id=1').json}
        self.assertFalse(depois[visto])
        self.assertTrue(depois[novo])
        self.assertEqual(antes_outro, novo_client.get('/api/conteudos?usuario_id=2').json)
        self.assertEqual(modelo, obter_resumo_modelo())

    def test_recomendacoes_excluem_vistos_e_sao_deterministicas(self):
        vistos = {c['id'] for c in self.client.get('/api/conteudos?usuario_id=1').json if c['visto']}
        r = recomendar(1)
        self.assertEqual(r, recomendar(1))
        self.assertEqual(len(r['recomendacoes']), 10)
        self.assertFalse(vistos.intersection(c['id'] for c in r['recomendacoes']))
        self.assertLessEqual(len(r['usuarios_semelhantes']), 5)
        self.assertNotIn(1, [u['id'] for u in r['usuarios_semelhantes']])
        for c in r['recomendacoes']:
            self.assertAlmostEqual(c['pontuacao'], (c['afinidade_genero'] + c['pontuacao_colaborativa']) / 2)
        primeiro = r['recomendacoes'][0]['id']
        self.marcar(1, primeiro, True)
        self.assertNotIn(primeiro, [c['id'] for c in recomendar(1)['recomendacoes']])

    def test_sem_historico_e_tudo_visto(self):
        r = recomendar(20)
        self.assertTrue(r['sem_historico'])
        self.assertEqual(r['usuarios_semelhantes'], [])
        with banco.conectar() as db:
            populares = [r[0] for r in db.execute('''SELECT c.id FROM conteudos c
                LEFT JOIN visualizacoes v ON c.id=v.conteudo_id GROUP BY c.id
                ORDER BY COUNT(v.usuario_id) DESC,c.id LIMIT 10''')]
            db.execute('INSERT INTO visualizacoes SELECT 20,id FROM conteudos')
        self.assertEqual(populares, [c['id'] for c in r['recomendacoes']])
        self.assertEqual(recomendar(20)['recomendacoes'], [])

    def test_sem_vizinhos_e_sem_consumo(self):
        with banco.conectar() as db:
            db.execute('DELETE FROM visualizacoes')
            db.execute('INSERT INTO visualizacoes VALUES (1,1)')
        r = recomendar(1)
        self.assertEqual(r['usuarios_semelhantes'], [])
        self.assertEqual(r['recomendacoes'][0]['id'], 2)
        for c in r['recomendacoes']:
            self.assertAlmostEqual(c['pontuacao'], c['afinidade_genero'])
        grupos = obter_clusters()
        sem_consumo = next(g for g in grupos['generos'] if g['id'] == 2)
        self.assertTrue(all(g['distancia'] == 1 for g in sem_consumo['proximos']))

    def test_colaboracao_com_resultado_conhecido(self):
        with banco.conectar() as db:
            db.execute('DELETE FROM visualizacoes')
            db.executemany('INSERT INTO visualizacoes VALUES (?,?)', [(1,1),(2,1),(2,3),(3,1),(3,3)])
        r = recomendar(1)
        self.assertEqual(r['recomendacoes'][0]['id'], 3)
        self.assertAlmostEqual(r['recomendacoes'][0]['pontuacao_colaborativa'], 1)
        self.assertIn('Bruno Almeida', ' '.join(r['recomendacoes'][0]['motivos']))

    def test_validacao_api(self):
        for url, status in [('/api/conteudos',400),('/api/conteudos?usuario_id=x',400),
                            ('/api/conteudos?usuario_id=999',404),('/api/usuarios/999/recomendacoes',404)]:
            self.assertEqual(self.client.get(url).status_code, status)
        for dados in [{}, [], {'visto':1}, {'visto':'true'}, None]:
            self.assertEqual(self.client.put('/api/usuarios/1/vistos/1', json=dados).status_code,400)
        self.assertEqual(self.marcar(999,1,True).status_code,404)
        self.assertEqual(self.marcar(1,999,True).status_code,404)
        valido = dict(tempo_plataforma=4, quantidade_vistos=10, quantidade_generos=3)
        self.assertEqual(self.client.post('/api/prever',json=valido).status_code,200)
        for chave, valor in [('tempo_plataforma',float('nan')),('tempo_plataforma',float('inf')),
                             ('tempo_plataforma',True),('tempo_plataforma',0),('tempo_plataforma',25),
                             ('quantidade_vistos',1.5),('quantidade_vistos',61),('quantidade_generos',11),
                             ('quantidade_generos',0),('quantidade_generos',-1)]:
            self.assertEqual(self.client.post('/api/prever',json={**valido,chave:valor}).status_code,400)
        for dados in [[], {}, None]:
            self.assertEqual(self.client.post('/api/prever',json=dados).status_code,400)

    def test_modelo_indisponivel_e_extrapolacao(self):
        r = self.client.post('/api/prever', json=dict(tempo_plataforma=24, quantidade_vistos=60, quantidade_generos=10))
        self.assertEqual(r.status_code,200)
        self.assertTrue(r.json['avisos'])
        with banco.conectar() as db:
            db.execute('DELETE FROM historico_inicial')
        self.assertFalse(self.client.get('/api/modelo').json['disponivel'])
        self.assertEqual(self.client.post('/api/prever',json=dict(tempo_plataforma=4,quantidade_vistos=0,quantidade_generos=0)).status_code,422)

    def test_migracao_preserva_engajamento(self):
        with banco.conectar() as db:
            db.execute('CREATE TABLE engajamento (usuario_id INTEGER PRIMARY KEY, valor REAL)')
            db.execute('INSERT INTO engajamento VALUES (1,4.5)')
        banco.inicializar_banco()
        with banco.conectar() as db:
            self.assertEqual(tuple(db.execute('SELECT * FROM engajamento').fetchone()), (1,4.5))

    def test_migracao_catalogo_preserva_historicos(self):
        self.marcar(20, 1, True)
        with banco.conectar() as db:
            antes = [tuple(r) for r in db.execute('SELECT * FROM visualizacoes ORDER BY 1,2')]
            inicial = [tuple(r) for r in db.execute('SELECT * FROM historico_inicial ORDER BY 1,2')]
            db.execute('DELETE FROM migracoes WHERE versao=2')
            db.execute("UPDATE conteudos SET titulo='Título antigo', genero_id=10 WHERE id=1")
        banco.inicializar_banco()
        banco.inicializar_banco()
        with banco.conectar() as db:
            self.assertEqual(tuple(db.execute('SELECT titulo,genero_id FROM conteudos WHERE id=1').fetchone()), ('Matrix (1999)',1))
            self.assertEqual(antes, [tuple(r) for r in db.execute('SELECT * FROM visualizacoes ORDER BY 1,2')])
            self.assertEqual(inicial, [tuple(r) for r in db.execute('SELECT * FROM historico_inicial ORDER BY 1,2')])


class MatematicaTest(unittest.TestCase):
    def test_cosseno_e_clusters_conhecidos(self):
        vetores = [[1,0,0], [2,0,0], [0,1,0], [0,2,0], [0,0,1], [0,0,2]]
        sim = cosseno(vetores)
        self.assertAlmostEqual(sim[0,1],1)
        self.assertAlmostEqual(sim[0,2],0)
        self.assertEqual(agrupar(1-sim, [1,2,3,4,5,6]), [[1,2],[3,4],[5,6]])
        self.assertTrue(np.isfinite(cosseno([[0,0],[1,0]])).all())

    def test_ligacao_media(self):
        d = np.array([[0,.1,.2,.9],[.1,0,.8,.9],[.2,.8,0,.4],[.9,.9,.4,0]])
        self.assertEqual(agrupar(d,[1,2,3,4],2), [[1,2],[3,4]])

    def test_regressao_conhecida(self):
        x = np.array([[1,0,0],[2,1,0],[3,0,1],[4,2,3],[2,3,1]])
        y = 2 + x @ np.array([3,4,5])
        coef, r2 = ajustar_modelo(x,y)
        np.testing.assert_allclose(coef,[2,3,4,5])
        self.assertAlmostEqual(r2,1)
        self.assertIsNone(ajustar_modelo(x,np.ones(5))[1])
        with self.assertRaises(ValueError):
            ajustar_modelo([[1,1,1]]*5,[1]*5)
        with self.assertRaises(ValueError):
            ajustar_modelo([[1,2,3]],[1])


if __name__ == '__main__':
    unittest.main()
