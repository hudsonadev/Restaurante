"""Gera o cardápio e os 100 pedidos sintéticos em dados/ (não modifica o banco).

A ordem dos sorteios é fixa (SEMENTE): os pratos e a fila de cada pedido são sempre os mesmos.
"""
import csv
import random
from comanda.cozinha import CARDAPIO, GRUPOS, sortear_pratos, tempo_real
from comanda.db import DIRETORIO_DADOS

SEMENTE = 20261028


def escrever(nome, campos, linhas):
    with (DIRETORIO_DADOS / nome).open('w', encoding='utf-8', newline='') as arquivo:
        writer = csv.writer(arquivo)
        writer.writerow(campos)
        writer.writerows(linhas)


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
    nomes = ['Ana', 'Robson', 'Josue', 'Lourimar', 'Pedro', 'Felipe', 'Hudson', 'Laissa', 'Vanessa', 'João']
    sobrenomes = ['Almeida', 'Veloso', 'Alves', 'Rubem', 'Noleto', 'Freitas', 'Gomes', 'Lima', 'Moura', 'Nunes'] # não lembro o sobrenome de todo mundo
    pedidos, itens = [], []
    for pid in range(1, 101):
        preferidas = GRUPOS[(pid - 1) % 3]
        quantidade, fila = rng.randint(1, 8), rng.randint(0, 12)
        escolhidos = sortear_pratos(rng, categoria_por_prato, preferidas, quantidade)
        distintas = {categoria_por_prato[p] for p in escolhidos}
        tempo = tempo_real([tempo_por_prato[p] for p in escolhidos], fila, len(distintas), rng)
        cliente = f'{nomes[(pid - 1) % 10]} {sobrenomes[(pid - 1) // 10]}'
        pedidos.append((pid, cliente, fila, tempo))
        itens.extend((pid, p) for p in escolhidos)
    escrever('pedidos.csv', ['pedido_id', 'cliente', 'pedidos_na_fila', 'tempo_preparo_min'], pedidos)
    escrever('itens_pedido.csv', ['pedido_id', 'prato_id'], sorted(itens))
