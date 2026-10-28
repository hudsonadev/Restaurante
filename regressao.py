"""Regressão múltipla sobre a fotografia imutável do histórico inicial."""
import numpy as np
from banco import conectar

VARIAVEIS = ['tempo_plataforma', 'quantidade_vistos', 'quantidade_generos']


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
        raise ValueError('As horas na plataforma precisam variar para ajustar a reta.')
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


def obter_analises():
    with conectar() as db:
        pontos = [dict(r) for r in db.execute('''SELECT u.id, u.nome,
            u.tempo_plataforma_horas AS tempo_plataforma,
            u.tempo_assistindo_horas AS tempo_assistindo,
            COUNT(h.conteudo_id) AS quantidade_vistos,
            COUNT(DISTINCT c.genero_id) AS quantidade_generos
            FROM usuarios u LEFT JOIN historico_inicial h ON h.usuario_id=u.id
            LEFT JOIN conteudos c ON c.id=h.conteudo_id GROUP BY u.id ORDER BY u.id''')]
    simples = {'disponivel': False, 'quantidade_registros': len(pontos)}
    try:
        coef, r2 = ajustar_simples([p['tempo_plataforma'] for p in pontos],
                                  [p['tempo_assistindo'] for p in pontos])
        simples.update(disponivel=True, intercepto=float(coef[0]), coeficiente=float(coef[1]),
                       r_quadrado=r2, formula=f'ŷ = {coef[0]:.4f} {coef[1]:+.4f} × horas na plataforma')
    except ValueError as erro:
        simples['aviso'] = str(erro)
    multipla = obter_resumo_modelo()
    for p in pontos:
        p['previsao_simples'] = simples['intercepto'] + simples['coeficiente'] * p['tempo_plataforma'] if simples['disponivel'] else None
        p['previsao_multipla'] = multipla['intercepto'] + sum(multipla['coeficientes'][v] * p[v] for v in VARIAVEIS) if multipla['disponivel'] else None
        for nome in ('simples', 'multipla'):
            previsto = p[f'previsao_{nome}']
            p[f'residuo_{nome}'] = p['tempo_assistindo'] - previsto if previsto is not None else None
        # JSON estrito: valores inválidos não viram NaN/Infinity na resposta.
        for chave, valor in p.items():
            if isinstance(valor, float) and not np.isfinite(valor):
                p[chave] = None
    for nome, modelo in [('simples', simples), ('multipla', multipla)]:
        modelo['erro_absoluto_medio'] = float(np.mean([abs(p[f'residuo_{nome}']) for p in pontos])) if modelo['disponivel'] else None
    return {'simples': simples, 'multipla': multipla, 'observacoes': pontos}


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


def obter_resumo_modelo(incluir_dados=False):
    with conectar() as db:
        linhas = db.execute('''SELECT u.tempo_plataforma_horas,
            COUNT(h.conteudo_id), COUNT(DISTINCT c.genero_id), u.tempo_assistindo_horas
            FROM usuarios u LEFT JOIN historico_inicial h ON h.usuario_id=u.id
            LEFT JOIN conteudos c ON c.id=h.conteudo_id GROUP BY u.id ORDER BY u.id''').fetchall()
    x = [list(r)[:3] for r in linhas]
    y = [r[3] for r in linhas]
    resumo = {'quantidade_registros': len(linhas), 'variaveis': VARIAVEIS,
              'disponivel': False, 'fonte': 'Fotografia fixa do histórico inicial; dados sintéticos.'}
    try:
        coeficientes, r2 = ajustar_modelo(x, y)
    except ValueError as erro:
        return {**resumo, 'aviso': str(erro)}
    resumo.update(disponivel=True, intercepto=float(coeficientes[0]),
                  coeficientes=dict(zip(VARIAVEIS, map(float, coeficientes[1:]))), r_quadrado=r2,
                  intervalos={v: [float(min(col)), float(max(col))] for v, col in zip(VARIAVEIS, zip(*x))})
    resumo['formula'] = 'ŷ = ' + f'{coeficientes[0]:.4f}' + ''.join(
        f' {coef:+.4f} × {nome}' for nome, coef in zip(VARIAVEIS, coeficientes[1:]))
    if incluir_dados:
        resumo['pontos'] = [dict(zip(VARIAVEIS + ['tempo_assistindo'], list(r))) for r in linhas]
    return resumo


def prever_engajamento(tempo_plataforma, quantidade_vistos, quantidade_generos):
    resumo = obter_resumo_modelo()
    if not resumo['disponivel']:
        raise ValueError(resumo['aviso'])
    valores = [tempo_plataforma, quantidade_vistos, quantidade_generos]
    previsao = resumo['intercepto'] + sum(resumo['coeficientes'][v] * n for v, n in zip(VARIAVEIS, valores))
    avisos = []
    if any(not resumo['intervalos'][v][0] <= n <= resumo['intervalos'][v][1] for v, n in zip(VARIAVEIS, valores)):
        avisos.append('Entrada fora do intervalo observado: a previsão é uma extrapolação.')
    if previsao < 0 or previsao > tempo_plataforma:
        avisos.append('A estimativa linear ficou fora do intervalo físico; a exibição foi limitada entre zero e as horas na plataforma.')
    return {'previsao_horas': max(0, min(tempo_plataforma, previsao)),
            'previsao_bruta': previsao, 'formula': resumo['formula'], 'avisos': avisos}


if __name__ == '__main__':
    from banco import inicializar_banco
    inicializar_banco()
    print(obter_resumo_modelo())
