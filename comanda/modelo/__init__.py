"""Regressão linear múltipla do tempo de preparo.

- variaveis: as variáveis do modelo e como aplicá-lo (aplicar, variaveis_do_pedido).
- minimos_quadrados: o ajuste em Python puro e a conferência com o NumPy (sem banco).
- coeficientes: β personalizados pelo usuário.
- previsao: treino com os dados do restaurante, resumo e previsão de pedidos novos.
"""
from comanda.modelo.minimos_quadrados import ajustar_modelo, ajustar_modelo_manual, comparar_numpy
from comanda.modelo.previsao import carregar_observacoes, obter_analises, obter_resumo_modelo, prever_tempo
from comanda.modelo.variaveis import NOMES_COEFICIENTES, VARIAVEIS, aplicar, variaveis_do_pedido
