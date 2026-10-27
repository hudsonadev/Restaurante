"""Regressão múltipla sobre a fotografia imutável do histórico inicial."""
import numpy as np
from banco import conectar

VARIAVEIS = ['tempo_plataforma', 'quantidade_vistos', 'quantidade_generos']


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
