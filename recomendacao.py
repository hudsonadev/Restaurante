"""Sugestões explicáveis de pratos com cosseno e agrupamento hierárquico médio."""
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
        pedidos = [dict(r) for r in db.execute('SELECT id,cliente FROM pedidos ORDER BY id')]
        categorias = [dict(r) for r in db.execute('SELECT * FROM categorias ORDER BY id')]
        pratos = [dict(r) for r in db.execute('''SELECT p.*, c.nome AS categoria
            FROM pratos p JOIN categorias c ON p.categoria_id=c.id ORDER BY p.id''')]
        itens = list(db.execute('SELECT * FROM itens_pedido'))
    pi = {p['id']: i for i, p in enumerate(pedidos)}
    ri = {p['id']: i for i, p in enumerate(pratos)}
    ci = {c['id']: i for i, c in enumerate(categorias)}
    matriz = np.zeros((len(pedidos), len(pratos)))
    for pedido, prato in itens:
        matriz[pi[pedido], ri[prato]] = 1
    contagens = np.zeros((len(pedidos), len(categorias)))
    for j, prato in enumerate(pratos):
        contagens[:, ci[prato['categoria_id']]] += matriz[:, j]
    totais = contagens.sum(axis=1, keepdims=True)
    perfis = np.divide(contagens, totais, out=np.zeros_like(contagens), where=totais != 0)
    return pedidos, categorias, pratos, matriz, perfis, cosseno(contagens.T)


def obter_clusters(estado=None):
    _, categorias, _, _, _, similaridades = estado or carregar_estado()
    distancias = 1 - similaridades
    ids = [c['id'] for c in categorias]
    grupos = agrupar(distancias, ids)
    return {
        'grupos': [{'id': i + 1, 'categorias': [c for c in categorias if c['id'] in grupo]}
                   for i, grupo in enumerate(grupos)],
        'categorias': [{**c, 'proximos': sorted([
            {**outra, 'distancia': float(distancias[i, j]),
             'similaridade': float(similaridades[i, j])}
            for j, outra in enumerate(categorias) if i != j],
            key=lambda item: (item['distancia'], item['id']))}
            for i, c in enumerate(categorias)]}


def recomendar(pedido_id):
    pedidos, categorias, pratos, matriz, perfis, sim_categorias = carregar_estado()
    indice = next((i for i, p in enumerate(pedidos) if p['id'] == pedido_id), None)
    if indice is None:
        raise LookupError('Pedido não encontrado.')
    similaridades = cosseno(perfis)[indice]
    vizinhos = sorted([i for i in range(len(pedidos))
                       if i != indice and similaridades[i] > 0],
                      key=lambda i: (-similaridades[i], pedidos[i]['id']))[:5]
    ci = {c['id']: i for i, c in enumerate(categorias)}
    popularidade = matriz.sum(axis=0)
    pedido_vazio = not matriz[indice].any()
    afinidades = perfis[indice] @ sim_categorias
    sugestoes = []
    for j, prato in enumerate(pratos):
        if matriz[indice, j]:
            continue
        categoria = ci[prato['categoria_id']]
        afinidade = float(afinidades[categoria])
        colaborativa = float(np.average(matriz[vizinhos, j], weights=similaridades[vizinhos])) if vizinhos else 0
        score = float(popularidade[j] / max(1, len(pedidos))) if pedido_vazio else (
            (afinidade + colaborativa) / 2 if vizinhos else afinidade)
        motivos = []
        if pedido_vazio:
            motivos.append(f'Popular: presente em {int(popularidade[j])} pedidos.')
        elif afinidade > 0:
            referencia = max(range(len(categorias)), key=lambda k: perfis[indice, k] * sim_categorias[k, categoria])
            motivos.append(f"Combina com {categorias[referencia]['nome']}, presente no pedido.")
        nomes = [f"#{pedidos[i]['id']} {pedidos[i]['cliente']}" for i in vizinhos if matriz[i, j]]
        if nomes:
            motivos.append('Incluído em pedidos semelhantes: ' + ', '.join(nomes) + '.')
        sugestoes.append({**prato, 'pontuacao': score, 'afinidade_categoria': afinidade,
                          'pontuacao_colaborativa': colaborativa, 'popularidade': int(popularidade[j]),
                          'motivos': motivos or ['Opção para variar o pedido, sem afinidade observada.']})
    sugestoes.sort(key=lambda c: (-c['pontuacao'], -c['popularidade'], c['id']))
    return {'pedido': pedidos[indice], 'pedido_vazio': pedido_vazio,
            'sugestoes': sugestoes[:10],
            'pedidos_semelhantes': [{**pedidos[i], 'similaridade': float(similaridades[i])} for i in vizinhos]}
