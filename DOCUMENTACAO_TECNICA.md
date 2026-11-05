# Comanda: documentação técnica da regressão

Este documento descreve **como a regressão linear múltipla está implementada no código** e **a matemática por trás de cada etapa**: da consulta SQL que monta a matriz X até a previsão exibida na tela, passando pelas equações normais, pela eliminação de Gauss, pela conferência com o NumPy e pelas métricas de avaliação.

Ele complementa os outros documentos:

- [GUIA_DIDATICO.md](GUIA_DIDATICO.md): versão simples;
- [DOCUMENTACAO.md](DOCUMENTACAO.md): visão completa do sistema;
- [COMPARACAO_MANUAL_NUMPY.md](COMPARACAO_MANUAL_NUMPY.md): comparação dos dois métodos.

Os números das seções 2 a 8 foram recalculados a partir dos CSVs de `dados/`, num banco temporário. São os 100 pedidos de treino, com os β calculados.

**Sumário**

1. [Onde está cada parte](#1-onde-está-cada-parte)
2. [De onde vêm os dados](#2-de-onde-vêm-os-dados)
3. [O modelo em notação matricial](#3-o-modelo-em-notação-matricial)
4. [Mínimos quadrados: as equações normais](#4-mínimos-quadrados-as-equações-normais)
5. [Eliminação de Gauss com pivoteamento parcial](#5-eliminação-de-gauss-com-pivoteamento-parcial)
6. [Coeficiente de determinação (R²)](#6-coeficiente-de-determinação-r)
7. [Conferência com numpy.linalg.lstsq (SVD)](#7-conferência-com-numpylinalglstsq-svd)
8. [Resultado nos 100 pedidos](#8-resultado-nos-100-pedidos)
9. [Previsão de um pedido novo](#9-previsão-de-um-pedido-novo)
10. [β personalizados](#10-β-personalizados)
11. [Avaliação do modelo](#11-avaliação-do-modelo)
12. [Validação e casos de falha](#12-validação-e-casos-de-falha)
13. [Testes da regressão](#13-testes-da-regressão)
14. [Apêndice: as outras contas do sistema](#14-apêndice-as-outras-contas-do-sistema)

---

## 1. Onde está cada parte

| Arquivo | Responsabilidade | Depende de |
| --- | --- | --- |
| [comanda/modelo/minimos_quadrados.py](comanda/modelo/minimos_quadrados.py) | Ajuste manual (`ajustar_modelo_manual`), ajuste pelo NumPy (`ajustar_modelo`) e comparação (`comparar_numpy`) | Só `math` e `numpy`; **não acessa o banco** |
| [comanda/modelo/variaveis.py](comanda/modelo/variaveis.py) | Nomes das variáveis, `aplicar()` (a única implementação de ŷ = β0 + Σβi·xi) e `variaveis_do_pedido()` | Nada |
| [comanda/modelo/previsao.py](comanda/modelo/previsao.py) | Consulta das observações, resumo do modelo, análises (previsões e resíduos) e `prever_tempo()` | `db`, `coeficientes`, `minimos_quadrados`, `variaveis` |
| [comanda/modelo/coeficientes.py](comanda/modelo/coeficientes.py) | β personalizados pelo usuário (tabela `coeficientes_personalizados`) | `db` |
| [comanda/cozinha.py](comanda/cozinha.py) | Regra sintética que **gera** o tempo real (o modelo não a conhece) | Nada |
| [comanda/acompanhamento.py](comanda/acompanhamento.py) | Pedidos novos (teste independente): previsão no envio × tempo real | `cozinha`, `modelo` |
| [comanda/web/api.py](comanda/web/api.py), [comanda/web/validacao.py](comanda/web/validacao.py) | Expõem o modelo por HTTP e validam as entradas | `modelo` |

Fluxo de dados:

```text
dados/*.csv ──(migracoes)──► SQLite: pedidos, itens_originais, pratos
                                   │
                    carregar_observacoes()  (SQL: agrega por pedido)
                                   │
                    x = [maior, demais, fila, categorias],  y = tempo real
                                   │
                    comparar_numpy(x, y)
                     ├─ ajustar_modelo_manual  → β oficial (Python puro)
                     └─ ajustar_modelo (lstsq) → β de conferência
                                   │
                    obter_resumo_modelo()  → β em uso (calculados ou personalizados)
                     ├─ obter_analises()   → ŷi, Ei, EAM   (/analises, /historico)
                     └─ prever_tempo()     → ŷ de um pedido novo  (POST /api/prever)
```

O modelo **não é persistido**: os β são recalculados em cada chamada de `obter_resumo_modelo()`. Com 100 linhas e 5 coeficientes, o ajuste leva menos de um milissegundo, e assim nunca há β desatualizados.

---

## 2. De onde vêm os dados

### 2.1 A regra que gerou o tempo real

Os dados são **sintéticos**. [comanda/dados.py](comanda/dados.py) sorteia 100 pedidos com semente fixa (`SEMENTE = 20261028`): de 1 a 8 pratos e fila de 0 a 12. O tempo real de cada pedido sai de `cozinha.tempo_real`:

```math
\text{cozinha} = t_{\max} + \underbrace{0{,}35}_{\texttt{FATOR\_PARALELISMO}} \cdot \Big(\sum_j t_j - t_{\max}\Big)
```

```math
y = \max\!\big(3 + \text{cozinha} + 1{,}3 \cdot \text{fila} + 0{,}8 \cdot \text{categorias} + \varepsilon,\; 3\big), \qquad \varepsilon \sim \mathcal{N}(0,\; 3{,}7^2)
```

O resultado é arredondado para uma casa decimal. Nessa regra:

- $t_j$ é o tempo individual de cada prato, entre 1 e 22 minutos (`CARDAPIO`);
- $\varepsilon$ é o ruído (`DESVIO_RUIDO = 3.7`), calibrado para que o modelo correto reduza o erro em cerca de 76% frente a prever sempre a média.

O modelo **não conhece** essa regra: só vê os exemplos. Recuperar os pesos a partir dos dados (seção 8) é a prova de que o ajuste funciona.

### 2.2 A consulta das observações

`carregar_observacoes()` ([previsao.py](comanda/modelo/previsao.py)) monta uma linha por pedido em uma única consulta SQL:

```sql
SELECT p.id, p.cliente, p.pedidos_na_fila,
       p.tempo_preparo_min                                    AS tempo_preparo,           -- y
       COUNT(i.prato_id)                                      AS quantidade_itens,
       COALESCE(SUM(c.tempo_prato_min), 0)                    AS tempo_base_itens,
       COALESCE(MAX(c.tempo_prato_min), 0)                    AS tempo_maior_prato,       -- x1
       COALESCE(SUM(c.tempo_prato_min) - MAX(c.tempo_prato_min), 0) AS tempo_demais_pratos, -- x2
       COUNT(DISTINCT c.categoria_id)                         AS quantidade_categorias    -- x4
FROM pedidos p
LEFT JOIN itens_originais i ON i.pedido_id = p.id
LEFT JOIN pratos c          ON c.id = i.prato_id
GROUP BY p.id ORDER BY p.id
```

A variável $x_3$ (fila) é a coluna `pedidos_na_fila`.

O treino usa **`itens_originais`**, uma fotografia imutável dos itens com que cada pedido foi feito. Não usa `itens_pedido`, que o usuário pode editar na tela. O tempo real registrado corresponde aos itens originais; treinar com itens editados desalinharia X e y.

### 2.3 As variáveis

Para um pedido com tempos de prato $t_1, \dots, t_m$:

| Símbolo | Coluna | Definição | Faixa nos dados |
| --- | --- | --- | --- |
| $x_1$ | `tempo_maior_prato` | $\max_j t_j$ | 2 a 22 min |
| $x_2$ | `tempo_demais_pratos` | $\sum_j t_j - \max_j t_j$ | 0 a 123 min |
| $x_3$ | `pedidos_na_fila` | pedidos já na fila | 0 a 12 |
| $x_4$ | `quantidade_categorias` | categorias distintas no pedido | 1 a 5 |
| $y$ | `tempo_preparo` | tempo real, em minutos | média $\bar y = 37{,}484$ |

A ordem das variáveis é definida uma única vez em `VARIAVEIS` ([variaveis.py](comanda/modelo/variaveis.py)) e reaproveitada em todo o sistema:

```python
VARIAVEIS = ['tempo_maior_prato', 'tempo_demais_pratos', 'pedidos_na_fila', 'quantidade_categorias']
NOMES_COEFICIENTES = ['intercepto'] + VARIAVEIS
```

**Por que separar o maior prato dos demais?** Porque a cozinha prepara os pratos em paralelo. Com uma única variável "soma dos tempos", o modelo não distingue um risoto de 20 min de quatro saladas de 5 min. Com a separação, o R² sobe de 0,930 para 0,947 e a redução de erro em pedidos novos, de 72% para 76% (tabela em [DOCUMENTACAO.md §3.1](DOCUMENTACAO.md)).

---

## 3. O modelo em notação matricial

Para cada pedido $i = 1, \dots, n$:

```math
y_i = \beta_0 + \beta_1 x_{i1} + \beta_2 x_{i2} + \beta_3 x_{i3} + \beta_4 x_{i4} + E_i
```

Empilhando os $n = 100$ pedidos:

```math
\mathbf{y} = X\boldsymbol\beta + \mathbf{E},
\qquad
X = \begin{bmatrix}
1 & x_{11} & x_{12} & x_{13} & x_{14} \\
1 & x_{21} & x_{22} & x_{23} & x_{24} \\
\vdots & \vdots & \vdots & \vdots & \vdots \\
1 & x_{n1} & x_{n2} & x_{n3} & x_{n4}
\end{bmatrix}_{n \times 5},
\qquad
\boldsymbol\beta = \begin{bmatrix}\beta_0\\ \beta_1\\ \beta_2\\ \beta_3\\ \beta_4\end{bmatrix}
```

A coluna de 1s permite estimar o intercepto $\beta_0$. No código ela é acrescentada dentro de `ajustar_modelo_manual`; quem chama passa só as variáveis:

```python
linhas = [[1.0] + linha for linha in x]   # coluna de 1 = intercepto
k = len(linhas[0])                        # k = 5 coeficientes
```

---

## 4. Mínimos quadrados: as equações normais

### 4.1 A função objetivo

Os β escolhidos são os que minimizam a **soma dos quadrados dos erros**:

```math
S(\boldsymbol\beta) = \sum_{i=1}^{n} E_i^2 = \sum_{i=1}^{n} \big(y_i - \mathbf{x}_i^\top \boldsymbol\beta\big)^2 = (\mathbf{y} - X\boldsymbol\beta)^\top(\mathbf{y} - X\boldsymbol\beta)
```

### 4.2 Derivação

Expandindo:

```math
S(\boldsymbol\beta) = \mathbf{y}^\top\mathbf{y} - 2\,\boldsymbol\beta^\top X^\top\mathbf{y} + \boldsymbol\beta^\top X^\top X\,\boldsymbol\beta
```

Gradiente igual a zero:

```math
\nabla S = -2\,X^\top\mathbf{y} + 2\,X^\top X\,\boldsymbol\beta = \mathbf{0}
\quad\Longrightarrow\quad
\boxed{(X^\top X)\,\boldsymbol\beta = X^\top\mathbf{y}}
```

Esse é o sistema das **equações normais**: 5 equações lineares com 5 incógnitas.

A hessiana é $\nabla^2 S = 2\,X^\top X$. Quando as colunas de X são linearmente independentes (posto 5), $X^\top X$ é definida positiva. Então $S$ é estritamente convexa e a solução é o **único mínimo global**. Se uma variável for constante ou combinação das outras, $X^\top X$ é singular, não há solução única e o código lança um erro (seção 12).

### 4.3 Elemento a elemento: o que o código monta

Com $x_{i0} = 1$:

```math
(X^\top X)_{ab} = \sum_{i=1}^{n} x_{ia}\, x_{ib},
\qquad
(X^\top \mathbf{y})_a = \sum_{i=1}^{n} x_{ia}\, y_i,
\qquad a, b \in \{0, \dots, 4\}
```

Em Python puro, sem nenhuma biblioteca:

```python
xtx = [[sum(l[i] * l[j] for l in linhas) for j in range(k)] for i in range(k)]
xty = [sum(l[i] * yi for l, yi in zip(linhas, y)) for i in range(k)]
beta = _resolver_gauss(xtx, xty)
```

Cada entrada é uma soma: $(X^\top X)_{00} = n$, $(X^\top X)_{01} = \sum x_{i1}$, $(X^\top X)_{11} = \sum x_{i1}^2$ e assim por diante. Montar a matriz custa $O(n k^2)$ operações e resolver o sistema, $O(k^3)$.

### 4.4 Duas propriedades do resíduo

A primeira linha das equações normais (correspondente à coluna de 1s) é:

```math
\sum_i (y_i - \hat y_i) = 0
```

Ou seja, **os resíduos somam zero**. De modo geral, $X^\top\mathbf{E} = \mathbf{0}$: o vetor de resíduos é **ortogonal** a cada coluna de X. Por isso a correlação entre o resíduo e cada variável é zero. Nos dados reais:

| Verificação | Valor calculado |
| --- | --- |
| $\sum_i E_i$ | $8{,}0 \times 10^{-15}$ |
| correlação(E, maior prato) | $-2{,}4 \times 10^{-15}$ |
| correlação(E, demais pratos) | $-7{,}1 \times 10^{-16}$ |
| correlação(E, fila) | $-8{,}8 \times 10^{-16}$ |
| correlação(E, categorias) | $8{,}2 \times 10^{-16}$ |

Os valores são zero até o limite do `float64`. É uma boa forma de checar se uma implementação de mínimos quadrados está correta.

---

## 5. Eliminação de Gauss com pivoteamento parcial

`_resolver_gauss(a, b)` resolve $A\boldsymbol\beta = \mathbf{b}$, com $A = X^\top X$ e $\mathbf{b} = X^\top\mathbf{y}$.

### 5.1 Algoritmo

Começa pela matriz aumentada $M = [A \mid \mathbf{b}]$, de tamanho $k \times (k+1)$:

1. **Escala de referência:** $s = \max_{ij} |a_{ij}|$, usada na tolerância do pivô.
2. **Para cada coluna** $c = 0, \dots, k-1$:
   1. **Pivoteamento parcial:** escolher $p = \arg\max_{i \ge c} |m_{ic}|$ e trocar as linhas $c$ e $p$. Usar o maior pivô disponível evita dividir por números pequenos, que ampliam o erro de arredondamento.
   2. **Teste de singularidade:** se $|m_{cc}| \le 10^{-12} \cdot s$, lançar `ValueError` (as variáveis não são independentes).
   3. **Eliminação:** para cada linha $i > c$:
      ```math
      f_i = \frac{m_{ic}}{m_{cc}}, \qquad m_{ij} \leftarrow m_{ij} - f_i \, m_{cj} \quad (j = c, \dots, k)
      ```
3. **Substituição regressiva** (de baixo para cima), com a matriz já triangular superior:
   ```math
   \beta_i = \frac{1}{m_{ii}}\Big(m_{ik} - \sum_{j=i+1}^{k-1} m_{ij}\,\beta_j\Big), \qquad i = k-1, \dots, 0
   ```

Trecho correspondente:

```python
for coluna in range(n):
    pivo = max(range(coluna, n), key=lambda i: abs(m[i][coluna]))
    if abs(m[pivo][coluna]) <= 1e-12 * escala:
        raise ValueError(MENSAGEM_DEPENDENCIA)
    m[coluna], m[pivo] = m[pivo], m[coluna]
    for i in range(coluna + 1, n):
        fator = m[i][coluna] / m[coluna][coluna]
        for j in range(coluna, n + 1):
            m[i][j] -= fator * m[coluna][j]
beta = [0.0] * n
for i in range(n - 1, -1, -1):
    beta[i] = (m[i][n] - sum(m[i][j] * beta[j] for j in range(i + 1, n))) / m[i][i]
```

A tolerância é **relativa** ($10^{-12} \cdot s$), não absoluta. Assim o teste funciona da mesma forma se os tempos estiverem em minutos ou em segundos.

### 5.2 Exemplo completo, como o código executa

Quatro pedidos com uma variável de tempo (t) e a fila (f), gerados exatamente por $y = 10 + 0{,}5\,t + 1\,f$:

| Pedido | t | f | y |
| --- | --- | --- | --- |
| A | 10 | 0 | 15 |
| B | 20 | 2 | 22 |
| C | 30 | 1 | 26 |
| D | 40 | 3 | 33 |

**Somas:**

| Soma | Valor |
| --- | --- |
| $n$ | 4 |
| $\sum t$ | 100 |
| $\sum f$ | 6 |
| $\sum t^2$ | 3000 |
| $\sum tf$ | 190 |
| $\sum f^2$ | 14 |
| $\sum y$ | 96 |
| $\sum ty$ | 2690 |
| $\sum fy$ | 169 |

```math
[A \mid \mathbf{b}] =
\left[\begin{array}{ccc|c}
4 & 100 & 6 & 96 \\
100 & 3000 & 190 & 2690 \\
6 & 190 & 14 & 169
\end{array}\right]
```

**Coluna 0.** O maior $|m_{i0}|$ é 100 (linha 1), então o código **troca as linhas 0 e 1**. Os fatores são $f_1 = 4/100 = 0{,}04$ e $f_2 = 6/100 = 0{,}06$:

```math
\left[\begin{array}{ccc|c}
100 & 3000 & 190 & 2690 \\
0 & -20 & -1{,}6 & -11{,}6 \\
0 & 10 & 2{,}6 & 7{,}6
\end{array}\right]
```

**Coluna 1.** O pivô é $|-20| > |10|$, então não há troca. O fator é $f_2 = 10 / (-20) = -0{,}5$:

```math
\left[\begin{array}{ccc|c}
100 & 3000 & 190 & 2690 \\
0 & -20 & -1{,}6 & -11{,}6 \\
0 & 0 & 1{,}8 & 1{,}8
\end{array}\right]
```

**Substituição regressiva:**

```math
\beta_2 = \frac{1{,}8}{1{,}8} = 1,
\qquad
\beta_1 = \frac{-11{,}6 - (-1{,}6)(1)}{-20} = 0{,}5,
\qquad
\beta_0 = \frac{2690 - 3000(0{,}5) - 190(1)}{100} = 10
```

Os pesos usados para gerar os dados voltam exatos. Em `float64`, `ajustar_modelo_manual` devolve `[9.999999999999986, 0.5000000000000008, 0.9999999999999948]` com R² = 1. As diferenças nas últimas casas são arredondamento.

> O [guia didático](GUIA_DIDATICO.md) escalona o mesmo sistema **sem** trocar linhas, porque é mais fácil acompanhar no papel. O resultado é o mesmo; o pivoteamento muda só a ordem das contas e melhora a precisão numérica.

---

## 6. Coeficiente de determinação (R²)

```math
\hat y_i = \mathbf{x}_i^\top\boldsymbol\beta,
\qquad
E_i = y_i - \hat y_i,
\qquad
\text{SQE} = \sum_i E_i^2,
\qquad
\text{SQT} = \sum_i (y_i - \bar y)^2
```

```math
R^2 = 1 - \frac{\text{SQE}}{\text{SQT}}
```

O R² é a fração da variação de y em torno da média que o modelo explica. Com β de mínimos quadrados e intercepto, $0 \le R^2 \le 1$.

No código:

```python
media_y = sum(y) / len(y)
sq_erros = sum((yi - sum(b * v for b, v in zip(beta, l))) ** 2 for l, yi in zip(linhas, y))
sq_total = sum((yi - media_y) ** 2 for yi in y)
r2 = 1 - sq_erros / sq_total if sq_total > 0 else None
```

Se y for constante, $\text{SQT} = 0$, o R² não está definido e a função devolve `None`. Os β continuam válidos nesse caso (o ajuste dá $\beta_0 = \bar y$ e os demais zero).

---

## 7. Conferência com numpy.linalg.lstsq (SVD)

### 7.1 O cálculo de referência

`ajustar_modelo(x, y)` resolve o mesmo problema por outro caminho. Monta a matriz de projeto com `np.column_stack([np.ones(n), x])` e chama `np.linalg.lstsq(design, y, rcond=None)`.

O `lstsq` não forma $X^\top X$. Ele usa a decomposição em valores singulares (SVD) da própria X:

```math
X = U \Sigma V^\top
\qquad\Longrightarrow\qquad
\boldsymbol\beta = V \Sigma^{+} U^\top \mathbf{y}
```

- $U$ ($n \times n$) e $V$ ($5 \times 5$) são ortogonais.
- $\Sigma$ é diagonal com os valores singulares $\sigma_1 \ge \dots \ge \sigma_5 \ge 0$.
- $\Sigma^{+}$ inverte os $\sigma_j$ acima de um limiar e zera os demais.

O `lstsq` também devolve o **posto** de X. O código lança o mesmo `ValueError` do cálculo manual se `posto < 5`.

### 7.2 Por que os dois dão o mesmo resultado

Os dois minimizam a mesma $S(\boldsymbol\beta)$, e com posto completo essa solução é única. Só muda o caminho das contas: o manual passa por $X^\top X$ e Gauss, o NumPy pela SVD de X. Por isso o arredondamento difere apenas nas últimas casas.

### 7.3 Condicionamento

O número de condição mede quanto um erro relativo na entrada pode ser ampliado na saída:

```math
\kappa(X) = \frac{\sigma_{\max}}{\sigma_{\min}} \approx 180{,}9,
\qquad
\kappa(X^\top X) = \kappa(X)^2 \approx 3{,}27 \times 10^{4}
```

Montar $X^\top X$ **eleva o condicionamento ao quadrado**, e é por isso que, em geral, as bibliotecas preferem SVD ou QR. Aqui $\kappa \approx 3 \times 10^4$ é pequeno. Com cerca de 16 dígitos do `float64`, sobram mais de 11 dígitos corretos, o que bate com as diferenças da ordem de $10^{-14}$ na seção 8.

### 7.4 `comparar_numpy`

`comparar_numpy(x, y, nomes)` roda os dois ajustes e devolve:

```python
{'manual':     {'coeficientes': {nome: β}, 'r_quadrado': R²},
 'numpy':      {'coeficientes': {nome: β}, 'r_quadrado': R²},
 'diferencas': {nome: |β_manual − β_numpy|, ..., 'r_quadrado': |ΔR²|,
                'previsao_maxima': max_i |x_iᵀβ_manual − x_iᵀβ_numpy|}}
```

`obter_resumo_modelo()` chama essa função com `NOMES_COEFICIENTES` e usa **os β manuais como resultado oficial** (`metodo = 'manual'`). Os β do NumPy servem só como conferência. Na API, a comparação aparece em `GET /api/analises` (`multipla.comparacao_numpy`) e na tabela "Cálculo manual × numpy.linalg.lstsq" da página Análises.

---

## 8. Resultado nos 100 pedidos

### 8.1 O sistema montado

```math
\underbrace{\begin{bmatrix}
100 & 1\,407 & 3\,157 & 572 & 275 \\
1\,407 & 23\,347 & 55\,336 & 7\,872 & 4\,047 \\
3\,157 & 55\,336 & 179\,437 & 17\,085 & 10\,559 \\
572 & 7\,872 & 17\,085 & 4\,886 & 1\,574 \\
275 & 4\,047 & 10\,559 & 1\,574 & 885
\end{bmatrix}}_{X^\top X}
\begin{bmatrix}\beta_0\\ \beta_1\\ \beta_2\\ \beta_3\\ \beta_4\end{bmatrix}
=
\underbrace{\begin{bmatrix} 3\,748{,}4 \\ 59\,726{,}1 \\ 156\,997{,}5 \\ 23\,071{,}8 \\ 11\,265{,}8 \end{bmatrix}}_{X^\top \mathbf{y}}
```

Para ler a matriz:

- 100 é $n$;
- 1 407 é $\sum$ maior prato;
- 3 157 é $\sum$ demais pratos;
- 572 é $\sum$ fila;
- 275 é $\sum$ categorias;
- 3 748,4 é $\sum y$, e daí $\bar y = 37{,}484$ min.

### 8.2 Os coeficientes

| Coeficiente | Manual (Python puro) | `lstsq` | Diferença | Valor na regra de geração |
| --- | --- | --- | --- | --- |
| β0 (intercepto) | 3,367269561609 | 3,367269561609 | 2,5 × 10⁻¹⁴ | 3 |
| β1 (maior prato) | 0,891427434220 | 0,891427434220 | 7,8 × 10⁻¹⁶ | 1 |
| β2 (demais pratos) | 0,354579647048 | 0,354579647048 | 7,8 × 10⁻¹⁶ | 0,35 |
| β3 (fila) | 1,320731243329 | 1,320731243329 | 2,9 × 10⁻¹⁵ | 1,3 |
| β4 (categorias) | 1,027521552643 | 1,027521552643 | 1,6 × 10⁻¹⁴ | 0,8 |
| R² | 0,947167790849 | 0,947167790849 | 0 | |

A maior diferença entre as previsões dos 100 pedidos é $7{,}1 \times 10^{-14}$ min.

```math
\hat y = 3{,}367 + 0{,}891\,x_1 + 0{,}355\,x_2 + 1{,}321\,x_3 + 1{,}028\,x_4
```

Os β ficam próximos dos pesos da regra de geração: **o modelo recuperou a regra da cozinha só a partir dos exemplos**. A diferença maior em β1 (0,891 em vez de 1) e em β4 (1,03 em vez de 0,8) vem do ruído: com 100 pedidos, cada estimativa tem incerteza (seção 8.4).

### 8.3 Somas de quadrados

| Grandeza | Valor |
| --- | --- |
| SQT = $\sum (y_i - \bar y)^2$ | 24 360,99 |
| SQE = $\sum E_i^2$ | 1 287,05 |
| $R^2 = 1 - 1\,287{,}05 / 24\,360{,}99$ | 0,9472 |

### 8.4 Erro-padrão e estatística t

Estas contas **não estão no código da aplicação**: foram feitas à parte, para interpretar os β. A variância do ruído é estimada por:

```math
\hat\sigma^2 = \frac{\text{SQE}}{n - p - 1} = \frac{1\,287{,}05}{95} = 13{,}55,
\qquad \hat\sigma = 3{,}68 \text{ min}
```

O valor fica próximo dos 3,7 min de `DESVIO_RUIDO`: o modelo deixa sobrar quase só o ruído. A matriz de covariância dos β e a estatística t são:

```math
\widehat{\text{Cov}}(\boldsymbol\beta) = \hat\sigma^2\,(X^\top X)^{-1},
\qquad
\text{EP}(\beta_j) = \sqrt{\big[\hat\sigma^2 (X^\top X)^{-1}\big]_{jj}},
\qquad
t_j = \frac{\beta_j}{\text{EP}(\beta_j)}
```

| Coeficiente | β | Erro-padrão | t |
| --- | --- | --- | --- |
| β0 | 3,367 | 1,465 | 2,30 |
| β1 (maior prato) | 0,891 | 0,083 | 10,78 |
| β2 (demais pratos) | 0,355 | 0,021 | 17,03 |
| β3 (fila) | 1,321 | 0,092 | 14,33 |
| β4 (categorias) | 1,028 | 0,408 | 2,52 |

Todos têm $|t| > 1{,}99$, o valor crítico de 5% com 95 graus de liberdade, então todos são estatisticamente diferentes de zero. Categorias é a variável menos precisa (EP 0,41), o que explica por que β4 = 1,03 ainda é compatível com o 0,8 da regra: a distância é de cerca de 0,6 erro-padrão.

### 8.5 Dois pedidos como exemplo

**Pedido #1:** Creme de cebola (7 min), fila 9, 1 categoria.

```math
\hat y = 3{,}367 + 0{,}891(7) + 0{,}355(0) + 1{,}321(9) + 1{,}028(1) = 22{,}52 \text{ min},
\qquad y = 27{,}0,\; E = 4{,}48
```

**Pedido #12:** 8 pratos, maior de 13 min, demais somando 59 min, fila 1, 5 categorias.

```math
\hat y = 3{,}367 + 0{,}891(13) + 0{,}355(59) + 1{,}321(1) + 1{,}028(5) = 42{,}33 \text{ min}
```

A regra da cozinha sem ruído dá $3 + 13 + 0{,}35(59) + 1{,}3(1) + 0{,}8(5) = 41{,}95$ min, e o real foi 33,7 min. O modelo acertou a regra; o erro de −8,6 min é quase todo ruído.

---

## 9. Previsão de um pedido novo

### 9.1 Caminho de uma requisição

```text
POST /api/prever  {"pratos": [ids], "pedidos_na_fila": f}
  → validacao.ler_pedido     → (ids, fila, tempos dos pratos, nº de categorias)   ou 400
  → previsao.prever_tempo    → resposta                                           ou 422
```

### 9.2 Montagem das variáveis

`variaveis_do_pedido(tempos, fila, categorias)` aplica as mesmas definições da consulta SQL:

```python
maior = max(tempos_pratos)
return dict(zip(VARIAVEIS, [maior, sum(tempos_pratos) - maior, pedidos_na_fila, quantidade_categorias]))
```

### 9.3 A fórmula, num único lugar

```python
def aplicar(coeficientes, valores):
    return coeficientes['intercepto'] + sum(coeficientes[v] * valores[v] for v in VARIAVEIS)
```

Todas as previsões do sistema passam por `aplicar`:

- o treino (R² com β personalizados);
- os resíduos de `/analises`;
- a previsão de um pedido novo;
- a conferência com o NumPy.

Por isso o número da tela, o do gráfico e o da API nunca divergem.

### 9.4 O que `prever_tempo` calcula

Seja $\mathbf{x}^*$ o pedido novo:

| Campo da resposta | Fórmula | Uso |
| --- | --- | --- |
| `previsao_bruta` | $\hat y^* = \beta_0 + \sum_j \beta_j x^*_j$ com os **β em uso** | Valor do modelo, sem ajuste |
| `previsao_minutos` | $\max(0,\; \hat y^*)$ | O que a tela mostra (tempo não pode ser negativo) |
| `previsao_calculada` | $\hat y^*$ com os β **calculados** | Base da conferência |
| `previsao_numpy` | $\hat y^*$ com os β do `lstsq` | Conferência |
| `diferenca_numpy` | $\lvert \hat y^*_{\text{calculada}} - \hat y^*_{\text{numpy}} \rvert$ | Linha "Conferida com o NumPy" |
| `calculo` | texto `3,37 + 0,89 × 13,0 + … = 42,3 min` | Mostra a conta na tela |

O limite em zero vale **só na exibição**. Gráficos e resíduos usam a previsão bruta, para não esconder o comportamento linear do modelo.

**Aviso de extrapolação.** `obter_resumo_modelo` guarda o intervalo observado de cada variável, `intervalos[v] = [min, max]`. Se alguma variável do pedido cair fora de $[\min_v, \max_v]$, a resposta traz o aviso *"a estimativa é uma extrapolação"*. É o caso de uma fila acima de 12. A validação aceita fila até 50 (`LIMITE_FILA`), mas o modelo só viu de 0 a 12.

---

## 10. β personalizados

O usuário pode substituir os β na página Análises ou por `PUT /api/coeficientes`. A regra fica em `obter_resumo_modelo`:

```python
salvos = personalizados.ler()
usa_personalizados = set(salvos) == set(NOMES_COEFICIENTES)   # só vale com os cinco
em_uso = salvos if usa_personalizados else calculados
```

- Os β em uso valem para todas as previsões do sistema.
- A tabela manual × NumPy (`comparacao_numpy`) continua usando os **calculados**.
- O R² é recalculado com os β em uso por `_r_quadrado`, com a mesma fórmula $1 - \text{SQE}/\text{SQT}$.

Os β calculados minimizam a SQE, então **qualquer outro conjunto dá SQE maior ou igual e R² menor ou igual**. Com β arbitrários, o R² pode até ficar **negativo**, quando o modelo erra mais que a média. Exemplo: os pesos exatos da regra de geração (3; 1; 0,35; 1,3; 0,8) dão R² = 0,9447, abaixo de 0,9472.

A validação (`ler_coeficientes`) exige os cinco nomes, valores finitos e $|\beta| \le 1000$ (`LIMITE_COEFICIENTE`).

---

## 11. Avaliação do modelo

### 11.1 Métricas na amostra de treino

`obter_analises()` calcula, para cada pedido, `previsao_multipla` $= \hat y_i$ e `residuo_multipla` $= E_i$. O EAM é calculado ali; as demais métricas, a partir desses resíduos ($n = 100$, $p = 4$):

| Métrica | Fórmula | Valor |
| --- | --- | --- |
| EAM (erro absoluto médio) | $\frac{1}{n}\sum \lvert E_i \rvert$ | 2,82 min |
| RMSE | $\sqrt{\frac{1}{n}\sum E_i^2}$ | 3,59 min |
| Maior erro | $\max \lvert E_i \rvert$ | 9,25 min |
| R² | $1 - \text{SQE}/\text{SQT}$ | 0,9472 |
| R² ajustado | $1 - (1 - R^2)\dfrac{n-1}{n-p-1}$ | 0,9449 |

O R² ajustado desconta o número de variáveis. A queda pequena (0,947 → 0,945) indica que as quatro variáveis compensam o custo.

Antes de responder em JSON, valores não finitos (`NaN`, `inf`) viram `None`, para que a resposta seja JSON estrito.

### 11.2 Validação cruzada (pedidos não vistos)

O erro no treino é otimista, porque o modelo viu aqueles pedidos. O teste `test_reducao_de_erro_calibrada` ([tests/test_admin.py](tests/test_admin.py)) mede o erro em pedidos novos com **validação cruzada 10-fold repetida 10 vezes**:

```text
para rep = 0..9:
    ordem = permutação aleatória dos 100 pedidos (semente rep)
    para dobra = 0..9:
        teste  = ordem[dobra::10]          (10 pedidos)
        treino = os outros 90
        β = ajustar_modelo_manual(X[treino], y[treino])
        guarda |y_teste − X_teste·β|
```

Cada pedido é previsto 10 vezes por um modelo que não o viu: $10 \times 100 = 1\,000$ erros no total.

```math
\text{EAM}_{\text{CV}} = \frac{1}{1000}\sum \lvert y_i - \hat y_i^{(-i)} \rvert = 2{,}97 \text{ min},
\qquad
\text{EAM}_{\text{média}} = \frac{1}{n}\sum \lvert y_i - \bar y \rvert = 12{,}29 \text{ min}
```

```math
\text{redução de erro} = 1 - \frac{\text{EAM}_{\text{CV}}}{\text{EAM}_{\text{média}}} = 1 - \frac{2{,}97}{12{,}29} = 75{,}9\%
```

Aqui $\hat y_i^{(-i)}$ é a previsão de um modelo treinado sem o pedido $i$. O teste exige que a redução fique entre 74% e 78%. O EAM em pedidos novos (2,97) é pouco maior que no treino (2,82), então **não há sobreajuste**.

### 11.3 Previsão × realidade com pedidos acompanhados

Os pedidos enviados à Cozinha ([acompanhamento.py](comanda/acompanhamento.py)) são o teste mais honesto: **não entram no treino**.

No envio, o sistema grava a previsão daquele momento. No modo `simulado` (padrão), sorteia também o tempo real pela mesma regra `cozinha.tempo_real` do histórico. Um relógio acelerado, `ACELERACAO_SIMULACAO = 120` (1 s real = 2 min simulados), corre até esse tempo antes de liberar o botão Pronto:

```math
\text{minutos simulados} = \frac{\Delta t_{\text{real}} \,[\text{s}]}{60} \times 120
```

Para os $m$ pedidos concluídos, com $e_i = y_i^{\text{real}} - \hat y_i$, `resumo()` calcula:

```math
\text{EAM} = \frac{1}{m}\sum \lvert e_i \rvert,
\qquad
\text{viés} = \frac{1}{m}\sum e_i,
\qquad
\text{maior erro} = e_{\arg\max_i \lvert e_i \rvert}
```

Viés positivo significa que os pedidos demoram mais que o previsto, ou seja, prazos otimistas. Em pedidos simulados, o EAM fica em torno de 3 min, a mesma faixa da validação cruzada.

---

## 12. Validação e casos de falha

| Situação | Onde é detectada | Resultado |
| --- | --- | --- |
| Valores não numéricos | `_validar`: `float()` falha | `ValueError('As amostras devem conter apenas números.')` |
| $n \le k$, linhas de tamanhos diferentes ou X vazio | `_validar` / `ajustar_modelo` | `ValueError('São necessárias mais observações que variáveis…')` |
| `NaN` ou `inf` | `math.isfinite` / `np.isfinite` | `ValueError('A amostra contém valores não finitos.')` |
| Variável constante ou combinação das outras | Gauss: pivô $\le 10^{-12} s$; NumPy: posto $< 5$ | `ValueError(MENSAGEM_DEPENDENCIA)` |
| y constante | SQT = 0 | β calculados, R² = `None` |

Como esses erros chegam ao usuário:

- `obter_resumo_modelo` captura o `ValueError` e devolve `disponivel: False` com o `aviso`.
- As páginas mostram o aviso.
- `POST /api/prever` responde **422** (modelo indisponível).
- Entradas inválidas do usuário (lista vazia, prato repetido ou inexistente, fila fora de 0–50, booleanos) lançam `EntradaInvalida` em [validacao.py](comanda/web/validacao.py), e a API responde **400**.

---

## 13. Testes da regressão

| Teste | O que garante |
| --- | --- |
| `test_plano_conhecido_e_alvo_constante` | Recupera $y = 2 + 3a + 4b + 5c$ exatamente (R² = 1); y constante dá R² `None` |
| `test_manual_confere_com_numpy` | Manual e `lstsq` iguais em dados com ruído (diferença $< 10^{-9}$) |
| `test_funcao_manual_nao_usa_numpy` | Com `minimos_quadrados.np = None`, o ajuste manual continua funcionando: é Python puro |
| `test_variaveis_dependentes_e_amostras_invalidas` | Colinearidade, amostra vazia, `inf`, `nan` e linhas mal formadas geram erro |
| `test_previsoes_residuos_e_metricas` | Nos dados reais: previsões, resíduos, EAM e diferenças manual × NumPy $< 10^{-9}$ |
| `test_reducao_de_erro_calibrada` | Validação cruzada com redução de erro entre 74% e 78% |
| `test_previsao_aplica_os_coeficientes` | A previsão de um pedido novo é $\beta_0 + \sum \beta_j x_j$ e coincide com a do NumPy |

Os testes redirecionam `comanda.db.CAMINHO_BANCO` para bancos temporários. Para rodar:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe gerenciar.py modelo     # fórmula, R² e manual × NumPy no terminal
```

---

## 14. Apêndice: as outras contas do sistema

As sugestões de pratos ([comanda/recomendacao.py](comanda/recomendacao.py)) não usam a regressão, mas também são contas explícitas. Elas usam **`itens_pedido`** (os itens atuais, editáveis).

**Matrizes de base.** Para $P$ pedidos, $J$ pratos e $C$ categorias:

- $M \in \{0,1\}^{P \times J}$, com $M_{pj} = 1$ se o prato $j$ está no pedido $p$;
- $N \in \mathbb{N}^{P \times C}$ conta os pratos de cada categoria por pedido.

**Perfil do pedido.** É a fração de cada categoria no pedido:

```math
\pi_{pc} = \frac{N_{pc}}{\sum_{c'} N_{pc'}}
```

**Similaridade do cosseno.** Linhas de norma zero viram vetor nulo, e o resultado é cortado em $[0, 1]$:

```math
\cos(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\lVert\mathbf{u}\rVert\,\lVert\mathbf{v}\rVert}
```

- Entre categorias: $S^{\text{cat}} = \cos$ das colunas de $N$, ou seja, quanto duas categorias aparecem nos mesmos pedidos.
- Entre pedidos: $\cos$ dos perfis $\pi$.

**Pontuação de um prato $j$** (da categoria $c_j$) para o pedido $p$:

```math
A_j = \sum_c \pi_{pc}\, S^{\text{cat}}_{c\,c_j}
\qquad \text{(afinidade por categoria)}
```

```math
B_j = \frac{\sum_{q \in V} s_{pq}\, M_{qj}}{\sum_{q \in V} s_{pq}}
\qquad \text{(colaborativa: média ponderada nos 5 vizinhos } V \text{ com } s_{pq} > 0\text{)}
```

```math
\text{pontuação}_j =
\begin{cases}
\dfrac{\text{popularidade}_j}{P} & \text{pedido vazio} \\[6pt]
\dfrac{A_j + B_j}{2} & \text{com vizinhos} \\[6pt]
A_j & \text{sem vizinhos}
\end{cases}
```

Pratos já no pedido são excluídos. O desempate é feito pela pontuação, depois pela popularidade e depois pelo ID. A pontuação é um índice de 0 a 1, **não uma probabilidade**.

**Agrupamento de categorias.** Usa agrupamento hierárquico aglomerativo com **ligação média**, sobre a distância $d = 1 - S^{\text{cat}}$:

```math
d(G, H) = \frac{1}{|G|\,|H|}\sum_{a \in G}\sum_{b \in H} d_{ab}
```

O algoritmo começa com cada categoria isolada e une repetidamente o par de grupos de menor $d(G, H)$ até sobrarem 3 grupos. Os empates são resolvidos pelos IDs, de forma determinística.
