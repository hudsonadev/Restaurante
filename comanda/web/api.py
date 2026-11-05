"""API JSON (/api/...)."""
from flask import Blueprint, jsonify, request
from comanda import acompanhamento
from comanda.db import conectar
from comanda.modelo import coeficientes, obter_analises, obter_resumo_modelo, prever_tempo
from comanda.recomendacao import obter_clusters, recomendar
from comanda.web.consultas import consultar_cardapio, existe
from comanda.web.validacao import EntradaInvalida, ler_coeficientes, ler_inclusao, ler_pedido, ler_quantidade_simulada

bp = Blueprint('api', __name__, url_prefix='/api')


def erro(mensagem, status):
    return jsonify(erro=str(mensagem)), status


@bp.errorhandler(EntradaInvalida)
def entrada_invalida(e):
    return erro(e, 400)


def prever_pedido():
    """Valida o pedido do corpo da requisição e devolve (ids, previsão).

    EntradaInvalida → 400 (handler do blueprint); ValueError → modelo indisponível."""
    ids, fila, tempos, categorias = ler_pedido(request.get_json(silent=True))
    # O modelo usa o maior tempo entre os pratos e a soma dos demais (ver modelo.variaveis_do_pedido).
    return ids, prever_tempo(tempos, fila, categorias)


# ---------- Dados do histórico ----------

@bp.get('/pedidos')
def pedidos():
    with conectar() as db:
        return jsonify([dict(r) for r in db.execute('SELECT id,cliente FROM pedidos ORDER BY id')])


@bp.get('/pratos')
def pratos():
    pedido_id = request.args.get('pedido_id', type=int)
    if pedido_id is None:
        return erro('Informe pedido_id inteiro.', 400)
    with conectar() as db:
        if not existe(db, 'pedidos', pedido_id):
            return erro('Pedido não encontrado.', 404)
        return jsonify([{k: v for k, v in p.items() if k != 'quantidade_pedidos'}
                        for p in consultar_cardapio(db, pedido_id)])


@bp.put('/pedidos/<int:pedido_id>/itens/<int:prato_id>')
def alterar_item(pedido_id, prato_id):
    incluido = ler_inclusao(request.get_json(silent=True))
    with conectar() as db:
        if not existe(db, 'pedidos', pedido_id):
            return erro('Pedido não encontrado.', 404)
        if not existe(db, 'pratos', prato_id):
            return erro('Prato não encontrado.', 404)
        if incluido:
            db.execute('INSERT OR IGNORE INTO itens_pedido VALUES (?,?)', (pedido_id, prato_id))
        else:
            db.execute('DELETE FROM itens_pedido WHERE pedido_id=? AND prato_id=?', (pedido_id, prato_id))
    return jsonify(pedido_id=pedido_id, prato_id=prato_id, incluido=incluido)


@bp.get('/pedidos/<int:pedido_id>/sugestoes')
def sugestoes(pedido_id):
    try:
        return jsonify(recomendar(pedido_id))
    except LookupError as e:
        return erro(e, 404)


@bp.get('/clusters')
def clusters():
    return jsonify(obter_clusters())


# ---------- Modelo ----------

@bp.get('/analises')
def analises():
    return jsonify(obter_analises())


@bp.get('/modelo')
def modelo():
    return jsonify(obter_resumo_modelo())


def resumo_coeficientes():
    m = obter_resumo_modelo()
    if not m['disponivel']:
        return jsonify(disponivel=False, aviso=m['aviso'])
    return jsonify(disponivel=True, personalizado=m['personalizado'], calculados=m['coeficientes_calculados'],
                   em_uso={'intercepto': m['intercepto'], **m['coeficientes']},
                   r_quadrado=m['r_quadrado'], r_quadrado_calculado=m['r_quadrado_calculado'])


@bp.get('/coeficientes')
def ver_coeficientes():
    return resumo_coeficientes()


@bp.put('/coeficientes')
def definir_coeficientes():
    # Os cinco β personalizados passam a valer em todo o sistema (previsões, páginas e API).
    valores = ler_coeficientes(request.get_json(silent=True))
    if not obter_resumo_modelo()['disponivel']:
        return erro('O modelo está indisponível com os dados atuais.', 422)
    coeficientes.salvar(valores)
    return resumo_coeficientes()


@bp.delete('/coeficientes')
def restaurar_coeficientes():
    coeficientes.limpar()
    return resumo_coeficientes()


@bp.post('/prever')
def prever():
    try:
        ids, resultado = prever_pedido()
    except ValueError as e:
        return erro(e, 422)
    resultado['quantidade_itens'] = len(ids)
    return jsonify(resultado)


# ---------- Cozinha (pedidos novos acompanhados) ----------

@bp.get('/acompanhados')
def listar_acompanhados():
    return jsonify(acompanhamento.resumo())


@bp.post('/acompanhados')
def enviar_para_cozinha():
    # Grava o pedido com a previsão DESTE momento (com os β em uso agora) e começa a contar o tempo.
    try:
        ids, previsao = prever_pedido()
    except ValueError as e:
        return erro(e, 422)
    registro = acompanhamento.registrar(previsao['entrada'], len(ids), ids,
                                        previsao['multipla']['previsao_minutos'], previsao['multipla']['personalizado'])
    return jsonify(registro), 201


@bp.post('/acompanhados/simular')
def simular_acompanhados():
    # Cria e conclui pedidos sorteados como os do histórico (tempo real pela regra da cozinha).
    quantidade = ler_quantidade_simulada(request.get_json(silent=True) or {})
    try:
        criados = acompanhamento.simular(quantidade)
    except ValueError as e:
        return erro(e, 422)
    return jsonify(criados=len(criados), resumo=acompanhamento.resumo()), 201


@bp.post('/acompanhados/<int:acompanhado_id>/pronto')
def marcar_pronto(acompanhado_id):
    try:
        registro = acompanhamento.marcar_pronto(acompanhado_id)
    except ValueError as e:
        return erro(e, 409)
    if registro is None:
        return erro('Pedido acompanhado não encontrado.', 404)
    return jsonify(registro)
