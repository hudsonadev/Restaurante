import math
from flask import Flask, jsonify, render_template, request, redirect, url_for, abort
from banco import conectar, inicializar_banco
from recomendacao import obter_clusters, recomendar
from regressao import obter_resumo_modelo, obter_analises, prever_engajamento, VARIAVEIS


def consultar_catalogo(db, usuario_id=None):
    linhas = db.execute('''SELECT c.*, g.nome AS genero,
        (SELECT COUNT(*) FROM visualizacoes v WHERE v.conteudo_id=c.id) AS quantidade_usuarios,
        EXISTS(SELECT 1 FROM visualizacoes v WHERE v.usuario_id=? AND v.conteudo_id=c.id) AS visto
        FROM conteudos c JOIN generos g ON g.id=c.genero_id ORDER BY c.id''', (usuario_id,))
    return [{**dict(r), 'visto': bool(r['visto'])} for r in linhas]


def criar_app():
    inicializar_banco()
    app = Flask(__name__)

    @app.template_filter('numero')
    def numero(valor):
        return 'Indefinido' if valor is None else f'{valor:.3f}'.replace('.', ',')

    @app.get('/')
    def pagina_inicial():
        with conectar() as db:
            indicadores = {t: db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                           for t in ('usuarios', 'conteudos', 'generos', 'visualizacoes')}
            medias = db.execute('SELECT AVG(tempo_plataforma_horas), AVG(tempo_assistindo_horas) FROM usuarios').fetchone()
        return render_template('index.html', indicadores=indicadores, medias=medias, analises=obter_analises())

    @app.get('/catalogo')
    def catalogo_global():
        with conectar() as db:
            itens = consultar_catalogo(db)
        return render_template('catalogo.html', itens=itens)

    @app.get('/analises')
    def pagina_analises():
        with conectar() as db:
            limites = (db.execute('SELECT COUNT(*) FROM conteudos').fetchone()[0],
                       db.execute('SELECT COUNT(*) FROM generos').fetchone()[0])
        return render_template('analises.html', analises=obter_analises(), limites=limites)

    @app.get('/regressao')
    def pagina_regressao():
        return redirect(url_for('pagina_analises', _anchor='regressao'))

    @app.get('/api/analises')
    def analises_api():
        return jsonify(obter_analises())

    @app.get('/usuarios/<int:usuario_id>')
    def perfil(usuario_id):
        analises = obter_analises()
        usuario = next((p for p in analises['observacoes'] if p['id'] == usuario_id), None)
        if usuario is None:
            abort(404)
        return render_template('perfil.html', usuario=usuario, analises=analises)

    @app.errorhandler(404)
    def nao_encontrado(erro):
        return render_template('404.html'), 404

    @app.get('/categorias')
    def categorias_mais_assistidas():
        with conectar() as db:
            categorias = [dict(r) for r in db.execute('''
                SELECT g.id, g.nome, COUNT(v.usuario_id) AS quantidade
                FROM generos g
                LEFT JOIN conteudos c ON c.genero_id = g.id
                LEFT JOIN visualizacoes v ON v.conteudo_id = c.id
                GROUP BY g.id, g.nome
                ORDER BY quantidade DESC, g.nome, g.id
            ''')]
        total = sum(c['quantidade'] for c in categorias)
        maior = max((c['quantidade'] for c in categorias), default=0)
        for categoria in categorias:
            categoria['percentual'] = 100 * categoria['quantidade'] / total if total else 0
            categoria['largura'] = 100 * categoria['quantidade'] / maior if maior else 0
        return render_template('categorias.html', categorias=categorias, total=total)

    @app.get('/api/usuarios')
    def usuarios():
        with conectar() as db:
            return jsonify([dict(r) for r in db.execute('SELECT id,nome FROM usuarios ORDER BY id')])

    @app.get('/api/conteudos')
    def conteudos():
        usuario_id = request.args.get('usuario_id', type=int)
        if usuario_id is None:
            return jsonify(erro='Informe usuario_id inteiro.'), 400
        with conectar() as db:
            if not db.execute('SELECT 1 FROM usuarios WHERE id=?', (usuario_id,)).fetchone():
                return jsonify(erro='Usuário não encontrado.'), 404
            return jsonify([{k: v for k, v in c.items() if k != 'quantidade_usuarios'}
                            for c in consultar_catalogo(db, usuario_id)])

    @app.get('/api/usuarios/<int:usuario_id>/recomendacoes')
    def recomendacoes(usuario_id):
        try:
            return jsonify(recomendar(usuario_id))
        except LookupError as erro:
            return jsonify(erro=str(erro)), 404

    @app.get('/api/clusters')
    def clusters():
        return jsonify(obter_clusters())

    @app.put('/api/usuarios/<int:usuario_id>/vistos/<int:conteudo_id>')
    def marcar_visto(usuario_id, conteudo_id):
        dados = request.get_json(silent=True)
        if not isinstance(dados, dict) or type(dados.get('visto')) is not bool:
            return jsonify(erro='Informe visto como true ou false.'), 400
        with conectar() as db:
            if not db.execute('SELECT 1 FROM usuarios WHERE id=?', (usuario_id,)).fetchone():
                return jsonify(erro='Usuário não encontrado.'), 404
            if not db.execute('SELECT 1 FROM conteudos WHERE id=?', (conteudo_id,)).fetchone():
                return jsonify(erro='Conteúdo não encontrado.'), 404
            if dados['visto']:
                db.execute('INSERT OR IGNORE INTO visualizacoes VALUES (?,?)', (usuario_id, conteudo_id))
            else:
                db.execute('DELETE FROM visualizacoes WHERE usuario_id=? AND conteudo_id=?', (usuario_id, conteudo_id))
        return jsonify(usuario_id=usuario_id, conteudo_id=conteudo_id, visto=dados['visto'])

    @app.get('/api/modelo')
    def modelo():
        return jsonify(obter_resumo_modelo())

    @app.post('/api/prever')
    def prever():
        dados = request.get_json(silent=True)
        try:
            if not isinstance(dados, dict) or any(isinstance(dados.get(v), bool) for v in VARIAVEIS):
                raise ValueError()
            horas, vistos, generos = [float(dados[v]) for v in VARIAVEIS]
            if not all(math.isfinite(n) for n in (horas, vistos, generos)):
                raise ValueError()
            if not (0 < horas <= 24 and vistos.is_integer() and generos.is_integer()):
                raise ValueError()
            with conectar() as db:
                max_vistos = db.execute('SELECT COUNT(*) FROM conteudos').fetchone()[0]
                max_generos = db.execute('SELECT COUNT(*) FROM generos').fetchone()[0]
            if not (0 <= vistos <= max_vistos and 0 <= generos <= min(vistos, max_generos)) or (vistos > 0 and generos == 0):
                raise ValueError()
        except (TypeError, ValueError, KeyError, OverflowError):
            return jsonify(erro='Informe horas entre 0 e 24 (maior que zero) e contagens inteiras coerentes com o catálogo.'), 400
        try:
            return jsonify(prever_engajamento(horas, vistos, generos))
        except ValueError as erro:
            return jsonify(erro=str(erro)), 422

    return app


app = criar_app()

if __name__ == '__main__':
    app.run(debug=True)
