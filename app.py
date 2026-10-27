import math
from flask import Flask, jsonify, render_template, request
from banco import conectar, inicializar_banco
from recomendacao import obter_clusters, recomendar
from regressao import obter_resumo_modelo, prever_engajamento, VARIAVEIS


def criar_app():
    inicializar_banco()
    app = Flask(__name__)

    @app.get('/')
    def pagina_inicial():
        return render_template('index.html')

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
            linhas = db.execute('''SELECT c.*, g.nome AS genero,
                EXISTS(SELECT 1 FROM visualizacoes v WHERE v.usuario_id=? AND v.conteudo_id=c.id) AS visto
                FROM conteudos c JOIN generos g ON g.id=c.genero_id ORDER BY c.id''', (usuario_id,))
            return jsonify([{**dict(r), 'visto': bool(r['visto'])} for r in linhas])

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
