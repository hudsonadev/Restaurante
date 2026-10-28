# Regressão simples: cálculo manual × NumPy

Este documento compara a função manual `ajustar_simples` ([regressao.py](regressao.py)) com o cálculo equivalente do NumPy (`numpy.linalg.lstsq`). A explicação geral das regressões está em [DOCUMENTACAO.md](DOCUMENTACAO.md).

Os dois chegam ao **mesmo resultado**: ambos fazem regressão por mínimos quadrados, isto é, escolhem a reta que minimiza a soma dos erros ao quadrado. A diferença está no **caminho** até a resposta, não na resposta.

## 1. Resultado nos 100 usuários do projeto

| | B0 (intercepto) | B1 (coeficiente angular) |
| --- | --- | --- |
| Manual (`ajustar_simples`) | 0,001093150585394**831** | 0,653497906947642**2** |
| NumPy (`np.linalg.lstsq`) | 0,001093150585395**130** | 0,653497906947642**1** |
| Diferença | 3 × 10⁻¹⁶ | 1 × 10⁻¹⁶ |

A diferença aparece só na 16ª casa decimal, que é o limite de precisão dos números de ponto flutuante (`float64`). Ela não tem nenhum efeito prático.

## 2. Como cada um calcula

### Manual

A função aplica diretamente as fórmulas fechadas da regressão simples `Y = B0 + B1·X + E`:

```text
x̄ = Σxi / n                 ȳ = Σyi / n
B1 = Σ(xi − x̄)(yi − ȳ) / Σ(xi − x̄)²
B0 = ȳ − B1·x̄
Ei = yi − (B0 + B1·xi)
```

O cálculo é feito com somas e médias em Python, passo a passo.

### NumPy

O NumPy monta a matriz de projeto com uma coluna de 1 (intercepto) e uma coluna de X:

```text
X = | 1  x1 |        β = | B0 |
    | 1  x2 |            | B1 |
    | …  …  |
```

Em seguida, resolve o sistema `Xβ ≈ y` por decomposição SVD, com uma rotina da biblioteca de álgebra linear LAPACK compilada em C/Fortran. Ele não usa a fórmula de B1: resolve o problema como álgebra matricial geral.

## 3. Diferenças práticas

| Aspecto | Manual | NumPy |
| --- | --- | --- |
| Transparência | Cada passo é visível e corresponde à fórmula do livro | Caixa-preta: chama uma rotina pronta |
| Quantidade de variáveis | Só 1 X; essas fórmulas valem apenas para a regressão simples | Qualquer número de variáveis (por isso a regressão múltipla usa NumPy) |
| Velocidade (100 pontos) | ~100 µs | ~18 µs (cerca de 5× mais rápido) |
| Escala | Laços em Python ficam lentos com milhões de pontos | Vetorizado, adequado para grandes volumes |
| Estabilidade numérica | Boa, porque centraliza os dados (xi − x̄) antes de multiplicar | Muito alta: a SVD lida bem com dados mal condicionados |
| Dados problemáticos | Detecta só o caso de X constante | Informa o posto da matriz e detecta qualquer dependência linear entre variáveis |

Os tempos foram medidos como média de 1000 execuções na máquina de desenvolvimento e servem só como ordem de grandeza.

## 4. Quando usar cada um

- **Manual:** serve para mostrar e entender o cálculo de `Y = B0 + B1·X + E`, como o requisito pede.
- **NumPy:** serve para generalizar (regressão múltipla), para ganhar desempenho e robustez e para conferir o resultado.

Com 100 usuários, a diferença de velocidade (microssegundos) não importa. A escolha aqui é didática, não de desempenho.

## 5. Como o projeto confere a equivalência

O teste `test_calculo_manual_confere_com_numpy` em [tests/test_admin.py](tests/test_admin.py) garante que a função manual dá o mesmo resultado que o `np.polyfit`. Ele também verifica que a soma dos erros é zero e que o R² corresponde aos erros calculados.

Para reproduzir a comparação com os dados reais:

```python
import numpy as np
from banco import conectar
from regressao import ajustar_simples

with conectar() as db:
    linhas = db.execute('SELECT tempo_plataforma_horas, tempo_assistindo_horas FROM usuarios').fetchall()
x = [a for a, _ in linhas]
y = [b for _, b in linhas]

manual, _ = ajustar_simples(x, y)
projeto = np.column_stack([np.ones(len(x)), x])
numpy_coef = np.linalg.lstsq(projeto, np.array(y), rcond=None)[0]

print('manual', manual)
print('numpy ', numpy_coef)
print('diferença', np.abs(manual - numpy_coef))
```
