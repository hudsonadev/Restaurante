import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from flask import template_rendered
import banco
from regressao import ajustar_simples, obter_analises


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

    def test_rotas_e_perfil(self):
        for rota in ['/', '/categorias', '/catalogo', '/analises', '/usuarios/1', '/usuarios/20']:
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertEqual(resposta.status_code, 200)
                self.assertIn('Navegação administrativa', resposta.get_data(as_text=True))
        resposta = self.client.get('/regressao')
        self.assertEqual(resposta.status_code, 302)
        self.assertTrue(resposta.location.endswith('/analises#regressao'))
        self.assertEqual(self.client.get('/usuarios/9999').status_code, 404)
        self.assertEqual(self.contexto('/usuarios/20')['usuario']['id'], 20)

    def test_previsoes_residuos_e_metricas(self):
        resposta = self.client.get('/api/analises')
        self.assertEqual(resposta.status_code, 200)
        dados = resposta.json
        self.assertEqual(len(dados['observacoes']), 100)
        vazio = next(p for p in dados['observacoes'] if p['id'] == 20)
        self.assertEqual(vazio['quantidade_vistos'], 0)
        for nome in ('simples', 'multipla'):
            modelo = dados[nome]
            self.assertTrue(modelo['disponivel'])
            residuos = []
            for p in dados['observacoes']:
                previsto = modelo['intercepto'] + (modelo['coeficiente'] * p['tempo_plataforma'] if nome == 'simples'
                    else sum(coef * p[v] for v, coef in modelo['coeficientes'].items()))
                self.assertAlmostEqual(p[f'previsao_{nome}'], previsto)
                residuo = p['tempo_assistindo'] - previsto
                self.assertAlmostEqual(p[f'residuo_{nome}'], residuo)
                residuos.append(residuo)
            self.assertAlmostEqual(modelo['erro_absoluto_medio'], np.mean(np.abs(residuos)))
            y = np.array([p['tempo_assistindo'] for p in dados['observacoes']])
            self.assertAlmostEqual(modelo['r_quadrado'], 1 - np.sum(np.square(residuos)) / np.sum((y-y.mean())**2))

    def test_edicao_atualiza_agregados_sem_retreinar(self):
        antes = obter_analises()
        indicadores = self.contexto('/')['indicadores']
        catalogo = self.contexto('/catalogo')['itens']
        outro = self.client.get('/api/conteudos?usuario_id=2').json
        for _ in range(2):
            self.assertEqual(self.client.put('/api/usuarios/20/vistos/1', json={'visto': True}).status_code, 200)
        self.assertEqual(obter_analises(), antes)
        self.assertEqual(self.contexto('/')['indicadores']['visualizacoes'], indicadores['visualizacoes'] + 1)
        self.assertEqual(self.contexto('/catalogo')['itens'][0]['quantidade_usuarios'], catalogo[0]['quantidade_usuarios'] + 1)
        self.assertEqual(self.client.get('/api/conteudos?usuario_id=2').json, outro)
        self.client.put('/api/usuarios/20/vistos/1', json={'visto': False})
        self.assertEqual(self.contexto('/')['indicadores'], indicadores)

    def test_indisponibilidade_independente_e_json_finito(self):
        with banco.conectar() as db:
            db.execute('DELETE FROM historico_inicial')
        dados = self.client.get('/api/analises').json
        self.assertTrue(dados['simples']['disponivel'])
        self.assertFalse(dados['multipla']['disponivel'])
        self.assertTrue(all(p['previsao_multipla'] is None for p in dados['observacoes']))
        self.assertEqual(self.client.get('/analises').status_code, 200)
        with banco.conectar() as db:
            db.execute('UPDATE usuarios SET tempo_plataforma_horas=? WHERE id=1', (float('inf'),))
        resposta = self.client.get('/api/analises')
        self.assertNotIn('Infinity', resposta.get_data(as_text=True))
        self.assertFalse(resposta.json['simples']['disponivel'])

    def test_base_vazia(self):
        with banco.conectar() as db:
            db.execute('DELETE FROM visualizacoes')
            db.execute('DELETE FROM historico_inicial')
            db.execute('DELETE FROM usuarios')
        dados = obter_analises()
        self.assertFalse(dados['simples']['disponivel'])
        self.assertFalse(dados['multipla']['disponivel'])
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get('/analises').status_code, 200)


if __name__ == '__main__':
    unittest.main()
