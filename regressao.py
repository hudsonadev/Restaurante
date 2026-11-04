"""Regressões do tempo de preparo sobre a fotografia imutável dos itens originais.

- Regressão simples: Y = B0 + B1·X, com X = tempo dos pratos (soma dos tempos individuais).
  Calculada à mão, em Python puro (ajustar_simples), e conferida com numpy.polyfit.
- Regressão múltipla: tempo dos pratos, fila e categorias, resolvida com numpy.linalg.lstsq.
"""
import math
import numpy as np
from banco import conectar

VARIAVEIS = ['tempo_base_itens', 'pedidos_na_fila', 'quantidade_categorias']
ROTULOS = {'tempo_base_itens': 'tempo dos pratos', 'pedidos_na_fila': 'fila', 'quantidade_categorias': 'categorias'}


def br(valor, casas=2):
    return f'{valor:.{casas}f}'.replace('.', ',')


def _validar_simples(x, y):
    """Validação em Python puro: converte para listas de float e checa a amostra."""
    try:
        x = [float(v) for v in x]
        y = [float(v) for v in y]
    except (TypeError, ValueError):
        raise ValueError('As amostras devem conter apenas números.') from None
    if len(x) != len(y) or len(x) < 2:
        raise ValueError('São necessárias pelo menos duas observações.')
    if not all(math.isfinite(v) for v in x + y):
        raise ValueError('A amostra contém valores não finitos.')
    if all(v == x[0] for v in x):
        raise ValueError('O tempo dos pratos precisa variar para ajustar a reta.')
    return x, y


def ajustar_simples(x, y):
    """Mínimos quadrados MANUAL de Y = B0 + B1·X + E, sem nenhuma biblioteca.

    B1 = Σ(xi − x̄)(yi − ȳ) / Σ(xi − x̄)²;  B0 = ȳ − B1·x̄;  Ei = yi − (B0 + B1·xi).
    """
    x, y = _validar_simples(x, y)
    n = len(x)
    media_x = sum(x) / n
    media_y = sum(y) / n
    sxy = 0.0
    sxx = 0.0
    for xi, yi in zip(x, y):
        sxy += (xi - media_x) * (yi - media_y)
        sxx += (xi - media_x) ** 2
    b1 = sxy / sxx
    b0 = media_y - b1 * media_x
    sq_erros = 0.0
    sq_total = 0.0
    for xi, yi in zip(x, y):
        sq_erros += (yi - (b0 + b1 * xi)) ** 2
        sq_total += (yi - media_y) ** 2
    r2 = 1 - sq_erros / sq_total if sq_total > 0 else None
    return (b0, b1), r2


def comparar_polyfit(x, y):
    """Confere o ajuste manual contra numpy.polyfit(x, y, 1), que devolve [B1, B0]."""
    (b0, b1), r2 = ajustar_simples(x, y)
    xs, ys = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    p1, p0 = (float(v) for v in np.polyfit(xs, ys, 1))
    total = float(np.sum((ys - ys.mean()) ** 2))
    r2_polyfit = 1 - float(np.sum((ys - (p0 + p1 * xs)) ** 2)) / total if total > 0 else None
    return {'manual': {'intercepto': b0, 'coeficiente': b1, 'r_quadrado': r2},
            'polyfit': {'intercepto': p0, 'coeficiente': p1, 'r_quadrado': r2_polyfit},
            'diferenca_intercepto': abs(b0 - p0),
            'diferenca_coeficiente': abs(b1 - p1),
            'diferenca_r_quadrado': abs(r2 - r2_polyfit) if r2 is not None and r2_polyfit is not None else None,
            'diferenca_previsao_maxima': float(np.max(np.abs((b0 + b1 * xs) - (p0 + p1 * xs))))}


def carregar_observacoes():
    with conectar() as db:
        return [dict(r) for r in db.execute('''SELECT p.id, p.cliente, p.pedidos_na_fila,
            p.tempo_preparo_min AS tempo_preparo,
            COUNT(i.prato_id) AS quantidade_itens,
            COALESCE(SUM(c.tempo_prato_min), 0) AS tempo_base_itens,
            COUNT(DISTINCT c.categoria_id) AS quantidade_categorias
            FROM pedidos p LEFT JOIN itens_originais i ON i.pedido_id=p.id
            LEFT JOIN pratos c ON c.id=i.prato_id GROUP BY p.id ORDER BY p.id''')]


def resumo_simples(pontos):
    simples = {'disponivel': False, 'quantidade_registros': len(pontos), 'variavel': 'tempo_base_itens'}
    x = [p['tempo_base_itens'] for p in pontos]
    y = [p['tempo_preparo'] for p in pontos]
    try:
        comparacao = comparar_polyfit(x, y)
    except ValueError as erro:
        return {**simples, 'aviso': str(erro)}
    manual = comparacao['manual']
    b0, b1 = manual['intercepto'], manual['coeficiente']
    simples.update(disponivel=True, metodo='manual', intercepto=b0, coeficiente=b1, r_quadrado=manual['r_quadrado'],
                   intervalo=[float(min(x)), float(max(x))], comparacao_polyfit=comparacao,
                   formula=f'ŷ = {br(b0, 4)} {"+" if b1 >= 0 else "−"} {br(abs(b1), 4)} × tempo dos pratos')
    return simples


def ajustar_modelo(x, y):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 2 or x.shape[1] != 3 or len(x) != len(y) or len(y) < 4:
        raise ValueError('São necessárias pelo menos quatro observações com três variáveis.')
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('A amostra contém valores não finitos.')
    design = np.column_stack([np.ones(len(x)), x])
    coeficientes, _, posto, _ = np.linalg.lstsq(design, y, rcond=None)
    if posto < 4:
        raise ValueError('As variáveis não apresentam independência suficiente para estimar os coeficientes.')
    estimativas = design @ coeficientes
    total = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - float(np.sum((y - estimativas) ** 2)) / total if total > 0 else None
    return coeficientes, r2


def obter_resumo_modelo(pontos=None):
    pontos = carregar_observacoes() if pontos is None else pontos
    x = [[p[v] for v in VARIAVEIS] for p in pontos]
    y = [p['tempo_preparo'] for p in pontos]
    resumo = {'quantidade_registros': len(pontos), 'variaveis': VARIAVEIS,
              'disponivel': False, 'fonte': 'Fotografia fixa dos itens originais; dados sintéticos.'}
    try:
        coeficientes, r2 = ajustar_modelo(x, y)
    except ValueError as erro:
        return {**resumo, 'aviso': str(erro)}
    resumo.update(disponivel=True, intercepto=float(coeficientes[0]),
                  coeficientes=dict(zip(VARIAVEIS, map(float, coeficientes[1:]))), r_quadrado=r2,
                  intervalos={v: [float(min(col)), float(max(col))] for v, col in zip(VARIAVEIS, zip(*x))})
    resumo['formula'] = f'ŷ = {br(coeficientes[0], 4)}' + ''.join(
        f' {"+" if coef >= 0 else "−"} {br(abs(coef), 4)} × {ROTULOS[nome]}'
        for nome, coef in zip(VARIAVEIS, coeficientes[1:]))
    return resumo


def obter_analises():
    pontos = carregar_observacoes()
    simples, multipla = resumo_simples(pontos), obter_resumo_modelo(pontos)
    for p in pontos:
        p['previsao_simples'] = simples['intercepto'] + simples['coeficiente'] * p['tempo_base_itens'] if simples['disponivel'] else None
        p['previsao_multipla'] = multipla['intercepto'] + sum(multipla['coeficientes'][v] * p[v] for v in VARIAVEIS) if multipla['disponivel'] else None
        for nome in ('simples', 'multipla'):
            previsto = p[f'previsao_{nome}']
            p[f'residuo_{nome}'] = p['tempo_preparo'] - previsto if previsto is not None else None
        # JSON estrito: valores inválidos não viram NaN/Infinity na resposta.
        for chave, valor in p.items():
            if isinstance(valor, float) and not np.isfinite(valor):
                p[chave] = None
    for nome, modelo in [('simples', simples), ('multipla', multipla)]:
        modelo['erro_absoluto_medio'] = float(np.mean([abs(p[f'residuo_{nome}']) for p in pontos])) if modelo['disponivel'] else None
    return {'simples': simples, 'multipla': multipla, 'observacoes': pontos}


def prever_tempo(tempo_base_itens, pedidos_na_fila, quantidade_categorias):
    """Estimativa para um pedido novo. tempo_base_itens = soma dos tempos individuais dos pratos."""
    pontos = carregar_observacoes()
    simples, multipla = resumo_simples(pontos), obter_resumo_modelo(pontos)
    if not simples['disponivel'] and not multipla['disponivel']:
        raise ValueError(multipla['aviso'])
    entrada = dict(zip(VARIAVEIS, [tempo_base_itens, pedidos_na_fila, quantidade_categorias]))
    resultado = {'entrada': entrada, 'avisos': []}
    extrapola = False
    if simples['disponivel']:
        bruta = simples['intercepto'] + simples['coeficiente'] * tempo_base_itens
        polyfit = simples['comparacao_polyfit']['polyfit']
        via_polyfit = polyfit['intercepto'] + polyfit['coeficiente'] * tempo_base_itens
        resultado['simples'] = {'disponivel': True, 'previsao_minutos': max(0, bruta), 'previsao_bruta': bruta,
                                'previsao_polyfit': via_polyfit, 'diferenca_polyfit': abs(bruta - via_polyfit),
                                'calculo': f'{br(simples["intercepto"])} + {br(simples["coeficiente"])} × {br(tempo_base_itens, 1)} = {br(bruta, 1)} min'}
        extrapola |= not simples['intervalo'][0] <= tempo_base_itens <= simples['intervalo'][1]
    else:
        resultado['simples'] = {'disponivel': False, 'aviso': simples['aviso']}
    if multipla['disponivel']:
        coef = multipla['coeficientes']
        bruta = multipla['intercepto'] + sum(coef[v] * entrada[v] for v in VARIAVEIS)
        termos = ''.join(f' {"+" if coef[v] >= 0 else "−"} {br(abs(coef[v]))} × {br(entrada[v], 1) if v == "tempo_base_itens" else entrada[v]}'
                         for v in VARIAVEIS)
        resultado['multipla'] = {'disponivel': True, 'previsao_minutos': max(0, bruta), 'previsao_bruta': bruta,
                                 'calculo': f'{br(multipla["intercepto"])}{termos} = {br(bruta, 1)} min'}
        extrapola |= any(not multipla['intervalos'][v][0] <= entrada[v] <= multipla['intervalos'][v][1] for v in VARIAVEIS)
    else:
        resultado['multipla'] = {'disponivel': False, 'aviso': multipla['aviso']}
    if extrapola:
        resultado['avisos'].append('Pedido fora do intervalo observado nos dados: a estimativa é uma extrapolação.')
    if any(m.get('previsao_bruta', 0) < 0 for m in (resultado['simples'], resultado['multipla'])):
        resultado['avisos'].append('A estimativa linear ficou negativa; o valor exibido foi limitado a zero.')
    return resultado


if __name__ == '__main__':
    import sys
    from banco import inicializar_banco
    sys.stdout.reconfigure(encoding='utf-8')  # o console do Windows (cp1252) não imprime "ŷ"
    inicializar_banco()
    analises = obter_analises()
    print(analises['simples']['formula'], '| R²', analises['simples']['r_quadrado'])
    print(analises['multipla']['formula'], '| R²', analises['multipla']['r_quadrado'])
    print('Manual × numpy.polyfit:', analises['simples']['comparacao_polyfit'])
