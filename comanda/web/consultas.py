"""Consultas de leitura usadas pelas páginas e pela API."""
from comanda import acompanhamento
from comanda.db import conectar
from comanda.modelo import obter_analises


def existe(db, tabela, registro_id):
    return db.execute(f'SELECT 1 FROM {tabela} WHERE id=?', (registro_id,)).fetchone() is not None


def consultar_cardapio(db, pedido_id=None):
    linhas = db.execute('''SELECT p.*, c.nome AS categoria,
        (SELECT COUNT(*) FROM itens_pedido i WHERE i.prato_id=p.id) AS quantidade_pedidos,
        EXISTS(SELECT 1 FROM itens_pedido i WHERE i.pedido_id=? AND i.prato_id=p.id) AS incluido
        FROM pratos p JOIN categorias c ON c.id=p.categoria_id ORDER BY p.id''', (pedido_id,))
    return [{**dict(r), 'incluido': bool(r['incluido'])} for r in linhas]


def indicadores_gerais():
    """Contagens das tabelas e as médias de fila e de preparo do histórico."""
    with conectar() as db:
        indicadores = {t: db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                       for t in ('pedidos', 'pratos', 'categorias', 'itens_pedido')}
        medias = db.execute('SELECT AVG(pedidos_na_fila), AVG(tempo_preparo_min) FROM pedidos').fetchone()
    return indicadores, medias


def ranking_categorias():
    """Categorias por número de pratos nos pedidos atuais (Cardápio e /categorias)."""
    with conectar() as db:
        categorias = [dict(r) for r in db.execute('''
            SELECT c.id, c.nome, COUNT(i.pedido_id) AS quantidade
            FROM categorias c
            LEFT JOIN pratos p ON p.categoria_id = c.id
            LEFT JOIN itens_pedido i ON i.prato_id = p.id
            GROUP BY c.id, c.nome
            ORDER BY quantidade DESC, c.nome, c.id
        ''')]
    total = sum(c['quantidade'] for c in categorias)
    maior = max((c['quantidade'] for c in categorias), default=0)
    for categoria in categorias:
        categoria['percentual'] = 100 * categoria['quantidade'] / total if total else 0
        categoria['largura'] = 100 * categoria['quantidade'] / maior if maior else 0
    return categorias, total


def analises_com_acompanhados():
    """Análises do histórico + pedidos novos concluídos (só para exibir; não entram no treino)."""
    analises = obter_analises()
    analises['acompanhados'] = acompanhamento.resumo()['concluidos']
    return analises
