import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from flask import template_rendered
import banco
import regressao
from regressao import ajustar_simples, comparar_polyfit, obter_analises


class RegressaoSimplesTest(unittest.TestCase):
    def test_reta_conhecida_e_alvo_constante(self):
        coef, r2 = ajustar_simples([1, 2, 3, 4], [5, 8, 11, 14])
        np.testing.assert_allclose(coef, [2, 3])
        self.assertAlmostEqual(r2, 1)
        self.assertIsNone(ajustar_simples([1, 2, 3], [4, 4, 4])[1])

    def test_calculo_manual_confere_com_numpy(self):
        x, y = [2, 5, 7, 9, 12], [3, 4, 8, 7, 13]
        (b0, b1), r2 = ajustar_simples(x, y)
        np.testing.assert_allclose([b1, b0], np.polyfit(x, y, 1))
        erros = np.array(y) - (b0 + b1 * np.array(x))
        self.assertAlmostEqual(erros.sum(), 0)
        self.assertAlmostEqual(r2, 1 - (erros ** 2).sum() / ((np.array(y) - np.mean(y)) ** 2).sum())

    def test_comparacao_polyfit(self):
        r = comparar_polyfit([1, 2, 3, 4], [5, 8, 11, 14])
        self.assertAlmostEqual(r['manual']['intercepto'], 2)
        self.assertAlmostEqual(r['polyfit']['coeficiente'], 3)
        self.assertLess(max(r['diferenca_intercepto'], r['diferenca_coeficiente']), 1e-9)
        r = comparar_polyfit([2, 5, 7, 9, 12], [3, 4, 8, 7, 13])
        self.assertAlmostEqual(r['manual']['r_quadrado'], r['polyfit']['r_quadrado'])
        self.assertLess(max(r['diferenca_r_quadrado'], r['diferenca_previsao_maxima']), 1e-9)

    def test_funcao_manual_nao_usa_numpy(self):
        with patch.object(regressao, 'np', None):
            (b0, b1), r2 = ajustar_simples([1, 2, 3, 4], [5, 8, 11, 14])
        self.assertIsInstance(b0, float)
        self.assertAlmostEqual(b1, 3)
        self.assertAlmostEqual(r2, 1)

    def test_amostras_invalidas(self):
        for x, y in [([], []), ([1], [2]), ([1, 1], [2, 3]),
                     ([1, 2], [2]), ([1, float('inf')], [2, 3]),
                     ([1, 2], [2, float('nan')]), ([[1], [2]], [2, 3])]:
            with self.subTest(x=x, y=y), self.assertRaises(ValueError):
                ajustar_simples(x, y)


class AdminTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        banco_patch = patch.object(banco, 'CAMINHO_BANCO', Path(temp.name) / 'teste.db')
        banco_patch.start()
        self.addCleanup(banco_patch.stop)
        self.app = importlib.import_module('app').criar_app()
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
        for rota in ['/', '/novo-pedido', '/categorias', '/cardapio', '/analises', '/pedidos/1', '/pedidos/20']:
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
        for nome in ('simples', 'multipla'):
            modelo = dados[nome]
            self.assertTrue(modelo['disponivel'])
            residuos = []
            for p in dados['observacoes']:
                previsto = modelo['intercepto'] + (modelo['coeficiente'] * p['tempo_base_itens'] if nome == 'simples'
                    else sum(coef * p[v] for v, coef in modelo['coeficientes'].items()))
                self.assertAlmostEqual(p[f'previsao_{nome}'], previsto)
                residuo = p['tempo_preparo'] - previsto
                self.assertAlmostEqual(p[f'residuo_{nome}'], residuo)
                residuos.append(residuo)
            self.assertAlmostEqual(modelo['erro_absoluto_medio'], np.mean(np.abs(residuos)))
            y = np.array([p['tempo_preparo'] for p in dados['observacoes']])
            self.assertAlmostEqual(modelo['r_quadrado'], 1 - np.sum(np.square(residuos)) / np.sum((y - y.mean()) ** 2))
        comparacao = dados['simples']['comparacao_polyfit']
        self.assertLess(max(comparacao['diferenca_intercepto'], comparacao['diferenca_coeficiente'],
                            comparacao['diferenca_r_quadrado'], comparacao['diferenca_previsao_maxima']), 1e-9)
        self.assertEqual(dados['multipla']['variaveis'], ['tempo_base_itens', 'pedidos_na_fila', 'quantidade_categorias'])

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
        self.assertTrue(dados['simples']['disponivel'])
        self.assertFalse(dados['multipla']['disponivel'])
        self.assertTrue(all(p['previsao_multipla'] is None for p in dados['observacoes']))
        self.assertEqual(self.client.get('/analises').status_code, 200)
        r = self.client.post('/api/prever', json={'pratos': [1, 2], 'pedidos_na_fila': 3}).json
        self.assertFalse(r['multipla']['disponivel'])
        self.assertTrue(r['simples']['disponivel'])
        with banco.conectar() as db:
            db.execute('UPDATE pedidos SET tempo_preparo_min=? WHERE id=1', (float('inf'),))
        resposta = self.client.get('/api/analises')
        self.assertNotIn('Infinity', resposta.get_data(as_text=True))
        self.assertFalse(resposta.json['simples']['disponivel'])

    def test_base_vazia(self):
        with banco.conectar() as db:
            db.execute('DELETE FROM itens_pedido')
            db.execute('DELETE FROM itens_originais')
            db.execute('DELETE FROM pedidos')
        dados = obter_analises()
        self.assertFalse(dados['simples']['disponivel'])
        self.assertFalse(dados['multipla']['disponivel'])
        for rota in ('/', '/analises', '/novo-pedido'):
            self.assertEqual(self.client.get(rota).status_code, 200)


if __name__ == '__main__':
    unittest.main()
