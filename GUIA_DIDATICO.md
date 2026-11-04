# Guia didático: prevendo o tempo de preparo com regressão linear

**Comanda: previsão do tempo de preparo de pedidos**

> *Um restaurante quer saber, assim que um pedido chega, quanto tempo ele vai levar para ficar pronto, para informar um prazo realista ao cliente e organizar a cozinha.*

Este guia explica o projeto do começo ao fim, na ordem em que você o apresentaria.

| Tema | Seção |
| --- | --- |
| Como os dados estão organizados e por que são coerentes | [1. Organização dos dados](#1-organização-dos-dados) |
| Regressão simples feita à mão | [2. Regressão simples](#2-regressão-simples-feita-à-mão) |
| O mesmo cálculo com NumPy | [3. Manual × numpy.polyfit](#3-o-mesmo-cálculo-com-numpypolyfit) |
| Regressão múltipla | [4. Regressão múltipla](#4-regressão-múltipla) |
| Como interpretar os resultados | [5. Interpretação](#5-como-interpretar-os-resultados) |
| A página web | [6. A página web](#6-a-página-web) |
| Como executar e testar | [7. Executar e testar](#7-como-executar-e-testar) |

Os números deste guia foram calculados sobre o banco atual. A página `/analises` sempre mostra os valores mais recentes.

---

## A resposta em uma frase

Organizamos **100 pedidos** com seus pratos, a fila da cozinha e o tempo real de preparo. Cada prato do cardápio tem seu **tempo individual de preparo**. Com isso, ajustamos duas regressões lineares:

- uma **simples**, que usa só o **tempo dos pratos** (a soma dos tempos individuais), calculada à mão e conferida com o `numpy.polyfit`;
- uma **múltipla**, que também considera a fila e as categorias.

Na página web, o atendente escolhe os pratos, informa a fila e vê a previsão dos dois modelos, com a conta feita.

---

## 1. Organização dos dados

### 1.1 O que queremos prever

| Papel | Variável | Unidade |
| --- | --- | --- |
| **Alvo (Y)** | `tempo_preparo`: tempo real até o pedido ficar pronto | minutos |
| X da simples e X₁ da múltipla | `tempo_base_itens`: **tempo dos pratos**, a soma dos tempos individuais dos pratos do pedido | minutos |
| X₂ | `pedidos_na_fila`: pedidos já na fila quando este chegou | contagem |
| X₃ | `quantidade_categorias`: categorias diferentes no pedido (massa + bebida = 2) | contagem |

### 1.2 As tabelas

```text
pedidos                    pratos                       categorias
──────────────────         ────────────────────         ──────────
id                         id                           id
cliente                    nome                         nome
pedidos_na_fila            categoria_id  ──────────────►
tempo_preparo_min  (Y)     tempo_prato_min  (tempo de cada prato)
        ▲                          ▲
        │                          │
        └──── itens_originais ─────┘   (pratos de cada pedido no registro: treina os modelos)
              itens_pedido             (cópia editável pela interface: sugestões e totais)
```

### 1.3 O tempo de cada prato

Cada prato recebeu um tempo de preparo conforme a complexidade:

| Categoria | Faixa (min) | Exemplos |
| --- | --- | --- |
| Bebidas | 1–4 | Água com gás 1, Café expresso 2, Limonada suíça 4 |
| Sobremesas | 2–7 | Pudim 2, Brownie com sorvete 5, Petit gâteau 7 |
| Saladas | 4–7 | Salada verde 4, Caesar 6, Quinoa 7 |
| Sopas | 6–9 | Sopa de legumes 6, Caldo verde 8, Canja 9 |
| Entradas | 6–11 | Carpaccio 6, Bolinho de bacalhau 10, Croquete 11 |
| Lanches | 6–11 | Misto quente 6, X-burger 10, Hambúrguer vegetariano 11 |
| Porções | 9–15 | Calabresa 9, Batata frita 10, Frango a passarinho 15 |
| Massas | 11–18 | Penne ao pesto 11, Espaguete 12, Lasanha 18 |
| Grelhados | 14–22 | Linguiça 14, Picanha 20, Costela suína 22 |
| Risotos | 19–22 | Limão-siciliano 19, Cogumelos 20, Camarão 22 |

### 1.4 Da tabela às variáveis do modelo

O modelo precisa de **uma linha por pedido**. A consulta SQL agrupa os pratos de cada pedido:

```sql
SELECT p.id,
       p.tempo_preparo_min                    AS tempo_preparo,          -- Y
       COUNT(i.prato_id)                      AS quantidade_itens,       -- só exibida
       COALESCE(SUM(c.tempo_prato_min), 0)    AS tempo_base_itens,       -- X
       p.pedidos_na_fila,                                                -- X2
       COUNT(DISTINCT c.categoria_id)         AS quantidade_categorias   -- X3
FROM pedidos p
LEFT JOIN itens_originais i ON i.pedido_id = p.id
LEFT JOIN pratos c          ON c.id = i.prato_id
GROUP BY p.id
```

Exemplo de pedido com Espaguete (12 min), Lasanha (18 min) e Picanha (20 min):

```text
tempo dos pratos = 12 + 18 + 20 = 50 min       categorias = 2 (Massas e Grelhados)
```

**Por que o tempo dos pratos, e não a quantidade de itens?** Contar itens trata 1 água com gás (1 min) igual a 1 risoto de camarão (22 min). Somar os tempos dá a cada prato o peso que ele tem na cozinha. Com os mesmos dados, a simples com X = itens explica só 35% da variação; com X = tempo dos pratos, explica 84%.

### 1.5 De onde vêm os dados, com honestidade

Os pedidos são **sintéticos**, gerados por [preparar_dados.py](preparar_dados.py) com semente fixa (sempre os mesmos dados). A regra imita uma cozinha real, que prepara os pratos **em paralelo**:

```text
cozinha    = maior tempo + 0,35 × (soma dos tempos − maior tempo)
tempo real = 3 + cozinha + 1,3 × fila + 0,8 × categorias + ruído aleatório
```

O prato mais demorado define a base, e cada prato a mais acrescenta só 35% do próprio tempo, porque é feito ao mesmo tempo que os outros.

**Os modelos não conhecem essa regra.** Eles usam a soma dos tempos, que é só uma aproximação do paralelismo. Ainda assim, a relação foi construída por nós ao gerar os dados. É importante dizer isso ao apresentar.

### 1.6 Checagens de coerência

| Regra | Situação |
| --- | --- |
| Cada pedido tem de 1 a 8 pratos, sem repetir | ✅ |
| Todo prato tem tempo entre 1 e 22 min | ✅ |
| Fila entre 0 e 12 pedidos | ✅ |
| Tempo real mínimo de 3 min | ✅ (o menor é 8,4 min) |
| Pedidos com 2 ou mais pratos levam menos do que levariam com os pratos feitos um de cada vez | ✅ nos 85 pedidos (efeito do paralelismo) |

Nos pedidos de **1 prato** o paralelismo não ajuda. Em 7 deles, o ruído aleatório deixa o tempo real alguns minutos acima dessa conta, como acontece em qualquer cozinha num dia mais lento.

---

## 2. Regressão simples, feita à mão

### 2.1 O modelo

A ideia é traçar a **reta** que melhor passa pelos pontos (tempo dos pratos, tempo real):

```text
Y = B0 + B1·X + E
```

| Símbolo | Significado |
| --- | --- |
| B0 | **Intercepto**: tempo fixo de um pedido (recepção, montagem, entrega) |
| B1 | **Inclinação**: minutos a mais no pedido por minuto de prato |
| E | **Erro (resíduo)**: real − previsto |

"Melhor reta" significa a que deixa a **menor soma dos erros ao quadrado** (ΣE²). Esse é o método dos **mínimos quadrados**. Os erros são elevados ao quadrado para que os positivos não cancelem os negativos e para que erros grandes pesem mais.

### 2.2 As fórmulas

```text
x̄ = Σxi / n            ȳ = Σyi / n

B1 = Σ(xi − x̄)(yi − ȳ)  /  Σ(xi − x̄)²

B0 = ȳ − B1 · x̄
```

**Como entender B1:** o numerador mede o quanto X e Y variam *juntos*, e o denominador mede o quanto X varia *sozinho*.

### 2.3 Exemplo resolvido no papel

Cinco pedidos fictícios:

| Pedido | x (tempo dos pratos) | y (tempo real) | x − x̄ | y − ȳ | (x − x̄)(y − ȳ) | (x − x̄)² |
| --- | --- | --- | --- | --- | --- | --- |
| A | 10 | 22 | −20 | −9 | 180 | 400 |
| B | 20 | 25 | −10 | −6 | 60 | 100 |
| C | 30 | 32 | 0 | 1 | 0 | 0 |
| D | 40 | 34 | 10 | 3 | 30 | 100 |
| E | 50 | 42 | 20 | 11 | 220 | 400 |
| **Σ** | 150 | 155 | | | **490** | **1000** |

```text
x̄ = 150/5 = 30          ȳ = 155/5 = 31
B1 = 490 / 1000 = 0,49
B0 = 31 − 0,49 × 30 = 16,3
ŷ  = 16,3 + 0,49·x
```

Erros (y − ŷ): 0,8; −1,1; 1,0; −1,9; 1,2. **A soma dá zero.** Isso sempre acontece com mínimos quadrados quando o modelo tem intercepto, e serve como conferência.

```text
R² = 1 − ΣE² / Σ(y − ȳ)² = 1 − 7,9 / 248 = 0,968
```

### 2.4 Como está no código

A função `ajustar_simples` em [regressao.py](regressao.py) faz exatamente essas contas, **em Python puro, sem nenhuma biblioteca**: só listas, `sum` e laços `for`. O teste `test_funcao_manual_nao_usa_numpy` roda a função com o NumPy desligado para provar isso.

```python
media_x = sum(x) / n
media_y = sum(y) / n
for xi, yi in zip(x, y):
    sxy += (xi - media_x) * (yi - media_y)
    sxx += (xi - media_x) ** 2
b1 = sxy / sxx
b0 = media_y - b1 * media_x
```

### 2.5 Resultado com os 100 pedidos

```text
ŷ = 17,66 + 0,437 × tempo dos pratos          R² = 0,843
```

- **B1 = 0,437:** cada minuto de prato acrescenta só **26 segundos** ao pedido. Um B1 bem menor que 1 é a **marca do paralelismo**: se a cozinha fizesse um prato de cada vez, B1 seria perto de 1.
- **B0 = 17,66:** tempo fixo de um pedido. Na simples, ele também absorve a fila média da cozinha (cerca de 6 pedidos), que esse modelo não enxerga.

---

## 3. O mesmo cálculo com numpy.polyfit

### 3.1 Como o NumPy resolve

`np.polyfit(x, y, 1)` ajusta um polinômio de grau 1, ou seja, uma reta. Ele não usa a fórmula de B1: monta uma matriz e resolve um sistema de álgebra linear com rotinas compiladas (LAPACK). Atenção: ele devolve `[B1, B0]`, nessa ordem.

```python
b1, b0 = np.polyfit(x, y, 1)
```

### 3.2 Comparação lado a lado

A página `/analises` mostra esta tabela na seção **"Cálculo manual × numpy.polyfit"**:

| | Manual (Python puro) | numpy.polyfit | Diferença |
| --- | --- | --- | --- |
| B0 | 17,655643096137 | 17,655643096137 | 3,6 × 10⁻¹⁵ |
| B1 | 0,436861457140 | 0,436861457140 | 2,2 × 10⁻¹⁶ |
| R² | 0,842769825957 | 0,842769825957 | 0 |
| Maior diferença entre previsões | | | 4,3 × 10⁻¹⁴ min |

**Por que dá igual?** Os dois minimizam a mesma ΣE², então chegam à mesma reta.

**De onde vem a diferença minúscula?** O computador guarda números com cerca de 16 dígitos (`float64`). Fazer as contas numa ordem diferente muda o arredondamento na última casa. Não há nenhum efeito prático.

A página **Novo pedido** também confere a previsão de cada pedido digitado pelos dois caminhos.

### 3.3 Quando usar cada um

| | Manual | numpy.polyfit |
| --- | --- | --- |
| Para que serve | Entender e mostrar o cálculo | Conferir e trabalhar com muitos dados |
| Bibliotecas | Nenhuma | NumPy |
| Número de variáveis | Só uma | Só uma também |

Para **várias variáveis**, nenhum dos dois serve. Por isso a regressão múltipla usa `numpy.linalg.lstsq`. Mais detalhes estão em [COMPARACAO_MANUAL_NUMPY.md](COMPARACAO_MANUAL_NUMPY.md).

---

## 4. Regressão múltipla

### 4.1 O modelo

```text
Y = β0 + β1·tempo dos pratos + β2·fila + β3·categorias + E
```

A matriz agora tem quatro colunas, `[1, tempo dos pratos, fila, categorias]`, e o `numpy.linalg.lstsq` encontra os β que minimizam ΣE² (`ajustar_modelo` em [regressao.py](regressao.py)). O código confere o **posto** da matriz: se uma variável for constante ou combinação das outras, o modelo avisa que não consegue separar os efeitos.

A quantidade de itens **não** entra: ela anda junto com o tempo dos pratos (correlação de 0,66), e mantê-la deixaria seu coeficiente negativo (−1,3 min por item) e sem interpretação.

### 4.2 Resultado

```text
ŷ = 9,02 + 0,447 × tempo dos pratos + 1,32 × fila + 0,24 × categorias        R² = 0,960
```

### 4.3 Lendo cada coeficiente

A regra de ouro da regressão múltipla: **cada β mede o efeito da sua variável quando as outras ficam paradas**.

- **β1 = 0,447 (tempo dos pratos):** cada minuto de prato soma cerca de 27 segundos, quase o mesmo que na simples. O tempo dos pratos não depende da fila, então separar os efeitos quase não mudou esse valor.
- **β2 = 1,32 (fila):** cada pedido na frente soma cerca de 1 min 20 s. É a informação que faltava à simples.
- **β3 = 0,24 (categorias):** cada categoria diferente soma cerca de 15 segundos, um efeito pequeno.
- **β0 = 9,02:** tempo fixo de um pedido, agora sem a fila embutida.

### 4.4 Exemplo: o pedido #1

Ana Almeida pediu só um Creme de cebola (7 min), com 9 pedidos na fila, e esperou 25,2 min.

```text
Simples:  ŷ = 17,66 + 0,437 × 7                         = 20,7 min   erro = 25,2 − 20,7 = 4,5 min
Múltipla: ŷ = 9,02 + 0,447 × 7 + 1,32 × 9 + 0,24 × 1    = 24,2 min   erro = 25,2 − 24,2 = 1,0 min
```

A simples não sabe da fila de 9 pedidos e subestima. A múltipla leva a fila em conta e chega bem perto do real.

---

## 5. Como interpretar os resultados

### 5.1 R² (coeficiente de determinação)

```text
R² = 1 − ΣE² / Σ(yi − ȳ)²
```

O R² compara o modelo com o palpite mais simples possível: **prever sempre o tempo médio** para todo pedido.

- **R² = 0:** o modelo não é melhor do que chutar a média.
- **R² = 1:** o modelo acerta todos os pedidos.
- **R² = 0,843 (simples):** o tempo dos pratos explica **84%** da diferença de tempo entre os pedidos.
- **R² = 0,960 (múltipla):** as três variáveis explicam **96%**.

### 5.2 R² ajustado

Acrescentar variáveis **nunca diminui** o R², mesmo que sejam inúteis. O R² ajustado desconta o número de variáveis:

```text
R² ajustado = 1 − (1 − R²) × (n − 1) / (n − p − 1)        n = 100 pedidos, p = nº de variáveis
```

### 5.3 Erros em minutos

- **EAM (erro absoluto médio):** em média, quanto o prazo informado ao cliente erraria.
- **RMSE (raiz do erro quadrático médio):** parecido com o EAM, mas pesa mais os erros grandes.
- **Maior erro:** a pior previsão individual.

### 5.4 Comparação final

| Métrica | Simples | Múltipla | Quem vence |
| --- | --- | --- | --- |
| R² | 0,843 | **0,960** | Múltipla |
| R² ajustado | 0,841 | **0,959** | Múltipla, então as variáveis extras compensam |
| EAM | 5,1 min | **2,5 min** | Múltipla |
| RMSE | 6,1 min | **3,1 min** | Múltipla |
| Maior erro | 13,7 min | **7,0 min** | Múltipla |

E o ganho de trocar "quantidade de itens" por "tempo dos pratos", com os mesmos pedidos:

| Modelo | Com quantidade de itens | Com tempo dos pratos |
| --- | --- | --- |
| Simples | R² = 0,345 | **R² = 0,843** |
| Múltipla | R² = 0,429 | **R² = 0,960** |

**Conclusão:**
1. O **tempo dos pratos** é o que mais pesa: sozinho, explica 84% da variação.
2. A **fila da cozinha** é a segunda informação mais importante. Com ela, o erro médio cai de 5 para 2,5 minutos.
3. A variedade de categorias quase não importa.
4. Para informar prazos aos clientes, o restaurante deve usar a **regressão múltipla**.

### 5.5 O limite do modelo: o paralelismo

O pedido #12 tem 8 pratos que somam 72 min, mas o maior deles leva só 13 min.

```text
Real:      37,0 min
Simples:   49,1 min   → erro de −12,1 min
Múltipla:  43,7 min   → erro de −6,7 min
```

Muitos pratos rápidos somam bastante, mas ficam prontos quase juntos, então o modelo linear superestima esse tipo de pedido. Para capturar isso, seria preciso uma variável como "maior tempo entre os pratos". Fica como melhoria futura, porque a regressão simples pedida usa uma única variável.

### 5.6 Cuidados ao interpretar

1. **As métricas foram medidas nos próprios dados de treino.** Elas mostram o ajuste, não o acerto com pedidos novos. Para isso seria preciso separar dados de teste.
2. **Associação não é causa.** Um coeficiente alto não prova que uma variável *provoca* a outra.
3. **Os dados são sintéticos.** A regra de geração (seção 1.5) define as relações. Com dados reais, o R² tende a ser menor.
4. **Extrapolação é arriscada.** Fora da faixa observada (2 a 145 min de pratos, fila de 0 a 12, 1 a 5 categorias), a reta pode dar valores sem sentido. O sistema avisa quando isso acontece.

---

## 6. A página web

### 6.1 Fluxo

```text
Atendente marca pratos ─► JavaScript envia JSON ─► Flask valida e soma ─► regressao.py calcula ─► JSON de volta ─► página mostra
  (/novo-pedido)          (novo_pedido.js)          os tempos (app.py)     (prever_tempo)
```

1. **Recebe os dados:** em `/novo-pedido`, cada prato aparece com seu tempo de preparo. Ao marcar as caixas, o resumo soma o **"Tempo base dos pratos"** na hora.
2. **Calcula a previsão:** o navegador envia `POST /api/prever`:
   ```json
   {"pratos": [25, 26, 37], "pedidos_na_fila": 6}
   ```
   O servidor busca os tempos dos pratos (12 + 18 + 20 = 50 min), conta as categorias (2) e aplica os dois modelos.
3. **Exibe o resultado:**

   ```text
   39,7 min — tempo estimado de preparo pela regressão múltipla
   Tempo base dos pratos: 50 min (3 itens)

   Regressão múltipla   9,02 + 0,45 × 50,0 + 1,32 × 6 + 0,24 × 2 = 39,7 min
   Regressão simples    17,66 + 0,44 × 50,0 = 39,5 min
   Regressão simples conferida: manual 39,4987 min × numpy.polyfit 39,4987 min (diferença 1,4e-14)
   ```

### 6.2 Validação das entradas

O servidor rejeita entradas inválidas com o código 400:

| Regra | Por quê |
| --- | --- |
| Pelo menos um prato | Pedido vazio não tem tempo |
| Pratos existentes no cardápio, sem repetir | Cada prato aparece uma vez por pedido |
| Fila inteira entre 0 e 50 | Não existe meio pedido nem fila negativa |

### 6.3 Outras páginas

| Página | O que mostra |
| --- | --- |
| `/` | Visão geral, gráfico da reta simples e tabela de pedidos |
| `/cardapio` | Pratos, categoria, **tempo de preparo** e em quantos pedidos aparecem |
| `/analises` | Reta simples, tabela manual × polyfit, gráficos real × previsto dos dois modelos e agrupamentos |
| `/pedidos/<id>` | Tempo base dos pratos, previsão e erro de cada modelo, sugestões e edição dos itens |

---

## 7. Como executar e testar

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py                              # abre em http://127.0.0.1:5000
.\.venv\Scripts\python.exe -B -m unittest discover -s tests    # 25 testes automáticos
```

Alguns testes ligados às regressões:

| Teste | O que garante |
| --- | --- |
| `test_reta_conhecida_e_alvo_constante` | A reta de pontos perfeitos (y = 2 + 3x) é recuperada exatamente |
| `test_funcao_manual_nao_usa_numpy` | O cálculo manual funciona sem NumPy |
| `test_calculo_manual_confere_com_numpy` / `test_comparacao_polyfit` | Manual e polyfit dão o mesmo B0, B1 e R² |
| `test_tempo_dos_pratos` | Cada prato tem seu tempo, e a soma por pedido está certa |
| `test_previsao_aplica_os_coeficientes` | A previsão de um pedido novo aplica os coeficientes, igual nos dois caminhos |
| `test_migracao_2_atualiza_banco_antigo` | Um banco antigo recebe os tempos sem perder itens editados |
| `test_validacao_api` | Entradas inválidas são rejeitadas |

### Mapa dos arquivos principais

| Arquivo | Papel |
| --- | --- |
| [regressao.py](regressao.py) | As duas regressões, a comparação com o polyfit e a previsão |
| [app.py](app.py) | Rotas, validação e soma dos tempos dos pratos |
| [banco.py](banco.py) | Criação do banco e migrações |
| [preparar_dados.py](preparar_dados.py) | Tempos dos pratos e geração dos pedidos |
| [templates/novo_pedido.html](templates/novo_pedido.html), [static/novo_pedido.js](static/novo_pedido.js) | Formulário do pedido e soma em tempo real |

---

## 8. Perguntas que podem aparecer

**Por que regressão linear?** Porque o alvo é um número contínuo (minutos), a relação com o tempo dos pratos é aproximadamente uma reta, e cada coeficiente tem um significado direto.

**Por que fazer à mão se o NumPy já faz?** Para mostrar que sabemos de onde vêm os números. A comparação com o polyfit prova que a implementação manual está correta.

**Por que B1 é 0,44, e não 1?** Porque a cozinha prepara vários pratos ao mesmo tempo. Se fizesse um de cada vez, cada minuto de prato somaria um minuto ao pedido.

**O R² de 0,96 é bom demais?** Os dados são sintéticos, e a regra de geração usa as mesmas variáveis do modelo. Com dados reais, o esperado é um R² menor.

**O que fazer para melhorar?** Incluir o maior tempo entre os pratos (que define o paralelismo), o número de cozinheiros e o horário, e validar com pedidos que não foram usados no treino.
