"""Esquema do banco e migrações versionadas. Itens editados pela interface nunca são repostos."""
from comanda import db as banco
from comanda.db import conectar, ler_csv

ESQUEMA = '''
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
    -- β definidos pelo usuário; vazia = o sistema usa os β calculados pelos mínimos quadrados.
    CREATE TABLE IF NOT EXISTS coeficientes_personalizados (
        nome TEXT PRIMARY KEY, valor REAL NOT NULL);
    -- Pedidos novos enviados à cozinha: previsão gravada na criação, tempo real ao marcar "Pronto".
    -- Não entram no treino do modelo (servem de teste independente).
    CREATE TABLE IF NOT EXISTS pedidos_acompanhados (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        criado_em TEXT NOT NULL, pronto_em TEXT,
        pedidos_na_fila INTEGER NOT NULL, quantidade_itens INTEGER NOT NULL,
        quantidade_categorias INTEGER NOT NULL,
        tempo_maior_prato REAL NOT NULL, tempo_demais_pratos REAL NOT NULL,
        previsao_min REAL NOT NULL, personalizado INTEGER NOT NULL,
        tempo_real_min REAL, origem_tempo TEXT,
        tempo_sorteado_min REAL);  -- modo simulado: quanto a cozinha vai levar (sorteado no envio)
    CREATE TABLE IF NOT EXISTS pedidos_acompanhados_itens (
        acompanhado_id INTEGER REFERENCES pedidos_acompanhados(id),
        prato_id INTEGER REFERENCES pratos(id),
        PRIMARY KEY (acompanhado_id, prato_id));
'''

# Colunas acrescentadas a pedidos_acompanhados depois que a tabela já existia em alguns bancos.
COLUNAS_ACOMPANHADOS = [('tempo_real_min', 'REAL'), ('origem_tempo', 'TEXT'), ('tempo_sorteado_min', 'REAL')]


def _colunas(db, tabela):
    return {r['name'] for r in db.execute(f'PRAGMA table_info({tabela})')}


def _itens_dos_csvs():
    return {(int(r['pedido_id']), int(r['prato_id'])) for r in ler_csv('itens_pedido.csv')}


def _exigir_itens_originais_dos_csvs(db):
    """Os tempos reais dos CSVs só valem para os mesmos itens originais."""
    originais = {tuple(r) for r in db.execute('SELECT pedido_id, prato_id FROM itens_originais')}
    if originais and originais != _itens_dos_csvs():
        raise ValueError('Os itens originais diferem dos CSVs: os tempos novos não corresponderiam a eles.')


def _atualizar_tempos_reais(db):
    db.executemany('UPDATE pedidos SET tempo_preparo_min=? WHERE id=?', [
        (float(r['tempo_preparo_min']), int(r['pedido_id'])) for r in ler_csv('pedidos.csv')])


def _v1_carga_inicial(db):
    db.executemany('INSERT INTO pedidos VALUES (?,?,?,?)', [
        (int(r['pedido_id']), r['cliente'], int(r['pedidos_na_fila']), float(r['tempo_preparo_min']))
        for r in ler_csv('pedidos.csv')])
    db.executemany('INSERT INTO categorias VALUES (?,?)', [
        (int(r['categoria_id']), r['nome']) for r in ler_csv('categorias.csv')])
    db.executemany('INSERT INTO pratos VALUES (?,?,?)', [
        (int(r['prato_id']), r['nome'], int(r['categoria_id'])) for r in ler_csv('pratos.csv')])
    itens = [(int(r['pedido_id']), int(r['prato_id'])) for r in ler_csv('itens_pedido.csv')]
    db.executemany('INSERT INTO itens_originais VALUES (?,?)', itens)
    db.executemany('INSERT INTO itens_pedido VALUES (?,?)', itens)


def _v2_tempo_dos_pratos(db):
    """Tempo individual de cada prato e tempo real dos pedidos gerado a partir dele."""
    if 'tempo_prato_min' not in _colunas(db, 'pratos'):
        db.execute('ALTER TABLE pratos ADD COLUMN tempo_prato_min REAL NOT NULL DEFAULT 0')
    pratos = [(float(r['tempo_prato_min']), int(r['prato_id'])) for r in ler_csv('pratos.csv')]
    if {r[1] for r in pratos} != {r[0] for r in db.execute('SELECT id FROM pratos')}:
        raise ValueError('A migração dos tempos exige os mesmos IDs de pratos.')
    _exigir_itens_originais_dos_csvs(db)
    db.executemany('UPDATE pratos SET tempo_prato_min=? WHERE id=?', pratos)
    _atualizar_tempos_reais(db)


def _v3_ruido_calibrado(db):
    """Tempos reais regerados com ruído calibrado (comanda.cozinha.DESVIO_RUIDO)."""
    _exigir_itens_originais_dos_csvs(db)
    _atualizar_tempos_reais(db)


MIGRACOES = [(1, _v1_carga_inicial), (2, _v2_tempo_dos_pratos), (3, _v3_ruido_calibrado)]


def inicializar_banco():
    """Cria o esquema, aplica as migrações pendentes e devolve a quantidade de pedidos."""
    with conectar() as db:
        db.executescript(ESQUEMA)
        existentes = _colunas(db, 'pedidos_acompanhados')
        for coluna, tipo in COLUNAS_ACOMPANHADOS:
            if coluna not in existentes:
                db.execute(f'ALTER TABLE pedidos_acompanhados ADD COLUMN {coluna} {tipo}')
        db.execute('BEGIN IMMEDIATE')
        # Pedidos concluídos antes dessas colunas: o tempo real é o do relógio (envio → clique em "Pronto").
        db.execute('''UPDATE pedidos_acompanhados
            SET tempo_real_min = ROUND((julianday(pronto_em) - julianday(criado_em)) * 1440, 1), origem_tempo = 'relogio'
            WHERE pronto_em IS NOT NULL AND tempo_real_min IS NULL''')
        for versao, aplicar in MIGRACOES:
            if not db.execute('SELECT 1 FROM migracoes WHERE versao=?', (versao,)).fetchone():
                aplicar(db)
                db.execute('INSERT INTO migracoes VALUES (?)', (versao,))
        return db.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0]


TABELAS = ['pedidos', 'pratos', 'categorias', 'itens_pedido', 'coeficientes_personalizados', 'pedidos_acompanhados']


def contar(tabelas=TABELAS):
    with conectar() as db:
        return {t: db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in tabelas}


def resetar_banco():
    """Apaga o banco e recria a partir dos CSVs (perde itens editados, β personalizados e pedidos da Cozinha).
    Devolve as contagens do banco novo."""
    caminho = banco.CAMINHO_BANCO
    try:
        caminho.unlink(missing_ok=True)
    except PermissionError:
        raise RuntimeError(f'{caminho.name} está em uso. Pare o servidor (Ctrl + C) e rode de novo.') from None
    inicializar_banco()
    return contar()
