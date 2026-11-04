"""Carga transacional dos dados fixos; itens editáveis nunca são repostos."""
import csv
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DIRETORIO_DADOS = BASE_DIR / 'dados'
CAMINHO_BANCO = BASE_DIR / 'restaurante.db'


def ler_csv(nome):
    with (DIRETORIO_DADOS / nome).open(encoding='utf-8-sig', newline='') as arquivo:
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
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY, cliente TEXT NOT NULL,
                pedidos_na_fila INTEGER NOT NULL,
                tempo_preparo_min REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY, nome TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pratos (
                id INTEGER PRIMARY KEY, nome TEXT NOT NULL,
                categoria_id INTEGER NOT NULL REFERENCES categorias(id));
            CREATE TABLE IF NOT EXISTS itens_pedido (
                pedido_id INTEGER REFERENCES pedidos(id),
                prato_id INTEGER REFERENCES pratos(id),
                PRIMARY KEY (pedido_id, prato_id));
            CREATE TABLE IF NOT EXISTS itens_originais (
                pedido_id INTEGER REFERENCES pedidos(id),
                prato_id INTEGER REFERENCES pratos(id),
                PRIMARY KEY (pedido_id, prato_id));
            CREATE TABLE IF NOT EXISTS migracoes (versao INTEGER PRIMARY KEY);
        ''')
        db.execute('BEGIN IMMEDIATE')
        if not db.execute('SELECT 1 FROM migracoes WHERE versao=1').fetchone():
            db.executemany('INSERT INTO pedidos VALUES (?,?,?,?)', [
                (int(r['pedido_id']), r['cliente'], int(r['pedidos_na_fila']),
                 float(r['tempo_preparo_min'])) for r in ler_csv('pedidos.csv')])
            db.executemany('INSERT INTO categorias VALUES (?,?)', [
                (int(r['categoria_id']), r['nome']) for r in ler_csv('categorias.csv')])
            db.executemany('INSERT INTO pratos VALUES (?,?,?)', [
                (int(r['prato_id']), r['nome'], int(r['categoria_id'])) for r in ler_csv('pratos.csv')])
            itens = [(int(r['pedido_id']), int(r['prato_id'])) for r in ler_csv('itens_pedido.csv')]
            db.executemany('INSERT INTO itens_originais VALUES (?,?)', itens)
            db.executemany('INSERT INTO itens_pedido VALUES (?,?)', itens)
            db.execute('INSERT INTO migracoes VALUES (1)')
        if not db.execute('SELECT 1 FROM migracoes WHERE versao=2').fetchone():
            # Tempo individual de cada prato e tempo real dos pedidos gerado a partir dele.
            # Os itens originais não mudam; itens_pedido (editável) não é tocada.
            colunas = {r['name'] for r in db.execute('PRAGMA table_info(pratos)')}
            if 'tempo_prato_min' not in colunas:
                db.execute('ALTER TABLE pratos ADD COLUMN tempo_prato_min REAL NOT NULL DEFAULT 0')
            pratos = [(float(r['tempo_prato_min']), int(r['prato_id'])) for r in ler_csv('pratos.csv')]
            if {r[1] for r in pratos} != {r[0] for r in db.execute('SELECT id FROM pratos')}:
                raise ValueError('A migração dos tempos exige os mesmos IDs de pratos.')
            originais = {tuple(r) for r in db.execute('SELECT pedido_id, prato_id FROM itens_originais')}
            if originais and originais != {(int(r['pedido_id']), int(r['prato_id'])) for r in ler_csv('itens_pedido.csv')}:
                raise ValueError('Os itens originais diferem dos CSVs: os tempos novos não corresponderiam a eles.')
            db.executemany('UPDATE pratos SET tempo_prato_min=? WHERE id=?', pratos)
            db.executemany('UPDATE pedidos SET tempo_preparo_min=? WHERE id=?', [
                (float(r['tempo_preparo_min']), int(r['pedido_id'])) for r in ler_csv('pedidos.csv')])
            db.execute('INSERT INTO migracoes VALUES (2)')
        return db.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0]


if __name__ == '__main__':
    print(f'{inicializar_banco()} pedidos disponíveis. Itens editados preservados.')
