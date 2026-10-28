# Como o StreamData foi implementado

## 1. Objetivo e arquitetura

O projeto começou como uma demonstração de regressão linear simples sobre horas na plataforma e horas assistidas. A versão atual tem duas funcionalidades independentes: recomendar títulos ainda não vistos e demonstrar regressão linear múltipla para estimar engajamento.

Os usuários, títulos e gêneros são fixos. Selecionar um nome na interface troca o perfil consultado; não é login. A única alteração de dados disponível pela interface é marcar ou desmarcar um conteúdo como visto.

O backend usa Flask para HTTP, SQLite para persistência e NumPy para operações numéricas. O frontend é HTML, CSS e JavaScript sem framework e sem processo de build. Não há serviço externo de IA nem modelo de linguagem no recomendador.

```mermaid
flowchart LR
    CSV[CSVs em dados/] -->|Primeira carga| DB[(SQLite)]
    UI[Interface] -->|Selecionar perfil e consultar| API[Flask]
    UI -->|Marcar ou desmarcar| API
    API -->|Persistir vistos| DB
    DB -->|Histórico atual| REC[Recomendação híbrida]
    DB -->|Histórico inicial e horas| REG[Regressão múltipla]
    REC --> API
    REG --> API
    API -->|JSON| UI
```

## 2. Arquivos de dados

O diretório [dados/](../dados/) contém todos os CSVs. Os quatro arquivos ativos usam cabeçalho, vírgula como separador e UTF-8; IDs são inteiros e horas usam ponto decimal.

| Arquivo | Colunas | Finalidade |
| --- | --- | --- |
| `dataset_streaming.csv` | `usuario_id,nome,tempo_plataforma_horas,tempo_assistindo_horas` | 100 usuários; IDs e horas originais, com nomes fictícios |
| `generos.csv` | `genero_id,nome` | 10 gêneros |
| `conteudos.csv` | `conteudo_id,titulo,genero_id` | 60 títulos; um gênero principal por título |
| `historico_inicial.csv` | `usuario_id,conteudo_id` | Relações de conteúdos vistos na amostra inicial |
| `Dataset Streaming(Planilha1).csv` | `Usuário,Tempo de uso (X),Tempo assistindo (Y)` | Referência original; não é lida pela aplicação |

`banco.DIRETORIO_DADOS` centraliza o caminho, calculado com `Path(__file__).resolve().parent / 'dados'`. O gerador também usa essa constante. O diretório corrente do terminal não define a localização dos CSVs.

### Geração demonstrativa

`preparar_dados.py` lê os IDs e horas do dataset existente, produz nomes e histórico e sobrescreve apenas os CSVs de usuários e histórico; o catálogo de filmes e os gêneros são preservados. Não é executado automaticamente. Não gera os dados originais de horas do zero.

A semente `20261027` torna a geração reproduzível com a mesma entrada. Cada usuário com histórico recebe de 3 a 17 títulos distintos. Três conjuntos de preferências aumentam o peso de seleção de determinados gêneros: peso 9 dentro da preferência e 0,4 fora dela. Os IDs 20, 40, 60, 80 e 100 começam sem histórico.

Esses conjuntos servem apenas para fabricar uma amostra com padrões. Os clusters exibidos na aplicação são calculados pelo consumo e não copiam diretamente esses conjuntos.

## 3. Banco e inicialização

| Tabela | Dados e relações |
| --- | --- |
| `usuarios` | ID, nome e as duas medidas de horas |
| `generos` | ID e nome |
| `conteudos` | ID, título e chave estrangeira para gênero |
| `visualizacoes` | Histórico editável; chave composta `(usuario_id, conteudo_id)` |
| `historico_inicial` | Cópia inicial dos vistos, usada pela regressão |
| `migracoes` | Versões de carga aplicadas; atualmente versões 1 e 2 |

A tabela antiga `engajamento`, quando presente, é preservada, mas não alimenta os cálculos atuais.

`app.criar_app()` chama `inicializar_banco()`. O módulo também cria `app` ao ser importado, garantindo inicialização no uso via WSGI. A criação de tabelas usa `CREATE TABLE IF NOT EXISTS`. Em seguida, `BEGIN IMMEDIATE` serializa a carga: quando a versão 1 ainda não existe, os CSVs são inseridos, os vistos são copiados para as duas tabelas de histórico e a versão é registrada na mesma transação.

Em próximas inicializações, a versão 1 impede recarga dos históricos. A versão 2 atualiza títulos e gêneros pelos mesmos IDs, usando os 60 filmes selecionados da lista do usuário. Ela preserva os pares de ambos os históricos; a mudança de gênero pode alterar os coeficientes da regressão, pois o gênero é consultado no catálogo atual. Portanto, alterações nos CSVs não atualizam automaticamente um banco já carregado. Isso evita restaurar um conteúdo desmarcado ou apagar novas marcações.

As conexões habilitam chaves estrangeiras e retornam `sqlite3.Row`. A classe `Conexao` fecha a conexão ao sair do bloco `with`, depois do commit ou rollback, evitando arquivos presos no Windows.

Marcar um conteúdo usa `INSERT OR IGNORE`; desmarcar usa `DELETE` pelo par de IDs. Repetir qualquer operação mantém o mesmo resultado: são operações idempotentes.

## 4. Recomendação passo a passo

As funções ficam em [recomendacao.py](../recomendacao.py). Os cálculos são refeitos nas consultas; não há treinamento persistido ou cache de ranking.

### Matrizes e perfis

- `M[u,c]`: 1 se o usuário `u` viu o conteúdo `c`, senão 0.
- `C[u,g]`: quantidade de conteúdos do gênero `g` vistos por `u`.
- `P[u,g]`: `C[u,g] / soma(C[u,:])`, ou zero quando o histórico está vazio.

Exemplo: um usuário com três títulos de ação e um de aventura tem perfil proporcional de 0,75 para ação e 0,25 para aventura. Os IDs são mapeados para índices; não é necessário que ID e posição na matriz coincidam.

### Proximidade de gêneros

Cada gênero é representado pela coluna de `C`, isto é, suas contagens de consumo entre todos os usuários. A similaridade é:

```text
cos(a,b) = produto_escalar(a,b) / (norma(a) × norma(b))
distância(a,b) = 1 − cos(a,b)
```

Vetores nulos produzem similaridade zero. O código limita resultados ao intervalo de 0 a 1 para eliminar desvios numéricos. Gêneros ficam próximos quando suas contagens entre usuários seguem padrões proporcionais; não é uma análise semântica dos nomes dos gêneros.

### Agrupamento hierárquico

Cada gênero começa sozinho. `agrupar()` calcula a média das distâncias de todos os pares entre dois grupos e une o par com a menor média. O processo termina com três grupos. Empates são resolvidos pelas tuplas de IDs dos grupos.

A API também retorna, para cada gênero, todos os outros ordenados por distância e ID. A ordenação usa as distâncias originais entre gêneros. Pertencer ao mesmo cluster não é requisito para receber uma recomendação.

### Afinidade por gênero e usuários semelhantes

A afinidade de um título é:

```text
A(u,c) = soma, para cada gênero g, de P[u,g] × similaridade(g, gênero(c))
```

A comparação entre usuários usa cosseno de seus perfis `P`. São escolhidos até cinco vizinhos com similaridade positiva, excluindo o próprio usuário. Empates seguem o ID do usuário.

O componente colaborativo é:

```text
B(u,c) = soma(similaridade(u,v) × M[v,c]) / soma(similaridade(u,v))
          para os vizinhos v selecionados
```

Usuários podem ser semelhantes por consumirem os mesmos gêneros mesmo sem terem visto os mesmos títulos. Já a contribuição colaborativa depende de o vizinho ter visto exatamente o título candidato.

### Ranking e exceções

| Situação | Pontuação |
| --- | --- |
| Histórico e vizinhos válidos | `0,5 × A + 0,5 × B` |
| Histórico, sem vizinhos válidos | `A` |
| Sem histórico | Número de usuários que viram o título dividido pelo total de usuários |

Exemplo ilustrativo: afinidade 0,8 e componente colaborativo 0,6 resultam em pontuação 0,7. Isso não significa 70% de chance de gostar.

Títulos vistos são sempre excluídos. O ranking ordena por pontuação decrescente, popularidade decrescente e ID crescente, retornando até dez itens. Se todo o catálogo já foi visto, a lista fica vazia. Candidatos sem afinidade ainda podem aparecer ao completar a lista, com explicação de exploração do catálogo.

Cada item informa afinidade, componente colaborativo, popularidade, pontuação final e motivos. Os motivos citam o gênero com maior contribuição ou os vizinhos que realmente viram o título; usuários sem histórico recebem explicação por popularidade.

## 5. Regressão linear múltipla

[regressao.py](../regressao.py) implementa uma análise separada. Ela não calcula a ordem das recomendações.

```text
y = β0 + β1 × horas_na_plataforma
       + β2 × quantidade_vistos
       + β3 × quantidade_generos
```

O alvo `y` são as horas assistidas originais. As contagens vêm de `historico_inicial`, com junções à esquerda para manter usuários sem histórico. A matriz de projeto tem quatro colunas: intercepto e três variáveis. `numpy.linalg.lstsq` calcula os coeficientes por mínimos quadrados.

O ajuste exige pelo menos quatro observações, valores finitos e posto 4. Posto insuficiente significa que não há independência suficiente para estimar os quatro coeficientes. O resumo sinaliza indisponibilidade nesses casos.

`R² = 1 − soma_dos_resíduos² / soma_dos_desvios_do_alvo²`. Quando o alvo é constante, retorna `null` em JSON. É uma medida do ajuste na própria amostra, não uma avaliação com usuários novos.

A previsão informa o valor bruto e um valor para exibição limitado entre zero e as horas na plataforma. Há avisos quando ocorre limitação ou alguma entrada fica fora dos intervalos observados. As contagens são históricas e as horas são diárias; não se assume duração de cada filme nem consumo de todos os filmes em um dia.

## 6. API e fluxo de interação

| Rota | Entrada | Saída principal |
| --- | --- | --- |
| `GET /` | Nenhuma | HTML da interface |
| `GET /api/usuarios` | Nenhuma | Lista com `id` e `nome` |
| `GET /api/conteudos` | Query `usuario_id` inteira | Catálogo com gênero e `visto` booleano |
| `GET /api/usuarios/<id>/recomendacoes` | ID do usuário | `usuario`, `sem_historico`, `recomendacoes`, `usuarios_semelhantes` |
| `GET /api/clusters` | Nenhuma | `grupos` e `generos`, com vizinhos ordenados em `proximos` |
| `PUT /api/usuarios/<id>/vistos/<conteudo_id>` | `{"visto": true}` ou `{"visto": false}` | IDs e estado confirmado |
| `GET /api/modelo` | Nenhuma | Disponibilidade, amostra, fórmula, coeficientes, R² e intervalos |
| `POST /api/prever` | Três variáveis | `previsao_horas`, `previsao_bruta`, `formula`, `avisos` |

Exemplo de entrada para previsão:

```json
{"tempo_plataforma": 4, "quantidade_vistos": 10, "quantidade_generos": 3}
```

Entradas inválidas retornam 400, IDs não encontrados nas rotas de consulta/marcação retornam 404 e modelo indisponível ao prever retorna 422. Os erros tratados usam `{"erro": "mensagem"}`. Rotas inexistentes seguem o tratamento padrão do Flask.

Horas precisam ser finitas, maiores que zero e no máximo 24. Contagens precisam ser inteiras e não negativas, limitadas ao catálogo; gêneros não podem superar a quantidade de vistos. Com vistos positivos, a quantidade de gêneros também deve ser positiva. A API aceita números ou strings numéricas para a previsão, mas rejeita booleanos; `visto` exige booleano JSON real.

## 7. Frontend

`templates/index.html` fornece a estrutura. `static/style.css` define o tema claro, cards, filtros e layouts responsivos. `static/script.js` faz as consultas com `fetch`, escapa os textos antes de montar HTML e mantém o estado de navegação no navegador.

As abas são **Para você**, **Catálogo**, **Já assistidos** e **Análises**. Elas usam `hidden`, papéis ARIA, seleção explícita e navegação por setas, Home e End. O catálogo tem busca por título sem diferença de maiúsculas ou acentos, filtro de gênero e filtro de vistos. A filtragem é local sobre os 60 títulos já recebidos.

Os cards deixam os motivos em uma seção expansível. Perfis semelhantes também ficam recolhidos inicialmente. Clusters e regressão permanecem disponíveis na aba Análises.

Ao trocar usuário, catálogo, recomendações e clusters são consultados. Um contador de requisições descarta respostas antigas quando há trocas rápidas. Durante o carregamento, as ações de marcação ficam bloqueadas.

Ao marcar/desmarcar, o frontend envia o `PUT`, espera a confirmação e recarrega os dados. Assim, não anuncia uma marcação antes de o banco confirmá-la. O foco de teclado é restaurado para um controle disponível e mensagens de status usam regiões acessíveis. O backend continua sendo a fonte de verdade do histórico.

## 8. Limites da demonstração

Não há autenticação, cadastro, notas, reprodução de vídeo ou avaliação de satisfação. A marcação é um sinal implícito de consumo. Títulos têm somente um gênero principal. Similaridades e clusters refletem os padrões sintéticos desta base.

Os cálculos em memória e a recomputação a cada consulta atendem ao catálogo pequeno, mas não foram projetados para escala de produção. A aplicação usa servidor de desenvolvimento ao executar `app.py`. A regressão não foi validada em uma amostra externa, e as horas originais não foram geradas a partir dos históricos novos.
