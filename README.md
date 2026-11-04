# Comanda: previsão do tempo de preparo de pedidos

Aplicação didática em Flask, SQLite e NumPy para um restaurante que quer prever quanto tempo cada pedido leva para ficar pronto e, assim, informar prazos melhores aos clientes. Ela recebe os dados de um pedido (pratos escolhidos e fila da cozinha), calcula o tempo estimado com duas regressões lineares e mostra o resultado com a conta feita.

A base tem 100 pedidos históricos fictícios, um cardápio de 60 pratos em 10 categorias, cada um com seu tempo individual de preparo, e o tempo real de preparo de cada pedido. Não há cadastro nem autenticação.

**Para estudar ou apresentar o trabalho, comece pelo [Guia didático](GUIA_DIDATICO.md).**

## Páginas

- `/`: indicadores, dispersão tempo dos pratos × tempo de preparo com a reta da regressão simples e tabela pesquisável de pedidos.
- `/novo-pedido`: escolha os pratos (cada um mostra seu tempo de preparo) e a fila da cozinha; o resumo soma o tempo base dos pratos, e a página calcula e exibe o tempo estimado pelas duas regressões.
- `/categorias`: ranking das categorias mais pedidas.
- `/cardapio`: pratos, categorias, tempo de preparo de cada prato e em quantos pedidos ele aparece.
- `/analises`: regressão simples, comparação do cálculo manual com `numpy.polyfit` (coeficientes, R² e previsões), gráficos real × previsto dos dois modelos e agrupamento de categorias.
- `/pedidos/<id>`: dados do pedido (incluindo o tempo base dos pratos), tempo previsto no registro, estimativa para os itens atuais, sugestões de pratos e edição dos itens.
- `/regressao`: redireciona para a regressão em Análises.

## Executar

Na primeira execução, crie o ambiente virtual e instale as dependências:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Depois, inicie a aplicação e acesse http://127.0.0.1:5000:

```powershell
.\.venv\Scripts\python.exe app.py
```

## Os modelos

| Modelo | Fórmula | Como é calculado |
| --- | --- | --- |
| Regressão simples | `tempo = B0 + B1 × tempo dos pratos + E` | Manualmente, em Python puro, pelas fórmulas de mínimos quadrados (`ajustar_simples`); conferida com `numpy.polyfit` |
| Regressão múltipla | `tempo = β0 + β1 × tempo dos pratos + β2 × fila + β3 × categorias + E` | `numpy.linalg.lstsq` (`ajustar_modelo`) |

O **tempo dos pratos** é a soma dos tempos individuais de preparo dos pratos do pedido. Assim, uma água (1 min) não pesa o mesmo que um risoto (22 min).

Com os dados atuais, a simples (`ŷ = 17,66 + 0,437 × tempo dos pratos`) explica 84% da variação do tempo (R² = 0,843) e erra em média 5,1 min. A múltipla explica 96% (R² = 0,960) e erra em média 2,5 min, porque também considera a fila da cozinha. O B1 de 0,437, bem menor que 1, mostra que a cozinha trabalha em paralelo. O cálculo manual da simples coincide com `numpy.polyfit` até a 15ª casa decimal.

As explicações completas estão em [DOCUMENTACAO.md](DOCUMENTACAO.md) (funcionamento, pesos e comparação dos modelos) e [COMPARACAO_MANUAL_NUMPY.md](COMPARACAO_MANUAL_NUMPY.md) (cálculo manual × `numpy.polyfit`).

## Dados e persistência

Todos os CSVs ficam em `dados/` e são gerados por `preparar_dados.py` com semente fixa (`20261028`), então a base é reproduzível:

- `pedidos.csv`: ID, cliente fictício, pedidos na fila da cozinha e tempo real de preparo em minutos.
- `categorias.csv` e `pratos.csv`: cardápio fixo, com uma categoria e o tempo individual de preparo (`tempo_prato_min`) de cada prato.
- `itens_pedido.csv`: pratos de cada pedido (de 1 a 8 por pedido).

O tempo real foi simulado considerando que a cozinha prepara os pratos em paralelo: `3 + maior tempo + 0,35 × (soma dos tempos − maior tempo) + 1,3 × fila + 0,8 × categorias`, mais um ruído aleatório. Os modelos não conhecem essa fórmula: eles a aproximam a partir dos dados.

Na primeira inicialização, `banco.py` cria `restaurante.db` e copia os CSVs em uma transação. A migração 2 acrescenta o tempo dos pratos e os novos tempos reais a bancos já existentes, sem tocar nos itens editados. Os itens são gravados em duas tabelas: `itens_originais`, uma fotografia fixa usada para treinar as regressões, e `itens_pedido`, que pode ser editada pela interface. Editar um pedido muda as sugestões, os totais e a estimativa para os itens atuais, mas não retreina os modelos. A tabela `migracoes` impede que reinicializações reponham itens removidos.

## API

| Método e rota | Contrato |
| --- | --- |
| `POST /api/prever` | JSON `{"pratos": [25, 26, 37], "pedidos_na_fila": 6}`; devolve `entrada` (tempo dos pratos, fila e categorias), `quantidade_itens`, `simples` (previsão, conta e conferência com `numpy.polyfit`), `multipla` (previsão em minutos, valor bruto e conta) e `avisos` |
| `GET /api/analises` | Modelos simples e múltiplo (com `comparacao_polyfit`) e observações com previsões e resíduos |
| `GET /api/modelo` | Resumo da regressão múltipla: coeficientes, fórmula, R² e intervalos observados |
| `GET /api/pedidos` | Lista de `{id, cliente}` |
| `GET /api/pratos?pedido_id=1` | Cardápio com categoria, `tempo_prato_min` e `incluido` booleano para o pedido |
| `GET /api/pedidos/1/sugestoes` | Sugestões de pratos com pontuações e motivos, e pedidos semelhantes |
| `GET /api/clusters` | Três grupos de categorias e proximidades |
| `PUT /api/pedidos/1/itens/2` | JSON `{"incluido": true}` ou `{"incluido": false}`; idempotente |

Entradas inválidas retornam 400; IDs inexistentes, 404; modelos indisponíveis ao prever, 422.

## Testes e utilitários

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe regressao.py         # fórmulas, R² e comparação com polyfit
.\.venv\Scripts\python.exe consultar_banco.py   # pedidos, itens e tempos
.\.venv\Scripts\python.exe preparar_dados.py    # regenera os CSVs (não altera um banco existente)
```

Os testes usam bancos temporários e cobrem o cálculo manual, a comparação com `numpy.polyfit`, a previsão, a validação da API, as sugestões, os agrupamentos e a persistência.

Mais detalhes em [docs/](docs/README.md).
