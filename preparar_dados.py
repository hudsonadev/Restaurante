"""Gera o cardápio e os pedidos sintéticos em dados/. Não modifica o banco."""
import csv
import random
from banco import DIRETORIO_DADOS

BASE = DIRETORIO_DADOS
SEMENTE = 20261028

CARDAPIO = {
    'Entradas': ['Bruschetta de tomate', 'Bolinho de bacalhau', 'Carpaccio', 'Pastel de feira', 'Dadinho de tapioca', 'Croquete de costela'],
    'Saladas': ['Salada Caesar', 'Salada caprese', 'Salada de grão-de-bico', 'Salada tropical', 'Salada de quinoa', 'Salada verde'],
    'Sopas': ['Caldo verde', 'Creme de abóbora', 'Sopa de legumes', 'Caldo de feijão', 'Canja de galinha', 'Creme de cebola'],
    'Bebidas': ['Suco de laranja', 'Limonada suíça', 'Refrigerante lata', 'Água com gás', 'Chá gelado', 'Café expresso'],
    'Massas': ['Espaguete à bolonhesa', 'Lasanha à bolonhesa', 'Fettuccine Alfredo', 'Penne ao pesto', 'Nhoque ao sugo', 'Ravióli de queijo'],
    'Risotos': ['Risoto de cogumelos', 'Risoto de camarão', 'Risoto de limão-siciliano', 'Risoto de abóbora', 'Risoto de filé', 'Risoto de alho-poró'],
    'Grelhados': ['Picanha grelhada', 'Filé de frango grelhado', 'Bife ancho', 'Costela suína', 'Salmão grelhado', 'Linguiça artesanal'],
    'Lanches': ['X-burger', 'X-salada', 'Sanduíche natural', 'Misto quente', 'Hambúrguer vegetariano', 'Wrap de frango'],
    'Porções': ['Batata frita', 'Mandioca frita', 'Isca de peixe', 'Calabresa acebolada', 'Anéis de cebola', 'Frango a passarinho'],
    'Sobremesas': ['Pudim de leite', 'Petit gâteau', 'Mousse de maracujá', 'Brownie com sorvete', 'Torta de limão', 'Sorvete de creme'],
}
# Minutos somados por prato de cada categoria; só entram na geração do tempo real.
AJUSTE_CATEGORIA = {'Grelhados': 1.5, 'Risotos': 1.0, 'Massas': 0.5, 'Sobremesas': -0.5, 'Bebidas': -1.5}
# Estilos de pedido (IDs de categoria) que tornam os agrupamentos observáveis.
GRUPOS = [[1, 2, 3, 4], [5, 6, 7], [8, 9, 10]]


def escrever(nome, campos, linhas):
    with (BASE / nome).open('w', encoding='utf-8', newline='') as arquivo:
        writer = csv.writer(arquivo)
        writer.writerow(campos)
        writer.writerows(linhas)


def preparar():
    rng = random.Random(SEMENTE)
    categorias = list(CARDAPIO)
    escrever('categorias.csv', ['categoria_id', 'nome'], list(enumerate(categorias, 1)))
    pratos = [(i, nome, cid) for i, (nome, cid) in enumerate(
        ((nome, cid) for cid, categoria in enumerate(categorias, 1) for nome in CARDAPIO[categoria]), 1)]
    escrever('pratos.csv', ['prato_id', 'nome', 'categoria_id'], pratos)
    categoria_por_prato = {p[0]: p[2] for p in pratos}
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
        ajuste = sum(AJUSTE_CATEGORIA.get(categorias[categoria_por_prato[p] - 1], 0) for p in escolhidos)
        tempo = 6 + 2.2 * quantidade + 1.3 * fila + 0.8 * len(distintas) + ajuste + rng.gauss(0, 2.2)
        cliente = f'{nomes[(pid - 1) % 10]} {sobrenomes[(pid - 1) // 10]}'
        pedidos.append((pid, cliente, fila, round(max(tempo, 3), 1)))
        itens.extend((pid, p) for p in escolhidos)
    escrever('pedidos.csv', ['pedido_id', 'cliente', 'pedidos_na_fila', 'tempo_preparo_min'], pedidos)
    escrever('itens_pedido.csv', ['pedido_id', 'prato_id'], sorted(itens))


if __name__ == '__main__':
    preparar()
