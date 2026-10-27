"""Carga transacional dos dados fixos; histórico editável nunca é reposto."""
import csv
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DIRETORIO_DADOS = BASE_DIR / 'dados'
CAMINHO_BANCO = BASE_DIR / 'streaming.db'
CAMINHO_DATASET = DIRETORIO_DADOS / 'dataset_streaming.csv'


def ler_csv(nome):
    with (DIRETORIO_DADOS / nome).open(encoding='utf-8', newline='') as arquivo:
        return list(csv.DictReader(arquivo))


class Conexao(sqlite3.Connection):
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


def inicializar_banco():
    with conectar() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY, nome TEXT NOT NULL,
                tempo_plataforma_horas REAL NOT NULL,
                tempo_assistindo_horas REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS generos (id INTEGER PRIMARY KEY, nome TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS conteudos (
                id INTEGER PRIMARY KEY, titulo TEXT NOT NULL,
                genero_id INTEGER NOT NULL REFERENCES generos(id));
            CREATE TABLE IF NOT EXISTS visualizacoes (
                usuario_id INTEGER REFERENCES usuarios(id),
                conteudo_id INTEGER REFERENCES conteudos(id),
                PRIMARY KEY (usuario_id, conteudo_id));
            CREATE TABLE IF NOT EXISTS historico_inicial (
                usuario_id INTEGER REFERENCES usuarios(id),
                conteudo_id INTEGER REFERENCES conteudos(id),
                PRIMARY KEY (usuario_id, conteudo_id));
            CREATE TABLE IF NOT EXISTS migracoes (versao INTEGER PRIMARY KEY);
        ''')
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM migracoes WHERE versao=1').fetchone():
            db.executemany('INSERT INTO usuarios VALUES (?,?,?,?)', [
                (int(r['usuario_id']), r['nome'], float(r['tempo_plataforma_horas']),
                 float(r['tempo_assistindo_horas'])) for r in ler_csv('dataset_streaming.csv')])
            db.executemany('INSERT INTO generos VALUES (?,?)', [
                (int(r['genero_id']), r['nome']) for r in ler_csv('generos.csv')])
            db.executemany('INSERT INTO conteudos VALUES (?,?,?)', [
                (int(r['conteudo_id']), r['titulo'], int(r['genero_id']))
                for r in ler_csv('conteudos.csv')])
            historico = [(int(r['usuario_id']), int(r['conteudo_id']))
                         for r in ler_csv('historico_inicial.csv')]
            db.executemany('INSERT INTO historico_inicial VALUES (?,?)', historico)
            db.executemany('INSERT INTO visualizacoes VALUES (?,?)', historico)
            db.execute('INSERT INTO migracoes VALUES (1)')
        return db.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0]


criar_banco = inicializar_banco
carregar_dataset = inicializar_banco

if __name__ == '__main__':
    print(f'{inicializar_banco()} usuários disponíveis. Histórico preservado.')
