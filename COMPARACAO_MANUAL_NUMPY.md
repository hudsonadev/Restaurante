# Regressão simples: cálculo manual × numpy.polyfit

Este documento verifica se a regressão linear manual está implementada e compara a função manual `ajustar_simples` ([regressao.py](regressao.py)) com `numpy.polyfit`. A explicação geral das regressões está em [DOCUMENTACAO.md](DOCUMENTACAO.md), e o passo a passo para estudo está no [GUIA_DIDATICO.md](GUIA_DIDATICO.md).

## 1. A regressão manual está implementada?

Sim. `ajustar_simples(x, y)` calcula `Y = B0 + B1·X + E` **em Python puro, sem nenhuma biblioteca**: só listas, `sum`, laços `for` e `math.isfinite` para validar a entrada.

- **X** é o **tempo dos pratos** do pedido: a soma dos tempos individuais de preparo dos pratos (`pratos.tempo_prato_min`), em minutos.
- **Y** é o **tempo real de preparo** do pedido, em minutos.

```python
n = len(x)
media_x = sum(x) / n
media_y = sum(y) / n
for xi, yi in zip(x, y):
    sxy += (xi - media_x) * (yi - media_y)      # Σ(xi − x̄)(yi − ȳ)
    sxx += (xi - media_x) ** 2                  # Σ(xi − x̄)²
b1 = sxy / sxx                                  # coeficiente angular
b0 = media_y - b1 * media_x                     # intercepto
for xi, yi in zip(x, y):
    sq_erros += (yi - (b0 + b1 * xi)) ** 2      # ΣE²
    sq_total += (yi - media_y) ** 2             # Σ(yi − ȳ)²
r2 = 1 - sq_erros / sq_total
```

O teste `test_funcao_manual_nao_usa_numpy` roda a função com o NumPy desligado (`regressao.np = None`) para provar que ela não depende dele.

## 2. Resultado nos 100 pedidos

| | Manual (Python puro) | `numpy.polyfit(x, y, 1)` | Diferença absoluta |
| --- | --- | --- | --- |
| B0 (intercepto) | 17,65564309613691**0** | 17,65564309613690**6** | 3,6 × 10⁻¹⁵ |
| B1 (coeficiente angular) | 0,436861457139857**4** | 0,436861457139857**6** | 2,2 × 10⁻¹⁶ |
| R² | 0,8427698259571683 | 0,8427698259571683 | 0 |
| Maior diferença entre as previsões dos 100 pedidos | | | 4,3 × 10⁻¹⁴ min |

Os dois métodos chegam à **mesma reta**:

```text
ŷ = 17,66 + 0,437 × tempo dos pratos
```

A diferença aparece só na 15ª ou 16ª casa decimal, que é o limite de precisão dos números de ponto flutuante (`float64`), e não tem efeito prático. Em minutos, ela equivale a menos de um bilionésimo de segundo.

Essa tabela é calculada a cada carregamento da página **Análises** (seção "Cálculo manual × numpy.polyfit") e aparece em `GET /api/analises`, no campo `simples.comparacao_polyfit`. Na página **Novo pedido**, a previsão da simples para o pedido digitado também é calculada pelos dois caminhos, e a diferença é exibida (`previsao_polyfit` e `diferenca_polyfit` em `POST /api/prever`).

## 3. Como cada um calcula

### Manual

Aplica as fórmulas fechadas da regressão simples, passo a passo, como no livro. Cada variável intermediária (x̄, ȳ, Σxy, Σxx) existe no código e pode ser inspecionada.

### numpy.polyfit

`np.polyfit(x, y, 1)` ajusta um polinômio de grau 1 por mínimos quadrados. Ele monta a matriz de Vandermonde `[x, 1]`, normaliza as colunas e resolve o sistema `Xβ ≈ y` com uma rotina da biblioteca de álgebra linear LAPACK, compilada em C/Fortran. Ele não usa a fórmula de B1: resolve o problema como álgebra matricial geral.

Atenção à ordem do resultado: o polyfit devolve os coeficientes da maior potência para a menor, ou seja, `[B1, B0]`.

```python
b1, b0 = np.polyfit(x, y, 1)
```

**Por que dá igual?** Os dois minimizam a mesma soma dos erros ao quadrado (ΣE²), então chegam à mesma reta. **De onde vem a diferença minúscula?** Fazer as contas numa ordem diferente muda o arredondamento na última casa dos 16 dígitos que o computador guarda.

## 4. Diferenças práticas

| Aspecto | Manual | numpy.polyfit |
| --- | --- | --- |
| Resultado | Mesma reta | Mesma reta |
| Transparência | Cada passo é visível e corresponde à fórmula | Chama uma rotina pronta |
| Bibliotecas | Nenhuma (Python puro) | NumPy + LAPACK |
| Grau / variáveis | Só reta (grau 1) com um X | Qualquer grau de polinômio, mas também com um único X |
| Velocidade (100 pedidos) | Dezenas de µs | Poucas dezenas de µs |
| Escala | Laços em Python ficam lentos com milhões de pontos | Vetorizado, adequado para grandes volumes |
| Estabilidade numérica | Boa, porque centraliza os dados (xi − x̄) antes de multiplicar | Muito alta: normaliza as colunas e usa decomposição ortogonal |
| Dados problemáticos | Detecta X constante e lança um erro explicativo | Avisa (`RankWarning`) quando o problema é mal condicionado |

Para a regressão **múltipla** (tempo dos pratos, fila e categorias), nenhum dos dois serve: as fórmulas manuais acima valem só para um X, e o polyfit também trabalha com uma única variável. Por isso a múltipla usa `numpy.linalg.lstsq`, que resolve mínimos quadrados para qualquer número de variáveis.

## 5. Quando usar cada um

- **Manual:** mostra e explica o cálculo de `Y = B0 + B1·X + E`, como o requisito pede.
- **numpy.polyfit:** confere o resultado e é a escolha prática em código de produção, pela velocidade e robustez.

Com 100 pedidos, a diferença de velocidade (microssegundos) não importa. A escolha aqui é didática.

## 6. Como o projeto confere a equivalência

- `comparar_polyfit(x, y)` em [regressao.py](regressao.py) roda os dois cálculos e devolve os coeficientes, os dois R² e as diferenças (intercepto, coeficiente, R² e maior diferença entre previsões).
- Os testes em [tests/test_admin.py](tests/test_admin.py) verificam:
  - `test_funcao_manual_nao_usa_numpy`: o cálculo manual funciona com o NumPy desligado;
  - `test_calculo_manual_confere_com_numpy`: B0 e B1 iguais aos do `np.polyfit`, soma dos erros zero e R² coerente com os erros;
  - `test_comparacao_polyfit`: diferenças abaixo de 10⁻⁹ em retas conhecidas, inclusive no R²;
  - `test_previsoes_residuos_e_metricas`: diferenças abaixo de 10⁻⁹ nos dados reais da aplicação.
- Em [tests/test_projeto.py](tests/test_projeto.py), `test_previsao_aplica_os_coeficientes` confere que a previsão de um pedido novo é igual pelos dois caminhos.

Para reproduzir no terminal:

```powershell
.\.venv\Scripts\python.exe regressao.py
```

A última linha mostra os coeficientes manuais, os do polyfit e as diferenças.
