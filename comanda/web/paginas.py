"""Páginas HTML."""
from flask import Blueprint, abort, redirect, render_template, request, url_for
from comanda import acompanhamento
from comanda.db import conectar
from comanda.modelo import obter_analises, obter_resumo_modelo
from comanda.web.consultas import analises_com_acompanhados, consultar_cardapio, indicadores_gerais, ranking_categorias
from comanda.web.validacao import LIMITE_FILA

bp = Blueprint('paginas', __name__)


@bp.get('/')
def pagina_inicial():
    # Início: o que está acontecendo agora na cozinha e como o modelo está indo.
    indicadores, medias = indicadores_gerais()
    return render_template('index.html', indicadores=indicadores, medias=medias,
                           modelo=obter_resumo_modelo(), analises=obter_analises(), acompanhamento=acompanhamento.resumo())


@bp.get('/novo-pedido')
def novo_pedido():
    with conectar() as db:
        pratos = consultar_cardapio(db)
        categorias = [dict(r) for r in db.execute('SELECT * FROM categorias ORDER BY id')]
    # A fila já vem preenchida com os pedidos em preparo na Cozinha (editável).
    fila_atual = min(len(acompanhamento.resumo()['em_preparo']), LIMITE_FILA)
    return render_template('novo_pedido.html', pratos=pratos, categorias=categorias, limite_fila=LIMITE_FILA, fila_atual=fila_atual)


@bp.get('/cozinha')
def pagina_cozinha():
    # Só a operação; a análise previsão × realidade fica em Análises.
    return render_template('cozinha.html', acompanhamento=acompanhamento.resumo(),
                           destaque=request.args.get('novo', type=int))


@bp.get('/analises')
def pagina_analises():
    return render_template('analises.html', analises=analises_com_acompanhados(), acompanhamento=acompanhamento.resumo())


@bp.get('/regressao')
def pagina_regressao():
    return redirect(url_for('paginas.pagina_analises', _anchor='regressao'))


@bp.get('/cardapio')
def cardapio_global():
    with conectar() as db:
        itens = consultar_cardapio(db)
    categorias, total = ranking_categorias()
    return render_template('cardapio.html', itens=itens, categorias=categorias, total=total)


@bp.get('/categorias')
def categorias_mais_pedidas():
    categorias, total = ranking_categorias()
    return render_template('categorias.html', categorias=categorias, total=total)


@bp.get('/historico')
def historico():
    return render_template('historico.html', analises=obter_analises())


@bp.get('/pedidos/<int:pedido_id>')
def pagina_pedido(pedido_id):
    analises = obter_analises()
    pedido = next((p for p in analises['observacoes'] if p['id'] == pedido_id), None)
    if pedido is None:
        abort(404)
    return render_template('pedido.html', pedido=pedido, analises=analises)


@bp.app_errorhandler(404)
def nao_encontrado(erro):
    return render_template('404.html'), 404
