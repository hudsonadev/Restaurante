"""Validação das entradas da API: tudo que chega do usuário passa por aqui antes de tocar no modelo."""
import math
from comanda.db import conectar
from comanda.modelo import NOMES_COEFICIENTES

LIMITE_FILA = 50
LIMITE_COEFICIENTE = 1000  # |β| acima disso é quase certamente erro de digitação
LIMITE_SIMULACAO = 50


class EntradaInvalida(Exception):
    """Entrada rejeitada; a mensagem vai para o usuário (HTTP 400)."""


def ler_inteiro(valor, minimo, maximo):
    if isinstance(valor, bool):
        raise ValueError()
    numero = float(valor)
    if not (math.isfinite(numero) and numero.is_integer() and minimo <= numero <= maximo):
        raise ValueError()
    return int(numero)


def ler_pedido(dados):
    """Valida {"pratos": [ids], "pedidos_na_fila": n} e devolve (ids, fila, tempos, categorias)."""
    try:
        if not isinstance(dados, dict) or not isinstance(dados.get('pratos'), list) or not dados['pratos']:
            raise ValueError()
        fila = ler_inteiro(dados.get('pedidos_na_fila'), 0, LIMITE_FILA)
        ids = [ler_inteiro(p, 1, 10 ** 9) for p in dados['pratos']]
        with conectar() as db:
            total = db.execute('SELECT COUNT(*) FROM pratos').fetchone()[0]
            if len(ids) > total or len(set(ids)) != len(ids):
                raise ValueError()
            encontrados = db.execute(f'SELECT categoria_id, tempo_prato_min FROM pratos WHERE id IN ({",".join("?" * len(ids))})',
                                     ids).fetchall()
        if len(encontrados) != len(ids):
            raise ValueError()
    except (TypeError, ValueError, OverflowError):
        raise EntradaInvalida(f'Escolha ao menos um prato do cardápio, sem repetir, e informe a fila como inteiro entre 0 e {LIMITE_FILA}.') from None
    return ids, fila, [r['tempo_prato_min'] for r in encontrados], len({r['categoria_id'] for r in encontrados})


def ler_coeficientes(dados):
    """Valida os cinco β personalizados e devolve {nome: float}."""
    try:
        if not isinstance(dados, dict) or set(dados) != set(NOMES_COEFICIENTES):
            raise ValueError()
        valores = {}
        for nome in NOMES_COEFICIENTES:
            if isinstance(dados[nome], bool):
                raise ValueError()
            valores[nome] = float(dados[nome])
            if not (math.isfinite(valores[nome]) and abs(valores[nome]) <= LIMITE_COEFICIENTE):
                raise ValueError()
    except (TypeError, ValueError, OverflowError):
        raise EntradaInvalida(f'Informe os cinco coeficientes ({", ".join(NOMES_COEFICIENTES)}) como números '
                              f'entre −{LIMITE_COEFICIENTE} e {LIMITE_COEFICIENTE}.') from None
    return valores


def ler_quantidade_simulada(dados):
    try:
        return ler_inteiro(dados.get('quantidade', 10), 1, LIMITE_SIMULACAO)
    except (TypeError, ValueError, OverflowError):
        raise EntradaInvalida(f'Informe quantidade como inteiro entre 1 e {LIMITE_SIMULACAO}.') from None


def ler_inclusao(dados):
    if not isinstance(dados, dict) or type(dados.get('incluido')) is not bool:
        raise EntradaInvalida('Informe incluido como true ou false.')
    return dados['incluido']
