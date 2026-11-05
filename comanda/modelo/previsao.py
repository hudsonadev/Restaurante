"""O modelo sobre os dados do restaurante: treino com a fotografia imutável dos itens originais,
resumo para as páginas e a previsão de um pedido novo."""
import math
from comanda.db import conectar
from comanda.modelo import coeficientes as personalizados
from comanda.modelo.minimos_quadrados import comparar_numpy
from comanda.modelo.variaveis import EM_MINUTOS, NOMES_COEFICIENTES, ROTULOS, VARIAVEIS, aplicar, variaveis_do_pedido


def br(valor, casas=2):
    return f'{valor:.{casas}f}'.replace('.', ',')


def carregar_observacoes():
    with conectar() as db:
        return [dict(r) for r in db.execute('''SELECT p.id, p.cliente, p.pedidos_na_fila,
            p.tempo_preparo_min AS tempo_preparo,
            COUNT(i.prato_id) AS quantidade_itens,
            COALESCE(SUM(c.tempo_prato_min), 0) AS tempo_base_itens,
            COALESCE(MAX(c.tempo_prato_min), 0) AS tempo_maior_prato,
            COALESCE(SUM(c.tempo_prato_min) - MAX(c.tempo_prato_min), 0) AS tempo_demais_pratos,
            COUNT(DISTINCT c.categoria_id) AS quantidade_categorias
            FROM pedidos p LEFT JOIN itens_originais i ON i.pedido_id=p.id
            LEFT JOIN pratos c ON c.id=i.prato_id GROUP BY p.id ORDER BY p.id''')]


def _formula(coef):
    return f'ŷ = {br(coef["intercepto"], 4)}' + ''.join(
        f' {"+" if coef[v] >= 0 else "−"} {br(abs(coef[v]), 4)} × {ROTULOS[v]}' for v in VARIAVEIS)


def _r_quadrado(coef, x, y):
    previsto = [aplicar(coef, dict(zip(VARIAVEIS, linha))) for linha in x]
    media = sum(y) / len(y)
    total = sum((yi - media) ** 2 for yi in y)
    return 1 - sum((yi - pi) ** 2 for yi, pi in zip(y, previsto)) / total if total > 0 else None


def obter_resumo_modelo(pontos=None):
    pontos = carregar_observacoes() if pontos is None else pontos
    x = [[p[v] for v in VARIAVEIS] for p in pontos]
    y = [p['tempo_preparo'] for p in pontos]
    resumo = {'quantidade_registros': len(pontos), 'variaveis': VARIAVEIS, 'metodo': 'manual',
              'disponivel': False, 'fonte': 'Fotografia fixa dos itens originais; dados sintéticos.'}
    try:
        comparacao = comparar_numpy(x, y, NOMES_COEFICIENTES)
    except ValueError as erro:
        return {**resumo, 'aviso': str(erro)}
    calculados = comparacao['manual']['coeficientes']
    salvos = personalizados.ler()
    # Com β personalizados completos, eles passam a valer em todo o sistema; senão, valem os calculados.
    usa_personalizados = set(salvos) == set(NOMES_COEFICIENTES)
    em_uso = salvos if usa_personalizados else calculados
    resumo.update(disponivel=True, personalizado=usa_personalizados,
                  metodo='personalizado' if usa_personalizados else 'manual',
                  intercepto=em_uso['intercepto'], coeficientes={v: em_uso[v] for v in VARIAVEIS},
                  r_quadrado=_r_quadrado(em_uso, x, y) if usa_personalizados else comparacao['manual']['r_quadrado'],
                  coeficientes_calculados=dict(calculados), r_quadrado_calculado=comparacao['manual']['r_quadrado'],
                  comparacao_numpy=comparacao, formula=_formula(em_uso), formula_calculada=_formula(calculados),
                  intervalos={v: [float(min(col)), float(max(col))] for v, col in zip(VARIAVEIS, zip(*x))})
    return resumo


def obter_analises():
    pontos = carregar_observacoes()
    modelo = obter_resumo_modelo(pontos)
    em_uso = {'intercepto': modelo.get('intercepto'), **modelo.get('coeficientes', {})}
    for p in pontos:
        previsto = aplicar(em_uso, p) if modelo['disponivel'] else None
        p['previsao_multipla'] = previsto
        p['residuo_multipla'] = p['tempo_preparo'] - previsto if previsto is not None else None
        # JSON estrito: valores inválidos não viram NaN/Infinity na resposta.
        for chave, valor in p.items():
            if isinstance(valor, float) and not math.isfinite(valor):
                p[chave] = None
    modelo['erro_absoluto_medio'] = (sum(abs(p['residuo_multipla']) for p in pontos) / len(pontos)
                                     if modelo['disponivel'] else None)
    return {'multipla': modelo, 'observacoes': pontos}


def prever_tempo(tempos_pratos, pedidos_na_fila, quantidade_categorias):
    """Estimativa para um pedido novo, a partir dos tempos individuais dos pratos escolhidos."""
    modelo = obter_resumo_modelo()
    if not modelo['disponivel']:
        raise ValueError(modelo['aviso'])
    entrada = variaveis_do_pedido(tempos_pratos, pedidos_na_fila, quantidade_categorias)
    coef = modelo['coeficientes']
    bruta = aplicar({'intercepto': modelo['intercepto'], **coef}, entrada)
    via_numpy = aplicar(modelo['comparacao_numpy']['numpy']['coeficientes'], entrada)
    com_calculados = aplicar(modelo['coeficientes_calculados'], entrada)
    termos = ''.join(f' {"+" if coef[v] >= 0 else "−"} {br(abs(coef[v]))} × {br(entrada[v], 1) if v in EM_MINUTOS else entrada[v]}'
                     for v in VARIAVEIS)
    avisos = []
    if any(not modelo['intervalos'][v][0] <= entrada[v] <= modelo['intervalos'][v][1] for v in VARIAVEIS):
        avisos.append('Pedido fora do intervalo observado nos dados: a estimativa é uma extrapolação.')
    if bruta < 0:
        avisos.append('A estimativa linear ficou negativa; o valor exibido foi limitado a zero.')
    return {'entrada': entrada, 'tempo_base_itens': sum(tempos_pratos), 'avisos': avisos,
            'multipla': {'disponivel': True, 'personalizado': modelo['personalizado'],
                         'previsao_minutos': max(0, bruta), 'previsao_bruta': bruta,
                         # Conferência: com β personalizados, compara-se o cálculo manual (β calculados) ao NumPy.
                         'previsao_calculada': com_calculados,
                         'previsao_numpy': via_numpy, 'diferenca_numpy': abs(com_calculados - via_numpy),
                         'calculo': f'{br(modelo["intercepto"])}{termos} = {br(bruta, 1)} min'}}
