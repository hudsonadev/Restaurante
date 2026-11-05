"""Comanda: previsão do tempo de preparo de pedidos por regressão linear múltipla.

- db, migracoes: SQLite e esquema versionado.
- cozinha, dados: a regra sintética da cozinha e a geração dos CSVs de dados/.
- modelo: a regressão (cálculo manual × NumPy), β personalizados e previsões.
- acompanhamento: pedidos novos enviados à Cozinha (previsão × realidade).
- recomendacao: sugestões de pratos e agrupamento de categorias.
- web: páginas e API Flask.
"""
from comanda.db import RAIZ
from comanda.migracoes import inicializar_banco


def criar_app():
    from flask import Flask
    from comanda.web import api, formatacao, paginas

    inicializar_banco()
    # templates/ e static/ ficam na raiz do projeto.
    app = Flask(__name__, root_path=str(RAIZ))
    formatacao.registrar(app)
    app.register_blueprint(paginas.bp)
    app.register_blueprint(api.bp)
    return app
