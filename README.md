# Comanda: previsão do tempo de preparo de pedidos

Aplicação didática em Flask, SQLite e NumPy para um restaurante que quer prever quanto tempo cada pedido leva para ficar pronto e, assim, informar prazos melhores aos clientes. Ela recebe os dados de um pedido (pratos escolhidos e fila da cozinha), calcula o tempo estimado com duas regressões lineares e mostra o resultado com a conta feita.

A base tem 100 pedidos históricos fictícios, um cardápio de 60 pratos em 10 categorias e o tempo real de preparo de cada pedido. Não há cadastro nem autenticação.

## Páginas

- `/`: indicadores, dispersão itens × tempo de preparo com a reta da regressão simples e tabela pesquisável de pedidos.
- `/novo-pedido`: escolha os pratos e a fila da cozinha; a página calcula e exibe o tempo estimado pelas duas regressões.
- `/categorias`: ranking das categorias mais pedidas.
- `/cardapio`: pratos, categorias e em quantos pedidos cada prato aparece.
- `/analises`: regressão simples, comparação do cálculo manual com `numpy.polyfit`, gráficos real × previsto dos dois modelos e agrupamento de categorias.
- `/pedidos/<id>`: dados do pedido, tempo previsto no registro, estimativa para os itens atuais, sugestões de pratos e edição dos itens.
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
| Regressão simples | `tempo = B0 + B1 × itens + E` | Manualmente, pelas fórmulas de mínimos quadrados (`ajustar_simples`) |
| Regressão múltipla | `tempo = β0 + β1 × itens + β2 × fila + β3 × categorias + E` | `numpy.linalg.lstsq` (`ajustar_modelo`) |

Com os dados atuais, a simples explica 45% da variação do tempo (R² = 0,447) e erra em média 5,2 min. A múltipla explica 83% (R² = 0,830) e erra em média 2,8 min, porque também considera a fila da cozinha. O cálculo manual da simples coincide com `numpy.polyfit` até a 15ª casa decimal.

As explicações completas estão em [DOCUMENTACAO.md](DOCUMENTACAO.md) (funcionamento, pesos e comparação dos modelos) e [COMPARACAO_MANUAL_NUMPY.md](COMPARACAO_MANUAL_NUMPY.md) (cálculo manual × `numpy.polyfit`).

## Dados e persistência

Todos os CSVs ficam em `dados/` e são gerados por `preparar_dados.py` com semente fixa (`20261028`), então a base é reproduzível:

- `pedidos.csv`: ID, cliente fictício, pedidos na fila da cozinha e tempo real de preparo em minutos.
- `categorias.csv` e `pratos.csv`: cardápio fixo, com uma categoria por prato.
- `itens_pedido.csv`: pratos de cada pedido (de 1 a 8 por pedido).

O tempo real foi simulado como `6 + 2,2 × itens + 1,3 × fila + 0,8 × categorias`, mais um ajuste por tipo de prato (grelhados e risotos demoram mais; bebidas e sobremesas, menos) e um ruído aleatório. Os modelos não conhecem essa fórmula: eles a reconstroem a partir dos dados.

Na primeira inicialização, `banco.py` cria `restaurante.db` e copia os CSVs em uma transação. Os itens são gravados em duas tabelas: `itens_originais`, uma fotografia fixa usada para treinar as regressões, e `itens_pedido`, que pode ser editada pela interface. Editar um pedido muda as sugestões, os totais e a estimativa para os itens atuais, mas não retreina os modelos. A tabela `migracoes` impede que reinicializações reponham itens removidos.

## API

| Método e rota | Contrato |
| --- | --- |
| `POST /api/prever` | JSON `{"pratos": [25, 26, 37], "pedidos_na_fila": 6}`; devolve `entrada`, `simples`, `multipla` (previsão em minutos, valor bruto e conta) e `avisos` |
| `GET /api/analises` | Modelos simples e múltiplo (com `comparacao_polyfit`) e observações com previsões e resíduos |
| `GET /api/modelo` | Resumo da regressão múltipla: coeficientes, fórmula, R² e intervalos observados |
| `GET /api/pedidos` | Lista de `{id, cliente}` |
| `GET /api/pratos?pedido_id=1` | Cardápio com categoria e `incluido` booleano para o pedido |
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
