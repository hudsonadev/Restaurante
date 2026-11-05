"""A cozinha sintética: cardápio com o tempo de cada prato e a regra que gera o tempo real.

Como o tempo real de um pedido é gerado (dados sintéticos, a regra é nossa):
- A cozinha prepara os pratos em PARALELO: o prato mais demorado define a base,
  e cada prato a mais acrescenta só uma fração (FATOR_PARALELISMO) do próprio tempo.
      cozinha = maior tempo + FATOR_PARALELISMO × (soma dos tempos − maior tempo)
- Tempo real = 3 + cozinha + 1,3 × fila + 0,8 × categorias distintas + ruído normal (σ = DESVIO_RUIDO).
- O ruído representa o que nenhuma variável registra numa cozinha real (equipe do turno,
  forno atrasado, horário de pico). DESVIO_RUIDO foi calibrado para que o modelo correto
  reduza o erro em ~75–76% frente a prever sempre a média, em pedidos não vistos.

A mesma regra gera o histórico (comanda.dados) e os pedidos novos da Cozinha (comanda.acompanhamento).
O modelo não a conhece: ele usa o maior prato, os demais pratos, a fila e as categorias.
"""
FATOR_PARALELISMO = 0.35
DESVIO_RUIDO = 3.7

# Prato: tempo individual de preparo em minutos, conforme a complexidade.
CARDAPIO = {
    'Entradas': {'Bruschetta de tomate': 7, 'Bolinho de bacalhau': 10, 'Carpaccio': 6,
                 'Pastel de feira': 8, 'Dadinho de tapioca': 9, 'Croquete de costela': 11},
    'Saladas': {'Salada Caesar': 6, 'Salada caprese': 4, 'Salada de grão-de-bico': 5,
                'Salada tropical': 5, 'Salada de quinoa': 7, 'Salada verde': 4},
    'Sopas': {'Caldo verde': 8, 'Creme de abóbora': 7, 'Sopa de legumes': 6,
              'Caldo de feijão': 8, 'Canja de galinha': 9, 'Creme de cebola': 7},
    'Bebidas': {'Suco de laranja': 3, 'Limonada suíça': 4, 'Refrigerante lata': 1,
                'Água com gás': 1, 'Chá gelado': 2, 'Café expresso': 2},
    'Massas': {'Espaguete à bolonhesa': 12, 'Lasanha à bolonhesa': 18, 'Fettuccine Alfredo': 13,
               'Penne ao pesto': 11, 'Nhoque ao sugo': 12, 'Ravióli de queijo': 14},
    'Risotos': {'Risoto de cogumelos': 20, 'Risoto de camarão': 22, 'Risoto de limão-siciliano': 19,
                'Risoto de abóbora': 20, 'Risoto de filé': 22, 'Risoto de alho-poró': 19},
    'Grelhados': {'Picanha grelhada': 20, 'Filé de frango grelhado': 15, 'Bife ancho': 18,
                  'Costela suína': 22, 'Salmão grelhado': 16, 'Linguiça artesanal': 14},
    'Lanches': {'X-burger': 10, 'X-salada': 10, 'Sanduíche natural': 6,
                'Misto quente': 6, 'Hambúrguer vegetariano': 11, 'Wrap de frango': 8},
    'Porções': {'Batata frita': 10, 'Mandioca frita': 12, 'Isca de peixe': 12,
                'Calabresa acebolada': 9, 'Anéis de cebola': 10, 'Frango a passarinho': 15},
    'Sobremesas': {'Pudim de leite': 2, 'Petit gâteau': 7, 'Mousse de maracujá': 2,
                   'Brownie com sorvete': 5, 'Torta de limão': 3, 'Sorvete de creme': 2},
}
# Estilos de pedido (IDs de categoria) que tornam os agrupamentos observáveis.
GRUPOS = [[1, 2, 3, 4], [5, 6, 7], [8, 9, 10]]


def tempo_cozinha(tempos):
    """Pratos em paralelo: o mais demorado inteiro, mais uma fração dos demais."""
    maior = max(tempos)
    return maior + FATOR_PARALELISMO * (sum(tempos) - maior)


def tempo_real(tempos, fila, categorias, rng):
    """A regra da cozinha sintética: gera o tempo real de um pedido (com ruído aleatório).

    É a mesma regra do histórico e da página Cozinha (modo simulado), então os pedidos novos
    são comparáveis aos 100 pedidos de treino."""
    tempo = 3 + tempo_cozinha(tempos) + 1.3 * fila + 0.8 * categorias + rng.gauss(0, DESVIO_RUIDO)
    return round(max(tempo, 3), 1)


def sortear_pratos(rng, categoria_por_prato, preferidas, quantidade):
    """Sorteia pratos distintos, com peso 9 nas categorias preferidas e 0,4 nas demais."""
    candidatos = sorted(categoria_por_prato)
    escolhidos = []
    for _ in range(quantidade):
        pesos = [9 if categoria_por_prato[c] in preferidas else 0.4 for c in candidatos]
        prato = rng.choices(candidatos, weights=pesos, k=1)[0]
        candidatos.remove(prato)
        escolhidos.append(prato)
    return escolhidos
