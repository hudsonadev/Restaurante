"""Gera o cardápio e os pedidos sintéticos em dados/. Não modifica o banco.

Como o tempo real de cada pedido é gerado (dados sintéticos, a regra abaixo é nossa):
- Cada prato tem um tempo individual de preparo (TEMPO_PRATO, em minutos).
- A cozinha prepara os pratos em PARALELO: o prato mais demorado define a base,
  e cada prato a mais acrescenta só uma fração (FATOR_PARALELISMO) do próprio tempo.
      cozinha = maior tempo + FATOR_PARALELISMO × (soma dos tempos − maior tempo)
- Tempo real = 3 + cozinha + 1,3 × fila + 0,8 × categorias distintas + ruído normal (σ = 2,2).
Os modelos não conhecem essa regra: a regressão usa a SOMA dos tempos, que é só uma aproximação.
A ordem dos sorteios é a mesma da versão anterior, então os pratos e a fila de cada pedido não mudam.
"""
import csv
import random
from banco import DIRETORIO_DADOS

BASE = DIRETORIO_DADOS
SEMENTE = 20261028
FATOR_PARALELISMO = 0.35

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


def escrever(nome, campos, linhas):
    with (BASE / nome).open('w', encoding='utf-8', newline='') as arquivo:
        writer = csv.writer(arquivo)
        writer.writerow(campos)
        writer.writerows(linhas)


def tempo_cozinha(tempos):
    """Pratos em paralelo: o mais demorado inteiro, mais uma fração dos demais."""
    maior = max(tempos)
    return maior + FATOR_PARALELISMO * (sum(tempos) - maior)


def preparar():
    rng = random.Random(SEMENTE)
    categorias = list(CARDAPIO)
    escrever('categorias.csv', ['categoria_id', 'nome'], list(enumerate(categorias, 1)))
    pratos = [(i, nome, cid, tempo) for i, (nome, cid, tempo) in enumerate(
        ((nome, cid, tempo) for cid, categoria in enumerate(categorias, 1)
         for nome, tempo in CARDAPIO[categoria].items()), 1)]
    escrever('pratos.csv', ['prato_id', 'nome', 'categoria_id', 'tempo_prato_min'], pratos)
    categoria_por_prato = {p[0]: p[2] for p in pratos}
    tempo_por_prato = {p[0]: p[3] for p in pratos}
    nomes = ['Ana', 'Bruno', 'Camila', 'Diego', 'Elisa', 'Felipe', 'Gabriela', 'Hugo', 'Isabela', 'João']
    sobrenomes = ['Almeida', 'Barros', 'Costa', 'Dias', 'Esteves', 'Freitas', 'Gomes', 'Lima', 'Moura', 'Nunes']
    pedidos, itens = [], []
    for pid in range(1, 101):
        preferidas = GRUPOS[(pid - 1) % 3]
        quantidade, fila = rng.randint(1, 8), rng.randint(0, 12)
        candidatos = sorted(categoria_por_prato)
        escolhidos = []
        for _ in range(quantidade):
            pesos = [9 if categoria_por_prato[c] in preferidas else 0.4 for c in candidatos]
            prato = rng.choices(candidatos, weights=pesos, k=1)[0]
            candidatos.remove(prato)
            escolhidos.append(prato)
        distintas = {categoria_por_prato[p] for p in escolhidos}
        cozinha = tempo_cozinha([tempo_por_prato[p] for p in escolhidos])
        tempo = 3 + cozinha + 1.3 * fila + 0.8 * len(distintas) + rng.gauss(0, 2.2)
        cliente = f'{nomes[(pid - 1) % 10]} {sobrenomes[(pid - 1) // 10]}'
        pedidos.append((pid, cliente, fila, round(max(tempo, 3), 1)))
        itens.extend((pid, p) for p in escolhidos)
    escrever('pedidos.csv', ['pedido_id', 'cliente', 'pedidos_na_fila', 'tempo_preparo_min'], pedidos)
    escrever('itens_pedido.csv', ['pedido_id', 'prato_id'], sorted(itens))


if __name__ == '__main__':
    preparar()
