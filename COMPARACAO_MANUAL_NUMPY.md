# Regressão simples: cálculo manual × numpy.polyfit

Este documento verifica se a regressão linear manual está implementada e compara a função manual `ajustar_simples` ([regressao.py](regressao.py)) com `numpy.polyfit`. A explicação geral das regressões está em [DOCUMENTACAO.md](DOCUMENTACAO.md).

## 1. A regressão manual está implementada?

Sim. `ajustar_simples(x, y)` calcula `Y = B0 + B1·X + E` sem nenhuma função pronta de regressão. Com X = quantidade de itens do pedido e Y = tempo de preparo em minutos, ela aplica as fórmulas de mínimos quadrados com somas e médias em Python:

```python
n = len(x)
media_x, media_y = sum(x) / n, sum(y) / n
sxy = sum((xi - media_x) * (yi - media_y) for xi, yi in zip(x, y))
sxx = sum((xi - media_x) ** 2 for xi in x)
b1 = sxy / sxx                                   # coeficiente angular
b0 = media_y - b1 * media_x                      # intercepto
erros = [yi - (b0 + b1 * xi) for xi, yi in zip(x, y)]   # E
```

O NumPy aparece na função só para converter a entrada e validar valores finitos, não no cálculo dos coeficientes. Os erros E são usados para calcular o R².

## 2. Resultado nos 100 pedidos

| | B0 (intercepto) | B1 (coeficiente angular) |
| --- | --- | --- |
| Manual (`ajustar_simples`) | 14,91539925431101**4** | 2,45035730930557**7** |
| `numpy.polyfit(x, y, 1)` | 14,91539925431101**7** | 2,45035730930557**8** |
| Diferença absoluta | 3,6 × 10⁻¹⁵ | 1,3 × 10⁻¹⁵ |

Os dois métodos chegam à **mesma reta**: `ŷ = 14,92 + 2,45 × itens`. A diferença aparece só na 15ª casa decimal, que é o limite de precisão dos números de ponto flutuante (`float64`), e não tem efeito prático. Em minutos, ela equivale a menos de um bilionésimo de segundo.

Essa tabela é calculada a cada carregamento da página Análises (seção "Cálculo manual × numpy.polyfit") e também aparece em `GET /api/analises`, no campo `simples.comparacao_polyfit`.

## 3. Como cada um calcula

### Manual

Aplica as fórmulas fechadas da regressão simples, passo a passo, como no livro. Cada variável intermediária (x̄, ȳ, Σxy, Σxx) existe no código e pode ser inspecionada.

### numpy.polyfit

`np.polyfit(x, y, 1)` ajusta um polinômio de grau 1 por mínimos quadrados. Ele monta a matriz de Vandermonde `[x, 1]`, normaliza as colunas e resolve o sistema `Xβ ≈ y` com uma rotina da biblioteca de álgebra linear LAPACK, compilada em C/Fortran. Ele não usa a fórmula de B1: resolve o problema como álgebra matricial geral.

Atenção à ordem do resultado: o polyfit devolve os coeficientes da maior potência para a menor, ou seja, `[B1, B0]`.

```python
b1, b0 = np.polyfit(x, y, 1)
```

## 4. Diferenças práticas

| Aspecto | Manual | numpy.polyfit |
| --- | --- | --- |
| Resultado | Mesma reta | Mesma reta |
| Transparência | Cada passo é visível e corresponde à fórmula | Chama uma rotina pronta |
| Grau / variáveis | Só reta (grau 1) com um X | Qualquer grau de polinômio, mas também com um único X |
| Velocidade (100 pedidos) | ~100 µs | ~23 µs (cerca de 4× mais rápido) |
| Escala | Laços em Python ficam lentos com milhões de pontos | Vetorizado, adequado para grandes volumes |
| Estabilidade numérica | Boa, porque centraliza os dados (xi − x̄) antes de multiplicar | Muito alta: normaliza as colunas e usa decomposição ortogonal |
| Dados problemáticos | Detecta X constante e lança um erro explicativo | Avisa (`RankWarning`) quando o problema é mal condicionado |

Os tempos foram medidos como média de 1000 execuções na máquina de desenvolvimento e servem só como ordem de grandeza.

Para a regressão **múltipla** (itens, fila e categorias), nenhum dos dois serve: as fórmulas manuais acima valem só para um X, e o polyfit também trabalha com uma única variável. Por isso a múltipla usa `numpy.linalg.lstsq`, que resolve mínimos quadrados para qualquer número de variáveis.

## 5. Quando usar cada um

- **Manual:** mostra e explica o cálculo de `Y = B0 + B1·X + E`, como o requisito pede.
- **numpy.polyfit:** confere o resultado e é a escolha prática em código de produção, pela velocidade e robustez.

Com 100 pedidos, a diferença de velocidade (microssegundos) não importa. A escolha aqui é didática.

## 6. Como o projeto confere a equivalência

- `comparar_polyfit(x, y)` em [regressao.py](regressao.py) roda os dois cálculos e devolve os coeficientes e as diferenças.
- Os testes em [tests/test_admin.py](tests/test_admin.py) verificam:
  - `test_calculo_manual_confere_com_numpy`: B0 e B1 iguais aos do `np.polyfit`, soma dos erros zero e R² coerente com os erros;
  - `test_comparacao_polyfit`: diferenças abaixo de 10⁻⁹ numa reta conhecida;
  - `test_previsoes_residuos_e_metricas`: diferenças abaixo de 10⁻⁹ nos dados reais da aplicação.

Para reproduzir no terminal:

```powershell
.\.venv\Scripts\python.exe regressao.py
```

A última linha mostra os coeficientes manuais, os do polyfit e as diferenças.
