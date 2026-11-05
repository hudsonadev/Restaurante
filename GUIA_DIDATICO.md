# Guia didático: o Comanda em versão simples

> *Um restaurante quer saber, assim que um pedido chega, quanto tempo ele vai levar para ficar pronto.*

Este guia explica o projeto do jeito mais direto possível, na ordem em que você o apresentaria. Para os detalhes técnicos, veja a [documentação completa](DOCUMENTACAO.md).

---

## Em uma frase

Usamos **100 pedidos antigos** para ensinar uma **regressão linear múltipla** a prever o tempo de preparo a partir de quatro informações do pedido. A conta é feita **à mão, em Python puro**, e conferida com o NumPy. Em pedidos que nunca viu, o modelo erra **cerca de 3 minutos**: **76% menos** do que chutar sempre o tempo médio.

---

## 1. Os dados

Cada pedido tem os pratos escolhidos, quantos pedidos estavam na fila da cozinha e **quanto tempo levou de verdade**. Cada prato do cardápio tem seu próprio tempo de preparo: um refrigerante leva 1 min, uma lasanha 18 min, um risoto 22 min.

O modelo olha quatro coisas em cada pedido:

| Variável | O que é | Exemplo: Espaguete (12) + Lasanha (18) + Picanha (20), fila de 6 |
| --- | --- | --- |
| **Maior prato** | o tempo do prato mais demorado | 20 min |
| **Demais pratos** | a soma dos outros | 12 + 18 = 30 min |
| **Fila** | pedidos na frente | 6 |
| **Categorias** | tipos de prato diferentes | 2 (massa e grelhado) |

**Por que separar o maior prato dos outros?** Porque a cozinha faz os pratos **ao mesmo tempo**. Quem define a hora em que o pedido fica pronto é o prato mais demorado; os outros só acrescentam um pouco.

**Os dados são inventados** (sintéticos), gerados por uma regra que imita uma cozinha. Essa regra tem uma parte aleatória, o **ruído**: equipe do turno, forno atrasado, horário de pico. É importante dizer isso ao apresentar.

---

## 2. A regressão, feita à mão

O modelo é uma soma com pesos:

```text
tempo = β0 + β1 × maior prato + β2 × demais pratos + β3 × fila + β4 × categorias
```

Os **pesos (β)** são escolhidos para que a soma dos erros ao quadrado seja a menor possível. Esse é o **método dos mínimos quadrados**.

Como achamos os pesos:

1. **Montamos uma tabela de somas** com os 100 pedidos (quantos pedidos, soma dos tempos, soma dos tempos × fila…). Essa tabela vira um sistema de **5 equações com 5 incógnitas** (os cinco β), chamado de equações normais.
2. **Resolvemos o sistema por escalonamento** (eliminação de Gauss), como se faz no papel: zeramos o que fica abaixo da diagonal e achamos os β de trás para frente.

### Um exemplo pequeno, para conferir de cabeça

Quatro pedidos, só com tempo de prato (t) e fila (f), que seguem exatamente `y = 10 + 0,5·t + 1·f`:

| Pedido | t | f | y |
| --- | --- | --- | --- |
| A | 10 | 0 | 15 |
| B | 20 | 2 | 22 |
| C | 30 | 1 | 26 |
| D | 40 | 3 | 33 |

```text
Equações normais:          4·β0 +  100·β1 +   6·β2 =   96
                         100·β0 + 3000·β1 + 190·β2 = 2690
                           6·β0 +  190·β1 +  14·β2 =  169

Escalonando:             500·β1 + 40·β2 = 290   e   40·β1 + 5·β2 = 25
                         1,8·β2 = 1,8  →  β2 = 1  →  β1 = 0,5  →  β0 = 10
```

Os pesos usados para criar os dados voltam exatos. Com dados reais há ruído, então o resultado é o melhor ajuste possível, não um ajuste perfeito.

### Conferindo com o NumPy

O mesmo ajuste é feito com `numpy.linalg.lstsq`, que usa outro método (decomposição SVD). Os dois chegam aos **mesmos pesos**; a diferença só aparece na 14ª casa decimal, por arredondamento do computador. A página **Análises** mostra essa comparação lado a lado.

---

## 3. O resultado

```text
tempo = 3,37 + 0,89 × maior prato + 0,35 × demais pratos + 1,32 × fila + 1,03 × categorias
```

Cada peso vale **com as outras variáveis paradas**:

- **0,89 (maior prato):** cada minuto do prato mais demorado soma quase um minuto inteiro.
- **0,35 (demais pratos):** cada minuto dos outros soma só uns 21 segundos, porque eles são feitos junto. É a marca do paralelismo.
- **1,32 (fila):** cada pedido na frente soma cerca de 1 min 20 s.
- **1,03 (categorias):** cada tipo de prato diferente soma cerca de 1 minuto.
- **3,37:** tempo fixo de qualquer pedido (receber, montar, entregar).

**Exemplo:** o pedido #1 tem só um Creme de cebola (7 min), com 9 pedidos na fila.

```text
3,37 + 0,89 × 7 + 0,35 × 0 + 1,32 × 9 + 1,03 × 1 = 22,5 min previstos      real: 27,0 min      erro: 4,5 min
```

---

## 4. O modelo é bom?

| Medida | Valor | Em palavras |
| --- | --- | --- |
| **R²** | 0,947 | As quatro variáveis explicam 95% da diferença de tempo entre os pedidos |
| **Erro médio em pedidos novos** | 3,0 min | Um prazo informado ao cliente erra uns 3 minutos |
| **Redução de erro** | 76% | Frente a chutar sempre o tempo médio (12,3 min de erro) |

O "erro em pedidos novos" é medido com **validação cruzada**: treinamos com 90 pedidos, testamos nos 10 que ficaram de fora e repetimos até testar todos.

O erro que sobra é o **ruído**: o que não foi registrado não pode ser previsto. Para melhorar, seria preciso registrar mais coisas, como o número de cozinheiros e o horário.

**Cuidados:** os dados são sintéticos; associação não é causa; fora da faixa observada (por exemplo, fila acima de 12) a previsão é uma extrapolação, e o sistema avisa.

---

## 5. O site

1. **Novo pedido:** você marca os pratos e o tempo estimado aparece na hora, com a conta feita.
2. **Enviar para a cozinha:** o pedido vai para a **Cozinha** com a previsão daquele momento.
3. **Cozinha:** um cronômetro acelerado (1 segundo = 2 minutos) corre até o tempo real, que a cozinha simulada decide. Aí o botão **Pronto** libera.
4. **Análises:** mostra quanto o modelo errou nesses pedidos novos (**previsão × realidade**), o gráfico real × previsto, a comparação manual × NumPy e os pesos, que você pode editar.

Os pedidos novos **não entram no treino**: são o teste mais honesto do modelo.

---

## 6. Rodar

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py                              # abre em http://127.0.0.1:5000
.\.venv\Scripts\python.exe -B -m unittest discover -s tests    # testes automáticos
.\.venv\Scripts\python.exe gerenciar.py modelo                 # fórmula, R² e manual × NumPy no terminal
```

Onde está cada coisa no código:

| Arquivo | O que faz |
| --- | --- |
| [comanda/modelo/minimos_quadrados.py](comanda/modelo/minimos_quadrados.py) | A regressão à mão e a conferência com o NumPy |
| [comanda/modelo/previsao.py](comanda/modelo/previsao.py) | Treina com os 100 pedidos e prevê um pedido novo |
| [comanda/cozinha.py](comanda/cozinha.py) | O cardápio e a regra que gerou os tempos |
| [comanda/web/](comanda/web/) | As páginas e a API |

---

## Perguntas que podem aparecer

**Por que regressão linear?** O alvo é um número (minutos), a relação é aproximadamente linear e cada peso tem um significado direto.

**Por que fazer à mão se o NumPy já faz?** Para mostrar de onde vêm os números. A comparação com o NumPy prova que a conta manual está certa.

**Por que o maior prato pesa 0,89 e os outros só 0,35?** Porque a cozinha prepara os pratos ao mesmo tempo.

**Por que não chegar a 90%?** O ruído foi calibrado para um nível realista de cozinha. Um modelo correto bate nesse limite; passar dele exigiria registrar o que hoje é ruído.
