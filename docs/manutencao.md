# Guia de manutenção para humanos e IA

## Antes de alterar

Leia [a implementação](implementacao.md) e confira o código atual. Esta documentação explica o projeto; não substitui requisitos novos nem instruções do usuário.

Verifique `git status --short` para distinguir alterações existentes das suas. Preserve `restaurante.db` e os itens editados ao realizar tarefas de código ou documentação.

## Onde mexer

| Necessidade | Local principal | Pontos relacionados |
| --- | --- | --- |
| Alterar leitura dos CSVs ou caminhos | `comanda/db.py` (`DIRETORIO_DADOS`, `CAMINHO_BANCO`) | `comanda/dados.py` grava no mesmo diretório |
| Alterar tabelas ou carga | `comanda/migracoes.py` (`ESQUEMA`, `MIGRACOES`) | Nova versão de migração para bancos existentes |
| Alterar o cálculo da regressão | `comanda/modelo/minimos_quadrados.py`, `ajustar_modelo_manual()` | `comparar_numpy()`, testes em `tests/test_admin.py` e `COMPARACAO_MANUAL_NUMPY.md` |
| Alterar variáveis do modelo | `comanda/modelo/variaveis.py` (`VARIAVEIS`, `ROTULOS`, `variaveis_do_pedido`) | `carregar_observacoes()` em `modelo/previsao.py`, colunas de `pedidos_acompanhados`, `observacoes.html` |
| Alterar a estimativa de um pedido | `comanda/modelo/previsao.py`, `prever_tempo()` | `renderEstimativa` em `static/common.js` |
| Alterar β personalizados | `comanda/modelo/coeficientes.py` | `web/validacao.ler_coeficientes` (limites) e `static/analises.js` |
| Alterar a regra da cozinha | `comanda/cozinha.py` (`tempo_real`, `CARDAPIO`) | Vale para o histórico (`dados.py`) e para a Cozinha (`acompanhamento.py`) |
| Alterar a Cozinha (relógio, Pronto, simulação) | `comanda/acompanhamento.py` | `static/cozinha.js`, `templates/cozinha.html` |
| Alterar sugestões ou vizinhos | `comanda/recomendacao.py`, `recomendar()` | Motivos exibidos e testes de pontuação |
| Alterar agrupamentos | `comanda/recomendacao.py`, `agrupar()` e `obter_clusters()` | `static/analises.js` |
| Alterar uma página | `comanda/web/paginas.py` | Template correspondente em `templates/` |
| Alterar a API | `comanda/web/api.py` | `static/*.js` e testes |
| Alterar validação de entradas | `comanda/web/validacao.py` | Mensagens exibidas pelo frontend |
| Alterar filtros dos templates | `comanda/web/formatacao.py` | `numero`, `cientifico`, `data_hoje` |
| Alterar visual | `templates/`, `static/style.css` | IDs usados pelos scripts, acessibilidade e estados de carregamento |
| Nova tarefa de terminal | `gerenciar.py` (`COMANDOS`) | |
| Regenerar a base | `python gerenciar.py dados` | Sobrescreve todos os CSVs; não atualiza um banco existente |

Cada página carrega só os scripts que usa. `common.js` é carregado em todas.

## Regras que preservam o comportamento

1. **Respeitar as camadas.**
   - Só `comanda/web/` importa o Flask.
   - `modelo/minimos_quadrados.py` não acessa o banco.
   - Módulos de baixo (`db`, `migracoes`, `cozinha`, `modelo`) não importam `web`.
2. Manter `ajustar_modelo_manual` como cálculo manual em Python puro (equações normais + eliminação de Gauss), sem NumPy, `lstsq` ou outra função pronta de regressão. O NumPy entra só na conferência (`comparar_numpy`). O teste `test_funcao_manual_nao_usa_numpy` garante isso.
3. Calcular `β0 + Σ βi·xi` só com `modelo.variaveis.aplicar`, para que R², análises e previsões nunca divirjam.
4. Manter as quatro variáveis do modelo: maior prato, demais pratos (a partir de `pratos.tempo_prato_min`), fila e categorias. Ao mudar variáveis ou o gerador, conferir `test_reducao_de_erro_calibrada` (alvo de 74–78% de redução de erro em pedidos novos).
5. Com `coeficientes_personalizados` preenchida, os β dela valem em todo o sistema (`obter_resumo_modelo`); a comparação manual × NumPy (`comparacao_numpy`) sempre usa os calculados.
6. **Não usar `pedidos_acompanhados` no treino:** eles são o teste independente da página Cozinha.
   - O tempo real depende de `acompanhamento.MODO_TEMPO`:
     - `simulado` (padrão): o tempo é sorteado no envio por `cozinha.tempo_real`, a mesma regra do histórico. O pedido é liberado quando o relógio acelerado `ACELERACAO_SIMULACAO` alcança esse tempo; antes disso, `marcar_pronto` recusa com `AindaEmPreparo`.
     - `relogio`: o tempo é o intervalo entre o envio e o clique.
   - O relógio fica em `acompanhamento.agora()`, que os testes substituem.
7. Treinar a regressão com `itens_originais`, nunca com `itens_pedido`: o tempo real registrado corresponde aos itens originais.
8. Manter previsões brutas nos gráficos e resíduos; limitar a zero só na exibição da estimativa.
9. Não sugerir pratos já incluídos no pedido nem usar o próprio pedido como vizinho.
10. Manter desempates determinísticos (pontuação, popularidade e ID).
11. Não apresentar a pontuação das sugestões como probabilidade.
12. Não repor os itens a cada inicialização. Mudanças de esquema ou de dados fixos em bancos existentes exigem uma nova versão em `MIGRACOES`; a atual é a 3.
13. Ao mudar `comanda/dados.py` ou `comanda/cozinha.sortear_pratos`, manter a ordem dos sorteios se os itens dos pedidos não devem mudar. As migrações 2 e 3 recusam rodar se os itens originais diferirem dos CSVs.
14. Validar no backend (`web/validacao.py`), mesmo que os controles HTML já imponham limites. Entrada inválida lança `EntradaInvalida`, que a API converte em 400.
15. Descartar respostas antigas no frontend (contador `requisicao`).

## Executar e testar

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Testes:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node --check static/novo_pedido.js
```

O segundo comando só é necessário ao alterar JavaScript e requer Node.js. Os testes redirecionam `comanda.db.CAMINHO_BANCO` para bancos temporários, então não modificam `restaurante.db`.

### O que os testes cobrem

- Cálculo manual com plano conhecido, alvo constante, variáveis dependentes e amostras inválidas, inclusive com o NumPy desligado (`minimos_quadrados.np = None`).
- Igualdade com `numpy.linalg.lstsq` em dados com ruído e nos dados reais (coeficientes, R² e previsões).
- Redução de erro em pedidos novos dentro da faixa-alvo (validação cruzada).
- Tempo individual dos pratos: valores no banco, em `/api/pratos` e nas páginas, e soma correta por pedido.
- Migrações 2 e 3 sobre um banco antigo, preservando itens editados; reset completo de volta aos CSVs.
- Previsão aplicando os coeficientes, extrapolação e modelo indisponível; β personalizados e retorno aos calculados.
- Cozinha: modo relógio, modo simulado com a regra da cozinha, pedidos antigos sem tempo sorteado e simulação em lote comparável ao histórico.
- Validação de `POST /api/prever` (lista vazia, repetida, inexistente, booleanos, fila fora da faixa).
- Sugestões: exclusão de itens, determinismo, pedido vazio, sem vizinhos e contribuição colaborativa conhecida.
- Cosseno, ligação média e agrupamentos com resultados conhecidos.
- Persistência, idempotência e isolamento das edições; edições não retreinam o modelo.
- Rotas, ranking de categorias e base vazia.

### Conferência manual da interface

1. Em **Novo pedido**:
   - conferir o tempo ao lado de cada prato e a estimativa ao vivo a cada caixa marcada;
   - abrir "Como calculamos" e conferir a conta e a linha de conferência com o NumPy;
   - testar fila acima de 12 (aviso de extrapolação) e conferir que "Enviar" fica desabilitado sem pratos.
2. Enviar para a cozinha. Conferir que a Cozinha abre com o pedido destacado, que o cronômetro corre e que **Pronto** libera ao fim.
3. Abrir um pedido do Histórico; adicionar uma sugestão e conferir que a estimativa para os itens atuais muda e que o prato vai para Itens do pedido. Remover o prato e recarregar a página para conferir a persistência.
4. Em **Análises**, conferir o gráfico real × previsto (com losangos para os pedidos novos), a previsão × realidade, a edição dos coeficientes, a tabela manual × lstsq e os agrupamentos.
5. Navegar pelas abas com o teclado e conferir uma tela estreita.

## Diagnóstico rápido

| Sintoma | Verificação |
| --- | --- |
| CSV não encontrado | Confirmar os quatro arquivos em `dados/` ou rodar `python gerenciar.py dados` |
| Alterei um CSV, mas a tela continua igual | Banco já inicializado não recarrega; rode `python gerenciar.py resetar` só se puder perder as edições, ou crie uma migração |
| `resetar` diz que o banco está em uso | Pare o servidor (Ctrl + C) e rode de novo |
| Modelo indisponível | Conferir se alguma variável ficou constante ou dependente das outras |
| Estimativa com aviso de extrapolação | Maior prato, demais pratos, fila ou categorias fora do intervalo observado nos dados |
| `ValueError` da migração 2 ou 3 na inicialização | Os itens originais do banco diferem dos CSVs; regenere com a mesma ordem de sorteios ou crie uma migração própria |
| Botão Pronto desabilitado | No modo simulado, a cozinha ainda não alcançou o tempo sorteado; espere o cronômetro |
| Nenhuma sugestão | O pedido já inclui todo o cardápio |
| Porta 5000 ocupada | Identificar o servidor local existente antes de iniciar outro |
| Estilo antigo no navegador | Atualizar com Ctrl + F5 |
