# Regressão múltipla: cálculo manual × numpy.linalg.lstsq

Este documento verifica se a regressão linear múltipla está implementada à mão e compara a função manual `ajustar_modelo_manual` ([comanda/modelo/minimos_quadrados.py](comanda/modelo/minimos_quadrados.py)) com `numpy.linalg.lstsq`. A explicação completa do modelo está em [DOCUMENTACAO.md](DOCUMENTACAO.md), e a versão resumida, no [Guia didático](GUIA_DIDATICO.md).

## 1. A regressão manual está implementada?

Sim. `ajustar_modelo_manual(x, y)` calcula

```text
Y = β0 + β1·maior prato + β2·demais pratos + β3·fila + β4·categorias + E
```

**em Python puro, sem nenhuma biblioteca**: só listas, `sum`, laços `for` e `math.isfinite` para validar a entrada. É o resultado oficial do sistema: os coeficientes exibidos e usados nas previsões vêm dele.

O método tem dois passos.

**1. Montar as equações normais.** Com a matriz X = [1, x1, x2, x3, x4] (a coluna de 1 é o intercepto), os β que minimizam a soma dos erros ao quadrado (ΣE²) são a solução do sistema:

```text
(XᵀX) · β = Xᵀy
```

```python
linhas = [[1.0] + linha for linha in x]                                      # coluna de 1
xtx = [[sum(l[i] * l[j] for l in linhas) for j in range(k)] for i in range(k)]  # XᵀX (5×5)
xty = [sum(l[i] * yi for l, yi in zip(linhas, y)) for i in range(k)]          # Xᵀy (5)
```

**2. Resolver o sistema por eliminação de Gauss** (`_resolver_gauss`), com pivoteamento parcial:
- para cada coluna, traz para cima a linha com o maior valor (pivô) e zera os valores abaixo dele;
- depois, calcula β de trás para frente.

Se um pivô ficar praticamente zero, as variáveis são dependentes entre si, e a função avisa que não consegue estimar os coeficientes.

O teste `test_funcao_manual_nao_usa_numpy` roda a função com o NumPy desligado (`minimos_quadrados.np = None`) para provar que ela não depende dele.

## 2. Resultado nos 100 pedidos

| | Manual (Python puro) | `numpy.linalg.lstsq` | Diferença absoluta |
| --- | --- | --- | --- |
| β0 (intercepto) | 3,367269561609 | 3,367269561609 | 2,5 × 10⁻¹⁴ |
| β1 (maior prato) | 0,891427434220 | 0,891427434220 | 7,8 × 10⁻¹⁶ |
| β2 (demais pratos) | 0,354579647048 | 0,354579647048 | 7,8 × 10⁻¹⁶ |
| β3 (fila) | 1,320731243329 | 1,320731243329 | 2,9 × 10⁻¹⁵ |
| β4 (categorias) | 1,027521552643 | 1,027521552643 | 1,6 × 10⁻¹⁴ |
| R² | 0,947167790849 | 0,947167790849 | 0 |
| Maior diferença entre as previsões dos 100 pedidos | | | 7,1 × 10⁻¹⁴ min |

Os dois métodos chegam ao **mesmo modelo**:

```text
ŷ = 3,37 + 0,891 × maior prato + 0,355 × demais pratos + 1,32 × fila + 1,03 × categorias
```

A diferença aparece só da 14ª casa decimal em diante, que é o limite de precisão dos números de ponto flutuante (`float64`), e não tem efeito prático.

Essa tabela é calculada a cada carregamento da página **Análises** (seção "Cálculo manual × numpy.linalg.lstsq") e aparece em `GET /api/analises`, no campo `multipla.comparacao_numpy`. Na página **Novo pedido**, a previsão do pedido digitado também é refeita com os coeficientes do NumPy, e a diferença aparece na tela (`previsao_numpy` e `diferenca_numpy` em `POST /api/prever`).

## 3. Como cada um calcula

### Manual: equações normais + Gauss

Aplica a fórmula do livro, passo a passo. O sistema real tem só 5 equações, uma por coeficiente:

```text
|   100    1 407    3 157    572    275 |   | β0 |   |   3 748,4 |
| 1 407   23 347   55 336  7 872  4 047 |   | β1 |   |  59 726,1 |
| 3 157   55 336  179 437 17 085 10 559 | · | β2 | = | 156 997,5 |
|   572    7 872   17 085  4 886  1 574 |   | β3 |   |  23 071,8 |
|   275    4 047   10 559  1 574    885 |   | β4 |   |  11 265,8 |
```

O primeiro número, 100, é o total de pedidos. Os outros são somas: por exemplo, 1 407 é a soma dos tempos do maior prato de todos os pedidos.

### numpy.linalg.lstsq: decomposição SVD

O `lstsq` não monta XᵀX. Ele decompõe a própria matriz X em valores singulares (SVD) com rotinas da biblioteca de álgebra linear LAPACK, compiladas em C/Fortran, e resolve `X·β ≈ y` diretamente. Também informa o **posto** da matriz: se for menor que 4, há variáveis dependentes.

**Por que dá igual?** Os dois minimizam a mesma ΣE², então chegam aos mesmos β.

**De onde vem a diferença minúscula?** O caminho das contas é diferente, e isso muda o arredondamento nas últimas casas dos cerca de 16 dígitos que o computador guarda.

## 4. Diferenças práticas

| Aspecto | Manual (equações normais) | numpy.linalg.lstsq (SVD) |
| --- | --- | --- |
| Resultado | Mesmo modelo | Mesmo modelo |
| Transparência | Cada passo é visível e corresponde à fórmula | Chama uma rotina pronta |
| Bibliotecas | Nenhuma (Python puro) | NumPy + LAPACK |
| Estabilidade numérica | Boa aqui, mas montar XᵀX "eleva ao quadrado" o mau condicionamento: com variáveis muito parecidas, perde precisão | Muito alta: trabalha direto em X, sem XᵀX |
| Dados problemáticos | Detecta pivô quase zero e lança um erro explicativo | Informa o posto e a matriz é tratada com segurança |
| Escala | Laços em Python ficam lentos com muitos dados | Vetorizado, adequado para grandes volumes |

Neste projeto, o número de condição de XᵀX é cerca de 3 × 10⁴. Isso é baixo: com `float64`, sobram mais de 10 dígitos corretos, como a tabela confirma.

## 5. Quando usar cada um

- **Manual:** mostra e explica o cálculo da regressão múltipla, como o requisito pede.
- **numpy.linalg.lstsq:** confere o resultado e é a escolha prática em código de produção, pela robustez e pela velocidade.

## 6. Como o projeto confere a equivalência

- `comparar_numpy(x, y, nomes)` em [comanda/modelo/minimos_quadrados.py](comanda/modelo/minimos_quadrados.py) roda os dois cálculos e devolve os coeficientes, os dois R² e as diferenças, inclusive a maior diferença entre previsões. O módulo não depende do banco: recebe só as listas X e y. `nomes` rotula os coeficientes (o modelo passa `NOMES_COEFICIENTES`).
- Os testes em [tests/test_admin.py](tests/test_admin.py) verificam:
  - `test_plano_conhecido_e_alvo_constante`: recupera y = 2 + 3a + 4b + 5c exatamente, com R² = 1;
  - `test_manual_confere_com_numpy`: manual e `lstsq` iguais em dados com ruído (diferença < 10⁻⁹);
  - `test_funcao_manual_nao_usa_numpy`: o cálculo manual funciona com o NumPy desligado;
  - `test_variaveis_dependentes_e_amostras_invalidas`: variáveis dependentes e entradas inválidas geram erro;
  - `test_previsoes_residuos_e_metricas`: diferenças abaixo de 10⁻⁹ nos dados reais da aplicação.
- Em [tests/test_projeto.py](tests/test_projeto.py), `test_previsao_aplica_os_coeficientes` confere que a previsão de um pedido novo é igual pelos dois caminhos.

Para reproduzir no terminal:

```powershell
.\.venv\Scripts\python.exe gerenciar.py modelo
```

A saída mostra a fórmula, o R² e as diferenças entre o cálculo manual e o NumPy.
