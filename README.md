# Comanda: previsão do tempo de preparo de pedidos

Aplicação didática em Flask, SQLite e NumPy para um restaurante que quer prever quanto tempo cada pedido leva para ficar pronto e, assim, informar prazos melhores aos clientes. Ela recebe os dados de um pedido (pratos escolhidos e fila da cozinha), calcula o tempo estimado com uma regressão linear múltipla e mostra o resultado com a conta feita.

A base tem 100 pedidos históricos fictícios, um cardápio de 60 pratos em 10 categorias, cada um com seu tempo individual de preparo, e o tempo real de preparo de cada pedido. Não há cadastro nem autenticação.

**Para estudar ou apresentar o trabalho, comece pelo [Guia didático](GUIA_DIDATICO.md)**, a versão simples. A versão completa está em [DOCUMENTACAO.md](DOCUMENTACAO.md).

## Páginas

O menu é organizado por tarefa, em três grupos: **Operação** (Início, Novo pedido, Cozinha), **Modelo** (Análises) e **Referência** (Cardápio, Histórico).

- `/` **Início**: atalhos para criar um pedido e abrir a cozinha, os pedidos em preparo agora (com cronômetro), como o modelo está indo (erro no histórico e em pedidos novos) e o índice das páginas.
- `/novo-pedido` **Novo pedido**: marque os pratos (cada um mostra seu tempo) e o tempo estimado aparece **ao vivo**. A fila já vem preenchida com os pedidos em preparo. A conta do modelo fica em "Como calculamos". Um único botão, **Enviar para a cozinha**, leva à Cozinha com o pedido destacado.
- `/cozinha` **Cozinha**: só a operação. Pedidos em preparo: a cozinha sorteia o tempo real no envio (mesma regra do histórico), um cronômetro acelerado mostra o andamento e o botão **Pronto** libera quando o pedido fica pronto para sair. Abaixo, os concluídos recentemente e **Simular 10 pedidos**.
- `/analises` **Análises**: desempenho do modelo (gráfico real × previsto, com os pedidos novos), **previsão × realidade**, coeficientes (editáveis), cálculo manual × `numpy.linalg.lstsq` e agrupamento de categorias.
- `/cardapio` **Cardápio**: pratos com o tempo de preparo de cada um e o ranking das categorias mais pedidas.
- `/historico` **Histórico**: os 100 pedidos de treino, com previsão e resíduo; cada um abre `/pedidos/<id>`.
- `/pedidos/<id>`: dados do pedido, tempo previsto no registro, estimativa para os itens atuais, sugestões de pratos e edição dos itens.
- `/categorias`: o ranking de categorias em página própria (o mesmo do Cardápio).
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

## O modelo

```text
tempo = β0 + β1 × maior prato + β2 × demais pratos + β3 × fila + β4 × categorias + E
```

A regressão múltipla é calculada **à mão, em Python puro** (`ajustar_modelo_manual`: equações normais resolvidas por eliminação de Gauss) e conferida com `numpy.linalg.lstsq` (`ajustar_modelo`), em [comanda/modelo/](comanda/modelo/).

Cada prato tem seu tempo de preparo. Como a cozinha trabalha em paralelo, o modelo separa o **maior prato** (o mais demorado, que define quando o pedido fica pronto) dos **demais pratos** (que só acrescentam uma parte do próprio tempo).

Com os dados atuais (`ŷ = 3,37 + 0,891 × maior prato + 0,355 × demais pratos + 1,32 × fila + 1,03 × categorias`), o modelo explica 95% da variação do tempo (R² = 0,947). Em pedidos que não viu, erra em média 3,0 min: **75,8% menos erro** que prever sempre o tempo médio, dentro do alvo de 75–76% do projeto. O cálculo manual coincide com o NumPy até a 14ª casa decimal. Os β podem ser substituídos por valores próprios em Análises → Coeficientes do modelo, e há um botão para voltar aos calculados.

As explicações completas estão em [DOCUMENTACAO.md](DOCUMENTACAO.md) (funcionamento, pesos e avaliação do modelo) e [COMPARACAO_MANUAL_NUMPY.md](COMPARACAO_MANUAL_NUMPY.md) (cálculo manual × `numpy.linalg.lstsq`).

## Dados e persistência

Todos os CSVs ficam em `dados/` e são gerados por `gerenciar.py dados` ([comanda/dados.py](comanda/dados.py)) com semente fixa (`20261028`), então a base é reproduzível:

- `pedidos.csv`: ID, cliente fictício, pedidos na fila da cozinha e tempo real de preparo em minutos.
- `categorias.csv` e `pratos.csv`: cardápio fixo, com uma categoria e o tempo individual de preparo (`tempo_prato_min`) de cada prato.
- `itens_pedido.csv`: pratos de cada pedido (de 1 a 8 por pedido).

O tempo real foi simulado considerando que a cozinha prepara os pratos em paralelo: `3 + maior tempo + 0,35 × (soma dos tempos − maior tempo) + 1,3 × fila + 0,8 × categorias`, mais um ruído aleatório com desvio de 3,7 min, calibrado para o alvo de 75–76% de redução de erro. O modelo não conhece essa fórmula: eles a aproximam a partir dos dados.

Na primeira inicialização, [comanda/migracoes.py](comanda/migracoes.py) cria `restaurante.db` e copia os CSVs em uma transação. As migrações 2 e 3 acrescentam o tempo dos pratos e os tempos reais atuais a bancos já existentes, sem tocar nos itens editados. Os itens são gravados em duas tabelas: `itens_originais`, uma fotografia fixa usada para treinar a regressão, e `itens_pedido`, que pode ser editada pela interface. Editar um pedido muda as sugestões, os totais e a estimativa para os itens atuais, mas não retreina o modelo. A tabela `migracoes` impede que reinicializações reponham itens removidos.

## API

| Método e rota | Contrato |
| --- | --- |
| `POST /api/prever` | JSON `{"pratos": [25, 26, 37], "pedidos_na_fila": 6}`; devolve `entrada` (maior prato, demais pratos, fila e categorias), `tempo_base_itens`, `quantidade_itens`, `multipla` (previsão em minutos, valor bruto, conta e conferência com o NumPy) e `avisos` |
| `GET /api/analises` | Modelo `multipla` (com `comparacao_numpy`) e observações com previsões e resíduos |
| `POST /api/acompanhados` | Mesmo JSON de `/api/prever`; grava o pedido com a previsão atual e o horário (201) |
| `POST /api/acompanhados/simular` | JSON `{"quantidade": 10}` (1 a 50); cria e conclui pedidos sorteados como os do histórico |
| `POST /api/acompanhados/1/pronto` | Marca o pedido como pronto e calcula o tempo real e o erro (409 se já estiver pronto) |
| `GET /api/acompanhados` | Pedidos em preparo, concluídos e métricas (erro absoluto médio e viés) |
| `GET /api/coeficientes` | β calculados, β em uso, se estão personalizados e os dois R² |
| `PUT /api/coeficientes` | JSON com os cinco β (`intercepto`, `tempo_maior_prato`, `tempo_demais_pratos`, `pedidos_na_fila`, `quantidade_categorias`); passam a valer em todo o sistema |
| `DELETE /api/coeficientes` | Volta aos β calculados |
| `GET /api/modelo` | Resumo da regressão múltipla: coeficientes, fórmula, R² e intervalos observados |
| `GET /api/pedidos` | Lista de `{id, cliente}` |
| `GET /api/pratos?pedido_id=1` | Cardápio com categoria, `tempo_prato_min` e `incluido` booleano para o pedido |
| `GET /api/pedidos/1/sugestoes` | Sugestões de pratos com pontuações e motivos, e pedidos semelhantes |
| `GET /api/clusters` | Três grupos de categorias e proximidades |
| `PUT /api/pedidos/1/itens/2` | JSON `{"incluido": true}` ou `{"incluido": false}`; idempotente |

Entradas inválidas retornam 400; IDs inexistentes, 404; modelo indisponível ao prever, 422. Os erros vêm como `{"erro": "mensagem"}`.

## Código

```text
app.py            inicia o servidor (chama comanda.criar_app)
gerenciar.py      tarefas de terminal
comanda/
  db.py, migracoes.py         SQLite, esquema e migrações
  cozinha.py, dados.py        regra sintética da cozinha e geração dos CSVs
  modelo/                     regressão manual × NumPy, β personalizados e previsão
  acompanhamento.py           pedidos enviados à Cozinha (previsão × realidade)
  recomendacao.py             sugestões de pratos e agrupamento de categorias
  web/                        páginas, API, validação das entradas e filtros dos templates
```

O mapa completo e onde mexer em cada caso estão em [docs/](docs/README.md).

## Testes e utilitários

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
.\.venv\Scripts\python.exe gerenciar.py modelo        # fórmula, R² e comparação manual × NumPy
.\.venv\Scripts\python.exe gerenciar.py consultar     # pedidos, itens e tempos
.\.venv\Scripts\python.exe gerenciar.py inicializar   # cria o banco ou aplica migrações pendentes
.\.venv\Scripts\python.exe gerenciar.py dados         # regenera os CSVs (não altera um banco existente)
.\.venv\Scripts\python.exe gerenciar.py resetar       # reset completo: apaga restaurante.db e recria dos CSVs (pare o servidor antes; --sim pula a confirmação)
```

Os 31 testes usam bancos temporários e cobrem o cálculo manual, a comparação com `numpy.linalg.lstsq`, a previsão, a validação da API, as sugestões, os agrupamentos e a persistência.

Mais detalhes em [docs/](docs/README.md).
