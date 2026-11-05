"""β definidos pelo usuário: quando estão completos, valem em todo o sistema no lugar dos calculados."""
from comanda.db import conectar
from comanda.modelo.variaveis import NOMES_COEFICIENTES


def ler():
    """β definidos pelo usuário ({nome: valor}); vazio quando o modelo usa os β calculados."""
    with conectar() as db:
        return {nome: valor for nome, valor in db.execute('SELECT nome, valor FROM coeficientes_personalizados')}


def salvar(valores):
    """Grava os cinco β personalizados de uma vez (substitui os anteriores)."""
    with conectar() as db:
        db.execute('DELETE FROM coeficientes_personalizados')
        db.executemany('INSERT INTO coeficientes_personalizados VALUES (?, ?)', [(n, float(valores[n])) for n in NOMES_COEFICIENTES])


def limpar():
    with conectar() as db:
        db.execute('DELETE FROM coeficientes_personalizados')
