"""Regressões do tempo de preparo sobre a fotografia imutável dos itens originais."""
import numpy as np
from banco import conectar

VARIAVEIS = ['quantidade_itens', 'pedidos_na_fila', 'quantidade_categorias']
ROTULOS = {'quantidade_itens': 'itens', 'pedidos_na_fila': 'fila', 'quantidade_categorias': 'categorias'}


def br(valor, casas=2):
    return f'{valor:.{casas}f}'.replace('.', ',')


def ajustar_simples(x, y):
    """Mínimos quadrados manual de Y = B0 + B1·X + E.

    B1 = Σ(xi − x̄)(yi − ȳ) / Σ(xi − x̄)²;  B0 = ȳ − B1·x̄;  Ei = yi − (B0 + B1·xi).
    """
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or len(x) < 2:
        raise ValueError('São necessárias pelo menos duas observações.')
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('A amostra contém valores não finitos.')
    if np.all(x == x[0]):
        raise ValueError('A quantidade de itens precisa variar para ajustar a reta.')
    n = len(x)
    media_x, media_y = sum(x) / n, sum(y) / n
    sxy = sum((xi - media_x) * (yi - media_y) for xi, yi in zip(x, y))
    sxx = sum((xi - media_x) ** 2 for xi in x)
    b1 = sxy / sxx
    b0 = media_y - b1 * media_x
    erros = [yi - (b0 + b1 * xi) for xi, yi in zip(x, y)]
    total = sum((yi - media_y) ** 2 for yi in y)
    r2 = 1 - sum(e ** 2 for e in erros) / total if total > 0 else None
    return np.array([b0, b1]), r2


def comparar_polyfit(x, y):
    """Confere o ajuste manual contra numpy.polyfit(x, y, 1), que devolve [B1, B0]."""
    (b0, b1), _ = ajustar_simples(x, y)
    p1, p0 = np.polyfit(np.asarray(x, dtype=float), np.asarray(y, dtype=float), 1)
    return {'manual': {'intercepto': float(b0), 'coeficiente': float(b1)},
            'polyfit': {'intercepto': float(p0), 'coeficiente': float(p1)},
            'diferenca_intercepto': abs(float(b0 - p0)),
            'diferenca_coeficiente': abs(float(b1 - p1))}


def carregar_observacoes():
    with conectar() as db:
        return [dict(r) for r in db.execute('''SELECT p.id, p.cliente, p.pedidos_na_fila,
            p.tempo_preparo_min AS tempo_preparo,
            COUNT(i.prato_id) AS quantidade_itens,
            COUNT(DISTINCT c.categoria_id) AS quantidade_categorias
            FROM pedidos p LEFT JOIN itens_originais i ON i.pedido_id=p.id
            LEFT JOIN pratos c ON c.id=i.prato_id GROUP BY p.id ORDER BY p.id''')]


def resumo_simples(pontos):
    simples = {'disponivel': False, 'quantidade_registros': len(pontos)}
    x = [p['quantidade_itens'] for p in pontos]
    y = [p['tempo_preparo'] for p in pontos]
    try:
        coef, r2 = ajustar_simples(x, y)
    except ValueError as erro:
        return {**simples, 'aviso': str(erro)}
    simples.update(disponivel=True, intercepto=float(coef[0]), coeficiente=float(coef[1]), r_quadrado=r2,
                   intervalo=[float(min(x)), float(max(x))], comparacao_polyfit=comparar_polyfit(x, y),
                   formula=f'ŷ = {br(coef[0], 4)} {"+" if coef[1] >= 0 else "−"} {br(abs(coef[1]), 4)} × itens')
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
        p['previsao_simples'] = simples['intercepto'] + simples['coeficiente'] * p['quantidade_itens'] if simples['disponivel'] else None
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


def prever_tempo(quantidade_itens, pedidos_na_fila, quantidade_categorias):
    pontos = carregar_observacoes()
    simples, multipla = resumo_simples(pontos), obter_resumo_modelo(pontos)
    if not simples['disponivel'] and not multipla['disponivel']:
        raise ValueError(multipla['aviso'])
    entrada = dict(zip(VARIAVEIS, [quantidade_itens, pedidos_na_fila, quantidade_categorias]))
    resultado = {'entrada': entrada, 'avisos': []}
    if simples['disponivel']:
        bruta = simples['intercepto'] + simples['coeficiente'] * quantidade_itens
        resultado['simples'] = {'disponivel': True, 'previsao_minutos': max(0, bruta), 'previsao_bruta': bruta,
                                'calculo': f'{br(simples["intercepto"])} + {br(simples["coeficiente"])} × {quantidade_itens} = {br(bruta, 1)} min'}
    else:
        resultado['simples'] = {'disponivel': False, 'aviso': simples['aviso']}
    if multipla['disponivel']:
        coef = multipla['coeficientes']
        bruta = multipla['intercepto'] + sum(coef[v] * entrada[v] for v in VARIAVEIS)
        termos = ''.join(f' {"+" if coef[v] >= 0 else "−"} {br(abs(coef[v]))} × {entrada[v]}' for v in VARIAVEIS)
        resultado['multipla'] = {'disponivel': True, 'previsao_minutos': max(0, bruta), 'previsao_bruta': bruta,
                                 'calculo': f'{br(multipla["intercepto"])}{termos} = {br(bruta, 1)} min'}
        if any(not multipla['intervalos'][v][0] <= entrada[v] <= multipla['intervalos'][v][1] for v in VARIAVEIS):
            resultado['avisos'].append('Pedido fora do intervalo observado nos dados: a estimativa é uma extrapolação.')
    else:
        resultado['multipla'] = {'disponivel': False, 'aviso': multipla['aviso']}
    if any(m.get('previsao_bruta', 0) < 0 for m in (resultado['simples'], resultado['multipla'])):
        resultado['avisos'].append('A estimativa linear ficou negativa; o valor exibido foi limitado a zero.')
    return resultado


if __name__ == '__main__':
    from banco import inicializar_banco
    inicializar_banco()
    analises = obter_analises()
    print(analises['simples']['formula'], '| R²', analises['simples']['r_quadrado'])
    print(analises['multipla']['formula'], '| R²', analises['multipla']['r_quadrado'])
    print('Manual × numpy.polyfit:', analises['simples']['comparacao_polyfit'])
