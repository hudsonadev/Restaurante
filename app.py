import math
from flask import Flask, jsonify, render_template, request, redirect, url_for, abort
from banco import conectar, inicializar_banco
from recomendacao import obter_clusters, recomendar
from regressao import obter_resumo_modelo, obter_analises, prever_tempo

LIMITE_FILA = 50


def consultar_cardapio(db, pedido_id=None):
    linhas = db.execute('''SELECT p.*, c.nome AS categoria,
        (SELECT COUNT(*) FROM itens_pedido i WHERE i.prato_id=p.id) AS quantidade_pedidos,
        EXISTS(SELECT 1 FROM itens_pedido i WHERE i.pedido_id=? AND i.prato_id=p.id) AS incluido
        FROM pratos p JOIN categorias c ON c.id=p.categoria_id ORDER BY p.id''', (pedido_id,))
    return [{**dict(r), 'incluido': bool(r['incluido'])} for r in linhas]


def ler_inteiro(valor, minimo, maximo):
    if isinstance(valor, bool):
        raise ValueError()
    numero = float(valor)
    if not (math.isfinite(numero) and numero.is_integer() and minimo <= numero <= maximo):
        raise ValueError()
    return int(numero)


def criar_app():
    inicializar_banco()
    app = Flask(__name__)

    @app.template_filter('numero')
    def numero(valor, casas=1):
        return 'Indefinido' if valor is None else f'{valor:.{casas}f}'.replace('.', ',')

    @app.template_filter('cientifico')
    def cientifico(valor):
        return f'{valor:.1e}'.replace('.', ',')

    @app.get('/')
    def pagina_inicial():
        with conectar() as db:
            indicadores = {t: db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                           for t in ('pedidos', 'pratos', 'categorias', 'itens_pedido')}
            medias = db.execute('SELECT AVG(pedidos_na_fila), AVG(tempo_preparo_min) FROM pedidos').fetchone()
        return render_template('index.html', indicadores=indicadores, medias=medias, analises=obter_analises())

    @app.get('/novo-pedido')
    def novo_pedido():
        with conectar() as db:
            pratos = consultar_cardapio(db)
            categorias = [dict(r) for r in db.execute('SELECT * FROM categorias ORDER BY id')]
        return render_template('novo_pedido.html', pratos=pratos, categorias=categorias, limite_fila=LIMITE_FILA)

    @app.get('/cardapio')
    def cardapio_global():
        with conectar() as db:
            itens = consultar_cardapio(db)
        return render_template('cardapio.html', itens=itens)

    @app.get('/analises')
    def pagina_analises():
        return render_template('analises.html', analises=obter_analises())

    @app.get('/regressao')
    def pagina_regressao():
        return redirect(url_for('pagina_analises', _anchor='regressao'))

    @app.get('/api/analises')
    def analises_api():
        return jsonify(obter_analises())

    @app.get('/pedidos/<int:pedido_id>')
    def pagina_pedido(pedido_id):
        analises = obter_analises()
        pedido = next((p for p in analises['observacoes'] if p['id'] == pedido_id), None)
        if pedido is None:
            abort(404)
        return render_template('pedido.html', pedido=pedido, analises=analises)

    @app.errorhandler(404)
    def nao_encontrado(erro):
        return render_template('404.html'), 404

    @app.get('/categorias')
    def categorias_mais_pedidas():
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
        return render_template('categorias.html', categorias=categorias, total=total)

    @app.get('/api/pedidos')
    def pedidos():
        with conectar() as db:
            return jsonify([dict(r) for r in db.execute('SELECT id,cliente FROM pedidos ORDER BY id')])

    @app.get('/api/pratos')
    def pratos():
        pedido_id = request.args.get('pedido_id', type=int)
        if pedido_id is None:
            return jsonify(erro='Informe pedido_id inteiro.'), 400
        with conectar() as db:
            if not db.execute('SELECT 1 FROM pedidos WHERE id=?', (pedido_id,)).fetchone():
                return jsonify(erro='Pedido não encontrado.'), 404
            return jsonify([{k: v for k, v in p.items() if k != 'quantidade_pedidos'}
                            for p in consultar_cardapio(db, pedido_id)])

    @app.get('/api/pedidos/<int:pedido_id>/sugestoes')
    def sugestoes(pedido_id):
        try:
            return jsonify(recomendar(pedido_id))
        except LookupError as erro:
            return jsonify(erro=str(erro)), 404

    @app.get('/api/clusters')
    def clusters():
        return jsonify(obter_clusters())

    @app.put('/api/pedidos/<int:pedido_id>/itens/<int:prato_id>')
    def alterar_item(pedido_id, prato_id):
        dados = request.get_json(silent=True)
        if not isinstance(dados, dict) or type(dados.get('incluido')) is not bool:
            return jsonify(erro='Informe incluido como true ou false.'), 400
        with conectar() as db:
            if not db.execute('SELECT 1 FROM pedidos WHERE id=?', (pedido_id,)).fetchone():
                return jsonify(erro='Pedido não encontrado.'), 404
            if not db.execute('SELECT 1 FROM pratos WHERE id=?', (prato_id,)).fetchone():
                return jsonify(erro='Prato não encontrado.'), 404
            if dados['incluido']:
                db.execute('INSERT OR IGNORE INTO itens_pedido VALUES (?,?)', (pedido_id, prato_id))
            else:
                db.execute('DELETE FROM itens_pedido WHERE pedido_id=? AND prato_id=?', (pedido_id, prato_id))
        return jsonify(pedido_id=pedido_id, prato_id=prato_id, incluido=dados['incluido'])

    @app.get('/api/modelo')
    def modelo():
        return jsonify(obter_resumo_modelo())

    @app.post('/api/prever')
    def prever():
        dados = request.get_json(silent=True)
        try:
            if not isinstance(dados, dict) or not isinstance(dados.get('pratos'), list) or not dados['pratos']:
                raise ValueError()
            fila = ler_inteiro(dados.get('pedidos_na_fila'), 0, LIMITE_FILA)
            ids = [ler_inteiro(p, 1, 10 ** 9) for p in dados['pratos']]
            with conectar() as db:
                total = db.execute('SELECT COUNT(*) FROM pratos').fetchone()[0]
                if len(ids) > total or len(set(ids)) != len(ids):
                    raise ValueError()
                encontrados = db.execute(f'SELECT categoria_id FROM pratos WHERE id IN ({",".join("?" * len(ids))})',
                                         ids).fetchall()
            if len(encontrados) != len(ids):
                raise ValueError()
        except (TypeError, ValueError, OverflowError):
            return jsonify(erro=f'Escolha ao menos um prato do cardápio, sem repetir, e informe a fila como inteiro entre 0 e {LIMITE_FILA}.'), 400
        try:
            return jsonify(prever_tempo(len(ids), fila, len({r['categoria_id'] for r in encontrados})))
        except ValueError as erro:
            return jsonify(erro=str(erro)), 422

    return app


app = criar_app()

if __name__ == '__main__':
    app.run(debug=True)
