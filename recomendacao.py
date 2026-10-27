"""Recomendação explicável com cosseno e agrupamento hierárquico médio."""
import numpy as np
from banco import conectar


def cosseno(linhas):
    linhas = np.asarray(linhas, dtype=float)
    normas = np.linalg.norm(linhas, axis=1, keepdims=True)
    normalizadas = np.divide(linhas, normas, out=np.zeros_like(linhas), where=normas != 0)
    return np.clip(normalizadas @ normalizadas.T, 0, 1)


def agrupar(distancias, ids, quantidade=3):
    grupos = [[i] for i in range(len(ids))]
    while len(grupos) > quantidade:
        candidatos = [(float(np.mean(distancias[np.ix_(a, b)])),
                       tuple(ids[k] for k in a), tuple(ids[k] for k in b), i, j)
                      for i, a in enumerate(grupos) for j, b in enumerate(grupos) if i < j]
        _, _, _, i, j = min(candidatos)
        unido = sorted(grupos[i] + grupos[j])
        grupos = [g for k, g in enumerate(grupos) if k not in (i, j)] + [unido]
        grupos.sort(key=lambda g: tuple(ids[k] for k in g))
    return [[ids[i] for i in grupo] for grupo in grupos]


def carregar_estado():
    with conectar() as db:
        usuarios = [dict(r) for r in db.execute('SELECT id,nome FROM usuarios ORDER BY id')]
        generos = [dict(r) for r in db.execute('SELECT * FROM generos ORDER BY id')]
        conteudos = [dict(r) for r in db.execute('''SELECT c.*, g.nome AS genero
            FROM conteudos c JOIN generos g ON c.genero_id=g.id ORDER BY c.id''')]
        vistos = list(db.execute('SELECT * FROM visualizacoes'))
    ui = {u['id']: i for i, u in enumerate(usuarios)}
    ci = {c['id']: i for i, c in enumerate(conteudos)}
    gi = {g['id']: i for i, g in enumerate(generos)}
    matriz = np.zeros((len(usuarios), len(conteudos)))
    for u, c in vistos:
        matriz[ui[u], ci[c]] = 1
    contagens = np.zeros((len(usuarios), len(generos)))
    for j, c in enumerate(conteudos):
        contagens[:, gi[c['genero_id']]] += matriz[:, j]
    totais = contagens.sum(axis=1, keepdims=True)
    perfis = np.divide(contagens, totais, out=np.zeros_like(contagens), where=totais != 0)
    return usuarios, generos, conteudos, matriz, perfis, cosseno(contagens.T)


def obter_clusters(estado=None):
    _, generos, _, _, _, similaridades = estado or carregar_estado()
    distancias = 1 - similaridades
    ids = [g['id'] for g in generos]
    grupos = agrupar(distancias, ids)
    return {
        'grupos': [{'id': i + 1, 'generos': [g for g in generos if g['id'] in grupo]}
                   for i, grupo in enumerate(grupos)],
        'generos': [{**g, 'proximos': sorted([
            {**outro, 'distancia': float(distancias[i, j]),
             'similaridade': float(similaridades[i, j])}
            for j, outro in enumerate(generos) if i != j],
            key=lambda item: (item['distancia'], item['id']))}
            for i, g in enumerate(generos)]}


def recomendar(usuario_id):
    usuarios, generos, conteudos, matriz, perfis, sim_generos = carregar_estado()
    indice = next((i for i, u in enumerate(usuarios) if u['id'] == usuario_id), None)
    if indice is None:
        raise LookupError('Usuário não encontrado.')
    similaridades = cosseno(perfis)[indice]
    vizinhos = sorted([i for i in range(len(usuarios))
                       if i != indice and similaridades[i] > 0],
                      key=lambda i: (-similaridades[i], usuarios[i]['id']))[:5]
    gi = {g['id']: i for i, g in enumerate(generos)}
    popularidade = matriz.sum(axis=0)
    sem_historico = not matriz[indice].any()
    afinidades = perfis[indice] @ sim_generos
    itens = []
    for j, conteudo in enumerate(conteudos):
        if matriz[indice, j]:
            continue
        genero = gi[conteudo['genero_id']]
        afinidade = float(afinidades[genero])
        colaborativa = float(np.average(matriz[vizinhos, j], weights=similaridades[vizinhos])) if vizinhos else 0
        score = float(popularidade[j] / max(1, len(usuarios))) if sem_historico else (
            (afinidade + colaborativa) / 2 if vizinhos else afinidade)
        motivos = []
        if sem_historico:
            motivos.append(f'Popular na base: visto por {int(popularidade[j])} usuários.')
        elif afinidade > 0:
            referencia = max(range(len(generos)), key=lambda k: perfis[indice, k] * sim_generos[k, genero])
            motivos.append(f"Afinidade com {generos[referencia]['nome']}, presente no seu histórico.")
        nomes = [usuarios[i]['nome'] for i in vizinhos if matriz[i, j]]
        if nomes:
            motivos.append('Visto por usuários semelhantes: ' + ', '.join(nomes) + '.')
        itens.append({**conteudo, 'pontuacao': score, 'afinidade_genero': afinidade,
                      'pontuacao_colaborativa': colaborativa, 'popularidade': int(popularidade[j]),
                      'motivos': motivos or ['Sugestão para explorar o catálogo, sem afinidade observada.']})
    itens.sort(key=lambda c: (-c['pontuacao'], -c['popularidade'], c['id']))
    return {'usuario': usuarios[indice], 'sem_historico': sem_historico,
            'recomendacoes': itens[:10],
            'usuarios_semelhantes': [{**usuarios[i], 'similaridade': float(similaridades[i])} for i in vizinhos]}
