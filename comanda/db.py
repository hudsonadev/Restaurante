"""Conexão com o SQLite e leitura dos CSVs de dados/."""
import csv
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIRETORIO_DADOS = RAIZ / 'dados'
CAMINHO_BANCO = RAIZ / 'restaurante.db'


def ler_csv(nome):
    with (DIRETORIO_DADOS / nome).open(encoding='utf-8-sig', newline='') as arquivo:
        return list(csv.DictReader(arquivo))


class Conexao(sqlite3.Connection):
    """Fecha a conexão ao sair do `with` (o sqlite3 padrão só faz commit/rollback)."""
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def conectar():
    conexao = sqlite3.connect(CAMINHO_BANCO, factory=Conexao)
    conexao.row_factory = sqlite3.Row
    conexao.execute('PRAGMA foreign_keys = ON')
    return conexao
