"""As variáveis do modelo e como aplicá-lo.

    Y = β0 + β1·maior prato + β2·demais pratos + β3·fila + β4·categorias + E

O maior prato e os demais pratos separam o tempo dos pratos do pedido: a cozinha prepara
os pratos em paralelo, então o mais demorado pesa muito mais que os outros.
"""
VARIAVEIS = ['tempo_maior_prato', 'tempo_demais_pratos', 'pedidos_na_fila', 'quantidade_categorias']
NOMES_COEFICIENTES = ['intercepto'] + VARIAVEIS
ROTULOS = {'tempo_maior_prato': 'maior prato', 'tempo_demais_pratos': 'demais pratos',
           'pedidos_na_fila': 'fila', 'quantidade_categorias': 'categorias'}
EM_MINUTOS = {'tempo_maior_prato', 'tempo_demais_pratos'}


def aplicar(coeficientes, valores):
    """ŷ = β0 + Σ βi·xi. coeficientes: {intercepto, variável: β}; valores: {variável: x}."""
    return coeficientes['intercepto'] + sum(coeficientes[v] * valores[v] for v in VARIAVEIS)


def variaveis_do_pedido(tempos_pratos, pedidos_na_fila, quantidade_categorias):
    """Variáveis do modelo a partir dos tempos individuais dos pratos de um pedido."""
    maior = max(tempos_pratos)
    return dict(zip(VARIAVEIS, [maior, sum(tempos_pratos) - maior, pedidos_na_fila, quantidade_categorias]))
