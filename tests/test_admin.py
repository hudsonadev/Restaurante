import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from flask import template_rendered
from comanda import acompanhamento, criar_app, db as banco
from comanda.migracoes import inicializar_banco
from comanda.modelo import VARIAVEIS, ajustar_modelo, ajustar_modelo_manual, comparar_numpy, minimos_quadrados, obter_analises


class RegressaoManualTest(unittest.TestCase):
    X = [[1, 0, 0], [2, 1, 0], [3, 0, 1], [4, 2, 3], [2, 3, 1], [5, 1, 2]]

    def test_plano_conhecido_e_alvo_constante(self):
        y = [2 + 3 * a + 4 * b + 5 * c for a, b, c in self.X]
        coef, r2 = ajustar_modelo_manual(self.X, y)
        np.testing.assert_allclose(coef, [2, 3, 4, 5])
        self.assertAlmostEqual(r2, 1)
        self.assertIsNone(ajustar_modelo_manual(self.X, [7] * len(self.X))[1])

    def test_manual_confere_com_numpy(self):
        rng = np.random.default_rng(1)
        x = rng.uniform(0, 50, size=(40, 3)).tolist()
        y = [9 + 0.4 * a + 1.3 * b + 0.2 * c + rng.normal(0, 2) for a, b, c in x]
        manual, r2 = ajustar_modelo_manual(x, y)
        via_numpy, r2_numpy = ajustar_modelo(x, y)
        np.testing.assert_allclose(manual, via_numpy, rtol=1e-10, atol=1e-10)
        self.assertAlmostEqual(r2, r2_numpy)
        diferencas = comparar_numpy(x, y)['diferencas']
        self.assertLess(max(diferencas.values()), 1e-9)

    def test_funcao_manual_nao_usa_numpy(self):
        y = [2 + 3 * a + 4 * b + 5 * c for a, b, c in self.X]
        with patch.object(minimos_quadrados, 'np', None):
            coef, r2 = ajustar_modelo_manual(self.X, y)
        self.assertIsInstance(coef[0], float)
        self.assertAlmostEqual(coef[1], 3)
        self.assertAlmostEqual(r2, 1)

    def test_variaveis_dependentes_e_amostras_invalidas(self):
        with self.assertRaises(ValueError):
            ajustar_modelo_manual([[1, 2, 3], [2, 4, 6], [3, 6, 9], [4, 8, 12], [5, 10, 15]], [1, 2, 3, 4, 5])
        for x, y in [([], []), ([[1, 2, 3]], [1]), (self.X[:3], [1, 2, 3]), (self.X, [1, 2]),
                     ([[1, 2, 3], [1, 2], [3, 4, 5], [6, 7, 8]], [1, 2, 3, 4]), ([[1, 2, float('inf')]] + self.X[1:], [1] * 6),
                     (self.X, [1, 2, 3, 4, 5, float('nan')]), ([[1, 'x', 3]] + self.X[1:], [1] * 6)]:
            with self.subTest(x=x, y=y), self.assertRaises(ValueError):
                ajustar_modelo_manual(x, y)


class AdminTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        banco_patch = patch.object(banco, 'CAMINHO_BANCO', Path(temp.name) / 'teste.db')
        banco_patch.start()
        self.addCleanup(banco_patch.stop)
        self.app = criar_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def contexto(self, rota):
        contextos = []
        def capturar(sender, template, context, **kwargs):
            contextos.append(context)
        with template_rendered.connected_to(capturar, self.app):
            resposta = self.client.get(rota)
        self.assertEqual(resposta.status_code, 200)
        return contextos[0]

    def test_rotas_e_pedido(self):
        for rota in ['/', '/novo-pedido', '/cozinha', '/historico', '/categorias', '/cardapio', '/analises', '/pedidos/1', '/pedidos/20']:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200)
                self.assertIn('Navegação administrativa', resposta.get_data(as_text=True))
        resposta = self.client.get('/regressao')
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.location.endswith('/analises#regressao'))
        self.assertEqual(self.client.get('/pedidos/9999').status_code, 404)
        self.assertEqual(self.contexto('/pedidos/20')['pedido']['id'], 20)
        self.assertEqual(len(self.contexto('/novo-pedido')['pratos']), 60)

    def test_previsoes_residuos_e_metricas(self):
        resposta = self.client.get('/api/analises')
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json
        self.assertEqual(len(dados['observacoes']), 100)
        modelo = dados['multipla']
        self.assertTrue(modelo['disponivel'])
        self.assertNotIn('simples', dados)
        residuos = []
        for p in dados['observacoes']:
            previsto = modelo['intercepto'] + sum(coef * p[v] for v, coef in modelo['coeficientes'].items())
            self.assertAlmostEqual(p['previsao_multipla'], previsto)
            self.assertAlmostEqual(p['residuo_multipla'], p['tempo_preparo'] - previsto)
            residuos.append(p['tempo_preparo'] - previsto)
        self.assertAlmostEqual(modelo['erro_absoluto_medio'], np.mean(np.abs(residuos)))
        y = np.array([p['tempo_preparo'] for p in dados['observacoes']])
        self.assertAlmostEqual(modelo['r_quadrado'], 1 - np.sum(np.square(residuos)) / np.sum((y - y.mean()) ** 2))
        self.assertLess(max(modelo['comparacao_numpy']['diferencas'].values()), 1e-9)
        self.assertEqual(dados['multipla']['variaveis'], ['tempo_maior_prato', 'tempo_demais_pratos', 'pedidos_na_fila', 'quantidade_categorias'])
        for p in dados['observacoes']:
            self.assertAlmostEqual(p['tempo_maior_prato'] + p['tempo_demais_pratos'], p['tempo_base_itens'])

    def test_pedido_novo_previsao_e_tempo_real(self):
        from datetime import datetime, timedelta
        inicio = datetime(2026, 11, 4, 12, 0, 0)
        relogio = [inicio]
        pedido = {'pratos': [25, 26, 37], 'pedidos_na_fila': 6}
        antes = obter_analises()
        previsto = self.client.post('/api/prever', json=pedido).json['multipla']['previsao_minutos']
        with patch.object(acompanhamento, 'agora', lambda: relogio[0]), patch.object(acompanhamento, 'MODO_TEMPO', 'relogio'):
            r = self.client.post('/api/acompanhados', json=pedido)
            self.assertEqual(r.status_code, 201)
            novo = r.json
            self.assertFalse(novo['pronto'])
            self.assertAlmostEqual(novo['previsao_min'], previsto)
            self.assertEqual(sorted(novo['pratos']), sorted(['Espaguete à bolonhesa', 'Lasanha à bolonhesa', 'Picanha grelhada']))
            # A previsão gravada não muda se os β mudarem depois.
            self.client.put('/api/coeficientes', json={'intercepto': 0, 'tempo_maior_prato': 1, 'tempo_demais_pratos': 1,
                                                       'pedidos_na_fila': 1, 'quantidade_categorias': 1})
            relogio[0] = inicio + timedelta(minutes=37)
            self.assertEqual(self.client.get('/api/acompanhados').json['em_preparo'][0]['id'], novo['id'])
            self.assertIn('Em preparo', self.client.get('/cozinha').get_data(as_text=True))
            pronto = self.client.post(f"/api/acompanhados/{novo['id']}/pronto").json
            self.assertAlmostEqual(pronto['tempo_real_min'], 37)
            self.assertAlmostEqual(pronto['erro_min'], 37 - previsto)
            self.assertAlmostEqual(pronto['previsao_min'], previsto)
            self.assertEqual(self.client.post(f"/api/acompanhados/{novo['id']}/pronto").status_code, 409)
        self.client.delete('/api/coeficientes')
        self.assertEqual(self.client.post('/api/acompanhados/9999/pronto').status_code, 404)
        self.assertEqual(self.client.post('/api/acompanhados', json={'pratos': [], 'pedidos_na_fila': 1}).status_code, 400)
        resumo = self.client.get('/api/acompanhados').json
        self.assertEqual(resumo['quantidade'], 1)
        self.assertAlmostEqual(resumo['erro_absoluto_medio'], abs(37 - previsto))
        # Os pedidos novos não entram no treino; aparecem no gráfico como "acompanhados".
        self.assertEqual(obter_analises(), antes)
        contexto = self.contexto('/analises')['analises']
        self.assertEqual(contexto['acompanhados'][0]['id'], novo['id'])
        self.assertIn('Pedidos novos (1)', self.client.get('/analises').get_data(as_text=True))
        self.assertIn('Erro médio em pedidos novos', self.client.get('/').get_data(as_text=True))

    def test_pronto_simulado_usa_a_regra_da_cozinha(self):
        import random
        from datetime import timedelta
        from comanda.cozinha import tempo_real
        self.assertEqual(acompanhamento.MODO_TEMPO, 'simulado')
        inicio = acompanhamento.agora()
        relogio = [inicio]
        with patch.object(acompanhamento, '_aleatorio', random.Random(7)), patch.object(acompanhamento, 'agora', lambda: relogio[0]):
            novo = self.client.post('/api/acompanhados', json={'pratos': [25, 26, 37], 'pedidos_na_fila': 6}).json
            # A cozinha decide no ENVIO: Espaguete 12, Lasanha 18, Picanha 20; fila 6; 2 categorias; mesmo sorteio.
            sorteado = tempo_real([12, 18, 20], 6, 2, random.Random(7))
            self.assertAlmostEqual(novo['tempo_sorteado_min'], sorteado)
            self.assertFalse(novo['pronto_para_sair'])
            pagina = self.client.get('/cozinha').get_data(as_text=True)
            self.assertIn('disabled title="A cozinha ainda está preparando"', pagina)
            self.assertIn(f'data-aceleracao="{acompanhamento.ACELERACAO_SIMULACAO}"', pagina)
            # Antes de a cozinha terminar, o Pronto é recusado.
            self.assertEqual(self.client.post(f"/api/acompanhados/{novo['id']}/pronto").status_code, 409)
            # Relógio acelerado: o tempo sorteado passa em sorteado / (aceleração / 60) minutos reais.
            relogio[0] = inicio + timedelta(minutes=sorteado / (acompanhamento.ACELERACAO_SIMULACAO / 60) + 0.01)
            self.assertTrue(self.client.get('/api/acompanhados').json['em_preparo'][0]['pronto_para_sair'])
            pronto = self.client.post(f"/api/acompanhados/{novo['id']}/pronto").json
        self.assertAlmostEqual(pronto['tempo_real_min'], sorteado)
        self.assertEqual(pronto['origem_tempo'], 'simulado')
        self.assertIn('Modo simulado', self.client.get('/cozinha').get_data(as_text=True))
        self.assertEqual(self.client.get('/api/acompanhados').json['aceleracao'], 120)

    def test_pedido_concluido_antes_do_modo_simulado(self):
        # Banco antigo: pedido pronto sem tempo_real_min gravado → usa o tempo do relógio.
        with banco.conectar() as db:
            db.execute('''INSERT INTO pedidos_acompanhados (criado_em, pronto_em, pedidos_na_fila, quantidade_itens,
                quantidade_categorias, tempo_maior_prato, tempo_demais_pratos, previsao_min, personalizado)
                VALUES ('2026-11-04T20:00:00', '2026-11-04T20:30:00', 2, 1, 1, 20, 0, 25.0, 0)''')
        inicializar_banco()
        concluido = self.client.get('/api/acompanhados').json['concluidos'][0]
        self.assertAlmostEqual(concluido['tempo_real_min'], 30)
        self.assertEqual(concluido['origem_tempo'], 'relogio')
        self.assertEqual(self.client.get('/cozinha').status_code, 200)

    def test_simulacao_em_lote_e_comparavel_ao_historico(self):
        import random
        antes = obter_analises()
        criados = acompanhamento.simular(200, random.Random(11))
        self.assertEqual(len(criados), 200)
        self.assertTrue(all(p['pronto'] and p['origem_tempo'] == 'simulado' for p in criados))
        self.assertTrue(all(1 <= p['quantidade_itens'] <= 8 and 0 <= p['pedidos_na_fila'] <= 12 for p in criados))
        resumo = acompanhamento.resumo()
        # Mesma cozinha do treino: o erro em pedidos novos fica na faixa da validação cruzada (~3 min), sem viés grande.
        self.assertTrue(2.0 < resumo['erro_absoluto_medio'] < 4.0, resumo['erro_absoluto_medio'])
        self.assertLess(abs(resumo['vies_medio']), 1.0)
        self.assertEqual(obter_analises(), antes)
        r = self.client.post('/api/acompanhados/simular', json={'quantidade': 3})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json['resumo']['quantidade'], 203)
        for q in (0, 51, 'x', 2.5):
            self.assertEqual(self.client.post('/api/acompanhados/simular', json={'quantidade': q}).status_code, 400)

    def test_coeficientes_personalizados(self):
        calculados = self.client.get('/api/coeficientes').json
        self.assertFalse(calculados['personalizado'])
        self.assertEqual(calculados['em_uso'], calculados['calculados'])
        antes = self.client.post('/api/prever', json={'pratos': [25, 26, 37], 'pedidos_na_fila': 6}).json['multipla']
        novos = {'intercepto': 3, 'tempo_maior_prato': 1, 'tempo_demais_pratos': 0.355, 'pedidos_na_fila': 1.3, 'quantidade_categorias': 0.8}
        r = self.client.put('/api/coeficientes', json=novos)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json['personalizado'])
        # Os mínimos quadrados dão o menor erro possível: qualquer outro β tem R² menor ou igual.
        self.assertLessEqual(r.json['r_quadrado'], r.json['r_quadrado_calculado'])
        # Vale em todo o sistema: previsão da API, observações e páginas.
        depois = self.client.post('/api/prever', json={'pratos': [25, 26, 37], 'pedidos_na_fila': 6}).json['multipla']
        self.assertAlmostEqual(depois['previsao_bruta'], 3 + 1 * 20 + 0.355 * 30 + 1.3 * 6 + 0.8 * 2)
        self.assertTrue(depois['personalizado'])
        self.assertAlmostEqual(depois['previsao_calculada'], antes['previsao_bruta'])
        p = obter_analises()['observacoes'][0]
        self.assertAlmostEqual(p['previsao_multipla'], sum(novos[k] * (1 if k == 'intercepto' else p[k]) for k in novos))
        self.assertIn('Usando β personalizados', self.client.get('/analises').get_data(as_text=True))
        self.assertIn('Usando β personalizados', self.client.get('/pedidos/1').get_data(as_text=True))
        # A comparação manual × NumPy continua mostrando os β calculados.
        comparacao = obter_analises()['multipla']['comparacao_numpy']
        self.assertAlmostEqual(comparacao['manual']['coeficientes']['intercepto'], calculados['calculados']['intercepto'])
        # Persistem após reinicializar o banco e voltam aos calculados com DELETE.
        inicializar_banco()
        self.assertTrue(self.client.get('/api/coeficientes').json['personalizado'])
        self.assertFalse(self.client.delete('/api/coeficientes').json['personalizado'])
        self.assertAlmostEqual(self.client.post('/api/prever', json={'pratos': [25, 26, 37], 'pedidos_na_fila': 6}).json['multipla']['previsao_bruta'],
                               antes['previsao_bruta'])
        for dados in [None, [], {}, {'intercepto': 1}, {**novos, 'extra': 1}, {**novos, 'intercepto': 'x'},
                      {**novos, 'intercepto': True}, {**novos, 'intercepto': float('inf')}, {**novos, 'intercepto': 5000}]:
            with self.subTest(dados=dados):
                self.assertEqual(self.client.put('/api/coeficientes', json=dados).status_code, 400)

    def test_reducao_de_erro_calibrada(self):
        """Alvo do projeto: ~75–76% menos erro que prever sempre a média, em pedidos não vistos."""
        obs = obter_analises()['observacoes']
        x = np.array([[p[v] for v in VARIAVEIS] for p in obs])
        y = np.array([p['tempo_preparo'] for p in obs])
        erros = []
        for rep in range(10):
            ordem = np.random.default_rng(rep).permutation(len(y))
            for dobra in range(10):
                teste = ordem[dobra::10]
                treino = np.setdiff1d(ordem, teste)
                coef, _ = ajustar_modelo_manual(x[treino].tolist(), y[treino].tolist())
                erros.extend(np.abs(y[teste] - np.column_stack([np.ones(len(teste)), x[teste]]) @ coef))
        reducao = 1 - np.mean(erros) / np.mean(np.abs(y - y.mean()))
        self.assertTrue(0.74 <= reducao <= 0.78, f'redução de erro {reducao:.1%}')

    def test_tempo_dos_pratos(self):
        with banco.conectar() as db:
            tempos = dict(db.execute('SELECT id, tempo_prato_min FROM pratos'))
            itens = list(db.execute('SELECT prato_id FROM itens_originais WHERE pedido_id=1'))
        self.assertEqual(len(tempos), 60)
        self.assertTrue(all(1 <= t <= 22 for t in tempos.values()))
        cardapio = self.client.get('/api/pratos?pedido_id=1').json
        self.assertEqual({p['id']: p['tempo_prato_min'] for p in cardapio}, tempos)
        pedido = obter_analises()['observacoes'][0]
        self.assertAlmostEqual(pedido['tempo_base_itens'], sum(tempos[r['prato_id']] for r in itens))
        self.assertIn('Tempo de preparo (min)', self.client.get('/cardapio').get_data(as_text=True))
        self.assertIn('Tempo base dos pratos', self.client.get('/novo-pedido').get_data(as_text=True))
        self.assertIn('Tempo base dos pratos', self.client.get('/pedidos/1').get_data(as_text=True))

    def test_edicao_atualiza_agregados_sem_retreinar(self):
        antes = obter_analises()
        indicadores = self.contexto('/')['indicadores']
        cardapio = self.contexto('/cardapio')['itens']
        outro = self.client.get('/api/pratos?pedido_id=2').json
        prato = next(p['id'] for p in self.client.get('/api/pratos?pedido_id=20').json if not p['incluido'])
        for _ in range(2):
            self.assertEqual(self.client.put(f'/api/pedidos/20/itens/{prato}', json={'incluido': True}).status_code, 200)
        self.assertEqual(obter_analises(), antes)
        self.assertEqual(self.contexto('/')['indicadores']['itens_pedido'], indicadores['itens_pedido'] + 1)
        self.assertEqual(self.contexto('/cardapio')['itens'][prato - 1]['quantidade_pedidos'], cardapio[prato - 1]['quantidade_pedidos'] + 1)
        self.assertEqual(self.client.get('/api/pratos?pedido_id=2').json, outro)
        self.client.put(f'/api/pedidos/20/itens/{prato}', json={'incluido': False})
        self.assertEqual(self.contexto('/')['indicadores'], indicadores)

    def test_indisponibilidade_independente_e_json_finito(self):
        with banco.conectar() as db:
            db.execute('UPDATE pedidos SET pedidos_na_fila=3')
        dados = self.client.get('/api/analises').json
        self.assertFalse(dados['multipla']['disponivel'])
        self.assertTrue(all(p['previsao_multipla'] is None for p in dados['observacoes']))
        self.assertEqual(self.client.get('/analises').status_code, 200)
        self.assertEqual(self.client.post('/api/prever', json={'pratos': [1, 2], 'pedidos_na_fila': 3}).status_code, 422)
        with banco.conectar() as db:
            db.execute('UPDATE pedidos SET tempo_preparo_min=? WHERE id=1', (float('inf'),))
        resposta = self.client.get('/api/analises')
        self.assertNotIn('Infinity', resposta.get_data(as_text=True))
        self.assertFalse(resposta.json['multipla']['disponivel'])

    def test_base_vazia(self):
        with banco.conectar() as db:
            db.execute('DELETE FROM itens_pedido')
            db.execute('DELETE FROM itens_originais')
            db.execute('DELETE FROM pedidos')
        dados = obter_analises()
        self.assertFalse(dados['multipla']['disponivel'])
        for rota in ('/', '/analises', '/novo-pedido'):
            self.assertEqual(self.client.get(rota).status_code, 200)


if __name__ == '__main__':
    unittest.main()
