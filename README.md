# StreamData — recomendação híbrida e regressão múltipla

Aplicação didática em Flask, SQLite e NumPy. O painel Admin apresenta a visão geral de consumo e as regressões simples e múltipla. Explore os 100 perfis fictícios, 60 títulos e 10 gêneros; abra um perfil para consultar previsões, recomendações e editar seu histórico. Não há cadastro nem autenticação.

## Navegação

- `/`: indicadores globais, dispersão com reta de regressão simples e tabela pesquisável de usuários.
- `/categorias`: ranking global de gêneros por marcações atuais.
- `/catalogo`: títulos, gêneros e audiência, com busca e filtro.
- `/analises`: regressões, comparação observado × previsto, métricas, simulador múltiplo e clusters.
- `/usuarios/<id>`: dados individuais, estimativas, histórico inicial e atual, recomendações e marcação de títulos.
- `/regressao`: redireciona para a regressão em Análises.

Os gráficos SVG funcionam sem serviços externos. Os pontos abrem os perfis e seus valores também estão disponíveis em tabela. R² e erro absoluto médio descrevem o ajuste na própria amostra. As marcações atualizam o consumo atual, mas não retreinam as regressões baseadas nas horas originais e no histórico inicial. `GET /api/analises` expõe os dois modelos e as observações com previsões brutas e resíduos (observado menos previsto); as APIs anteriores continuam disponíveis.

## Documentação

Comece pelo [índice de documentação](docs/README.md). O [guia de implementação](docs/implementacao.md) explica os dados, algoritmos, API e interface. O [guia de manutenção para humanos e IA](docs/manutencao.md) reúne os pontos de alteração, invariantes e verificações.

## Executar

Crie o ambiente virtual e instale as dependências na primeira execução:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Depois, inicie a aplicação:

```powershell
.\.venv\Scripts\python.exe app.py
```

Acesse http://127.0.0.1:5000. Em um ambiente novo, crie um virtualenv e instale `pip install -r requirements.txt` antes de iniciar.

## Dados e persistência

O catálogo contém 60 filmes reais selecionados da lista fornecida pelo usuário, com ano no título e um gênero principal definido para esta demonstração. Usuários e históricos continuam sintéticos. A migração 2 substitui títulos e gêneros mantendo os IDs e os dois históricos. As marcações passam a representar os novos títulos; mudanças de gênero podem alterar clusters e coeficientes da regressão.

- `dados/dataset_streaming.csv`: IDs originais, nomes fictícios e as horas originais preservadas.
- `dados/generos.csv` e `dados/conteudos.csv`: catálogo fixo; um gênero principal por título.
- `dados/historico_inicial.csv`: histórico demonstrativo fixo, com sobreposição entre perfis. Usuários 20, 40, 60, 80 e 100 começam sem histórico.
- `dados/Dataset Streaming(Planilha1).csv`: planilha original de referência, não utilizada na carga da aplicação.

Todos os CSVs ficam em `dados/`. Os caminhos são resolvidos a partir do diretório do código, independentemente da pasta de execução. O banco `streaming.db` continua na raiz, preservando o histórico existente.

A primeira inicialização cria as tabelas e copia os CSVs em uma transação. A tabela `migracoes` impede que reinicializações restaurem conteúdos desmarcados ou apaguem novas marcações. A tabela antiga `engajamento`, se existir, é preservada. O histórico inicial fica em uma tabela separada para a regressão. A aplicação também inicializa corretamente quando importada por um servidor WSGI.

`preparar_dados.py` gera nomes e históricos sintéticos (semente 20261027), lendo o catálogo atual e preservando `conteudos.csv` e `generos.csv`. Não é executado pela aplicação e não altera o banco. Uma nova geração usa os gêneros atuais e pode diferir do histórico antigo. Alterações futuras nos CSVs exigem uma nova migração para atualizar bancos já carregados. Não exclua o banco se quiser preservar o histórico.

## Como as recomendações funcionam

1. A matriz usuário × conteúdo registra visto/não visto. Contagens por gênero formam perfis de consumo; as proporções são usadas para comparar usuários.
2. A similaridade entre gêneros é o cosseno dos seus vetores de contagens por usuário. Distância = 1 − similaridade. Gêneros sem consumo têm similaridade zero com os demais.
3. O agrupamento hierárquico começa com um grupo por gênero e une o par com menor distância média, até restarem três grupos. Empates seguem IDs. Os grupos auxiliam a leitura; não bloqueiam sugestões entre grupos.
4. A afinidade de um conteúdo é a média da similaridade de seu gênero com os gêneros assistidos, ponderada pelo consumo do usuário.
5. Os cinco usuários com maior similaridade positiva de perfil são os vizinhos. A pontuação colaborativa é a fração ponderada desses vizinhos que viu o conteúdo.
6. O ranking combina 50% afinidade e 50% colaboração. Sem vizinhos, usa apenas afinidade. Sem histórico, usa popularidade (usuários que viram / total de usuários).
7. Exclui vistos, desempata por popularidade e ID e retorna até dez títulos. A pontuação não é probabilidade. As explicações indicam os sinais observados.

As marcações recalculam perfis, grupos e recomendações da base. Não há avaliação de satisfação: assistir é apenas um sinal implícito, e o agrupamento reflete esta amostra sintética.

## Regressão linear múltipla

Análise independente do recomendador: `horas assistidas = intercepto + b1 × horas na plataforma + b2 × conteúdos vistos + b3 × gêneros distintos`.

Os coeficientes são ajustados por `numpy.linalg.lstsq` sobre os 100 usuários e a fotografia inicial. Alterações em `visualizacoes` não alteram esse treinamento. O resumo informa coeficientes, R² e intervalos observados. Amostras insuficientes e matrizes sem posto completo desabilitam a previsão com uma mensagem. R² é indefinido quando a variável alvo não varia.

As contagens são históricas e as horas são diárias: a demonstração não assume duração por título nem que os títulos foram vistos em um único dia. As horas originais não foram produzidas pelo novo histórico; os coeficientes adicionais não garantem ganho preditivo. R² mede ajuste na própria amostra, não validação fora dela.

A API devolve a estimativa bruta e uma estimativa de exibição limitada entre zero e as horas na plataforma, avisando quando há limitação ou extrapolação.

## API

| Método e rota | Contrato |
| --- | --- |
| `GET /api/usuarios` | Lista de `{id, nome}` |
| `GET /api/conteudos?usuario_id=1` | Lista com ID, título, gênero, `genero_id` e `visto` booleano |
| `GET /api/usuarios/1/recomendacoes` | Usuário, indicador sem histórico, recomendações com pontuações/motivos e usuários semelhantes |
| `GET /api/clusters` | Três grupos e gêneros com vizinhos ordenados por distância |
| `PUT /api/usuarios/1/vistos/2` | JSON `{"visto": true}` ou `{"visto": false}`; idempotente |
| `GET /api/modelo` | Disponibilidade, amostra, coeficientes, intercepto, fórmula, R² e intervalos |
| `POST /api/prever` | JSON `{"tempo_plataforma": 4, "quantidade_vistos": 10, "quantidade_generos": 3}` |

Entradas inválidas retornam 400; IDs inexistentes, 404; modelo indisponível ao prever, 422. As APIs de regressão agora exigem três variáveis e substituem o contrato antigo de regressão simples.

## Validação e utilitários

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe consultar_banco.py
.\.venv\Scripts\python.exe regressao.py
```

Os testes usam bancos temporários e cobrem ranking, clusters, persistência, isolamento, validação da API e regressão. `popular_banco.py` e `banco.py` inicializam sem sobrescrever o histórico já salvo.
