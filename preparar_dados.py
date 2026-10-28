"""Gera usuários e históricos sintéticos usando o catálogo fixo. Não modifica o banco."""
import csv
import random
from banco import DIRETORIO_DADOS

BASE = DIRETORIO_DADOS


def escrever(nome, campos, linhas):
    with (BASE / nome).open('w', encoding='utf-8', newline='') as arquivo:
        writer = csv.writer(arquivo)
        writer.writerow(campos)
        writer.writerows(linhas)


def preparar():
    with (BASE / 'dataset_streaming.csv').open(encoding='utf-8', newline='') as arquivo:
        usuarios = list(csv.DictReader(arquivo))
    nomes = ['Ana', 'Bruno', 'Camila', 'Diego', 'Elisa', 'Felipe', 'Gabriela', 'Hugo', 'Isabela', 'João']
    sobrenomes = ['Almeida', 'Barros', 'Costa', 'Dias', 'Esteves', 'Freitas', 'Gomes', 'Lima', 'Moura', 'Nunes']
    escrever('dataset_streaming.csv', ['usuario_id', 'nome', 'tempo_plataforma_horas', 'tempo_assistindo_horas'], [
        (u['usuario_id'], nomes[(int(u['usuario_id']) - 1) % 10] + ' ' + sobrenomes[(int(u['usuario_id']) - 1) // 10],
         u['tempo_plataforma_horas'], u['tempo_assistindo_horas']) for u in usuarios])
    with (BASE / 'conteudos.csv').open(encoding='utf-8-sig', newline='') as arquivo:
        conteudos = list(csv.DictReader(arquivo))
    genero_por_id = {int(c['conteudo_id']): int(c['genero_id']) for c in conteudos}
    rng = random.Random(20261027)
    grupos = [[1, 2, 3, 4], [5, 6, 7], [8, 9, 10]]
    historico = []
    for u in usuarios:
        uid = int(u['usuario_id'])
        if uid % 20 == 0:
            continue
        preferidos = grupos[(uid - 1) % 3]
        quantidade = rng.randint(3, 17)
        candidatos = sorted(genero_por_id)
        for _ in range(quantidade):
            pesos = [9 if genero_por_id[c] in preferidos else 0.4 for c in candidatos]
            cid = rng.choices(candidatos, weights=pesos, k=1)[0]
            candidatos.remove(cid)
            historico.append((uid, cid))
    escrever('historico_inicial.csv', ['usuario_id', 'conteudo_id'], sorted(historico))


if __name__ == '__main__':
    preparar()

