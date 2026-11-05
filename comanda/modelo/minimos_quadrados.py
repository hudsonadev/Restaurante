"""Mínimos quadrados da regressão linear múltipla, sem dependência do banco.

- ajustar_modelo_manual: cálculo À MÃO, em Python puro (equações normais + eliminação de Gauss).
- ajustar_modelo: o mesmo ajuste pelo NumPy (numpy.linalg.lstsq, decomposição SVD), usado como conferência.
"""
import math
import numpy as np

MENSAGEM_DEPENDENCIA = 'As variáveis não apresentam independência suficiente para estimar os coeficientes.'


def _validar(x, y):
    """Validação em Python puro: listas de float, mesmo número de variáveis por linha, valores finitos."""
    try:
        x = [[float(v) for v in linha] for linha in x]
        y = [float(v) for v in y]
    except (TypeError, ValueError):
        raise ValueError('As amostras devem conter apenas números.') from None
    k = len(x[0]) if x else 0
    if k == 0 or len(x) != len(y) or len(y) <= k or any(len(linha) != k for linha in x):
        raise ValueError('São necessárias mais observações que variáveis, com as mesmas variáveis em todas.')
    if not all(math.isfinite(v) for linha in x for v in linha) or not all(math.isfinite(v) for v in y):
        raise ValueError('A amostra contém valores não finitos.')
    return x, y


def _resolver_gauss(a, b):
    """Resolve A·β = b por eliminação de Gauss com pivoteamento parcial (Python puro)."""
    n = len(b)
    m = [linha[:] + [b[i]] for i, linha in enumerate(a)]       # matriz aumentada [A | b]
    escala = max(abs(v) for linha in a for v in linha) or 1.0
    for coluna in range(n):
        # Pivoteamento: traz para cima a linha com o maior valor absoluto na coluna.
        pivo = max(range(coluna, n), key=lambda i: abs(m[i][coluna]))
        if abs(m[pivo][coluna]) <= 1e-12 * escala:
            raise ValueError(MENSAGEM_DEPENDENCIA)
        m[coluna], m[pivo] = m[pivo], m[coluna]
        for i in range(coluna + 1, n):                           # zera abaixo do pivô
            fator = m[i][coluna] / m[coluna][coluna]
            for j in range(coluna, n + 1):
                m[i][j] -= fator * m[coluna][j]
    beta = [0.0] * n
    for i in range(n - 1, -1, -1):                                # substituição de trás para frente
        beta[i] = (m[i][n] - sum(m[i][j] * beta[j] for j in range(i + 1, n))) / m[i][i]
    return beta


def ajustar_modelo_manual(x, y):
    """Mínimos quadrados MANUAL, sem nenhuma biblioteca.

    Com a matriz X = [1, x1, …, xk], os coeficientes que minimizam ΣE² resolvem as
    equações normais  (XᵀX)·β = Xᵀy.
    """
    x, y = _validar(x, y)
    linhas = [[1.0] + linha for linha in x]                      # coluna de 1 = intercepto
    k = len(linhas[0])
    xtx = [[sum(l[i] * l[j] for l in linhas) for j in range(k)] for i in range(k)]
    xty = [sum(l[i] * yi for l, yi in zip(linhas, y)) for i in range(k)]
    beta = _resolver_gauss(xtx, xty)
    media_y = sum(y) / len(y)
    sq_erros = sum((yi - sum(b * v for b, v in zip(beta, l))) ** 2 for l, yi in zip(linhas, y))
    sq_total = sum((yi - media_y) ** 2 for yi in y)
    r2 = 1 - sq_erros / sq_total if sq_total > 0 else None
    return beta, r2


def ajustar_modelo(x, y):
    """O mesmo ajuste pelo NumPy: numpy.linalg.lstsq (decomposição SVD)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 2 or x.shape[1] == 0 or len(x) != len(y) or len(y) <= x.shape[1]:
        raise ValueError('São necessárias mais observações que variáveis, com as mesmas variáveis em todas.')
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError('A amostra contém valores não finitos.')
    design = np.column_stack([np.ones(len(x)), x])
    coeficientes, _, posto, _ = np.linalg.lstsq(design, y, rcond=None)
    if posto < design.shape[1]:
        raise ValueError(MENSAGEM_DEPENDENCIA)
    estimativas = design @ coeficientes
    total = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - float(np.sum((y - estimativas) ** 2)) / total if total > 0 else None
    return coeficientes, r2


def comparar_numpy(x, y, nomes=None):
    """Confere o cálculo manual contra numpy.linalg.lstsq: coeficientes, R² e previsões.

    nomes: rótulos dos coeficientes, começando pelo intercepto (padrão: intercepto, x1, x2, …)."""
    manual, r2_manual = ajustar_modelo_manual(x, y)
    via_numpy, r2_numpy = ajustar_modelo(x, y)
    via_numpy = [float(v) for v in via_numpy]
    nomes = nomes or ['intercepto'] + [f'x{i}' for i in range(1, len(manual))]
    xs = np.column_stack([np.ones(len(y)), np.asarray(x, dtype=float)])
    previsoes = np.abs(xs @ np.array(manual) - xs @ np.array(via_numpy))
    return {'manual': {'coeficientes': dict(zip(nomes, manual)), 'r_quadrado': r2_manual},
            'numpy': {'coeficientes': dict(zip(nomes, via_numpy)), 'r_quadrado': r2_numpy},
            'diferencas': {**{n: abs(a - b) for n, a, b in zip(nomes, manual, via_numpy)},
                           'r_quadrado': abs(r2_manual - r2_numpy) if r2_manual is not None and r2_numpy is not None else None,
                           'previsao_maxima': float(previsoes.max())}}
