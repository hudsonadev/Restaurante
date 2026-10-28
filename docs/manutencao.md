# Guia de manutenção para humanos e IA

## Antes de alterar

Leia [a implementação](implementacao.md) e confira o código atual. Esta documentação explica o projeto; não substitui requisitos novos nem instruções do usuário.

Verifique `git status --short` para distinguir alterações existentes das suas. Preserve `restaurante.db` e os itens editados ao realizar tarefas de código ou documentação.

## Onde mexer

| Necessidade | Local principal | Pontos relacionados |
| --- | --- | --- |
| Alterar leitura dos CSVs | `banco.py`, constante `DIRETORIO_DADOS` | `preparar_dados.py` usa a mesma constante |
| Alterar tabelas ou carga | `banco.py`, `inicializar_banco()` | Tabela `migracoes` e preservação dos itens |
| Alterar a regressão simples | `regressao.py`, `ajustar_simples()` | `comparar_polyfit()`, testes em `tests/test_admin.py` e `COMPARACAO_MANUAL_NUMPY.md` |
| Alterar variáveis da múltipla | `regressao.py`, `VARIAVEIS` e `carregar_observacoes()` | Validação em `app.py`, `prever_tempo()`, tabela `observacoes.html` e documentação |
| Alterar o cálculo da estimativa | `regressao.py`, `prever_tempo()` | `renderEstimativa` em `static/common.js` |
| Alterar sugestões ou vizinhos | `recomendacao.py`, `recomendar()` | Motivos exibidos e testes de pontuação |
| Alterar agrupamentos | `recomendacao.py`, `agrupar()` e `obter_clusters()` | `static/analises.js` |
| Alterar API | `app.py` | `static/script.js`, `static/novo_pedido.js` e testes |
| Alterar visual | `templates/`, `static/style.css` | IDs usados pelos scripts, acessibilidade e estados de carregamento |
| Regenerar a base | `preparar_dados.py` | Sobrescreve todos os CSVs; não atualiza um banco existente |

Cada página carrega só os scripts que usa. `common.js` é carregado em todas.

## Regras que preservam o comportamento

1. Manter `ajustar_simples` como cálculo manual (somas e médias), sem `polyfit`, `lstsq` ou outra função pronta de regressão. O NumPy entra só na validação e na conferência.
2. Treinar as regressões com `itens_originais`, nunca com `itens_pedido`: o tempo real registrado corresponde aos itens originais.
3. Manter previsões brutas nos gráficos e resíduos; limitar a zero só na exibição da estimativa.
4. Não sugerir pratos já incluídos no pedido nem usar o próprio pedido como vizinho.
5. Manter desempates determinísticos (pontuação, popularidade e ID).
6. Não apresentar a pontuação das sugestões como probabilidade.
7. Não repor os itens a cada inicialização. Mudanças de esquema ou de dados fixos em bancos existentes exigem uma nova versão de migração.
8. Validar no backend, mesmo que os controles HTML já imponham limites.
9. Descartar respostas antigas no frontend (contador `requisicao`).

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

O segundo comando só é necessário ao alterar JavaScript e requer Node.js. Os testes redirecionam `banco.CAMINHO_BANCO` para bancos temporários, então não modificam `restaurante.db`.

### O que os testes cobrem

- Cálculo manual com reta conhecida, alvo constante e amostras inválidas.
- Igualdade com `numpy.polyfit` em dados conhecidos e nos dados reais.
- Previsão aplicando os coeficientes, extrapolação e modelos indisponíveis.
- Validação de `POST /api/prever` (lista vazia, repetida, inexistente, booleanos, fila fora da faixa).
- Sugestões: exclusão de itens, determinismo, pedido vazio, sem vizinhos e contribuição colaborativa conhecida.
- Cosseno, ligação média e agrupamentos com resultados conhecidos.
- Persistência, idempotência e isolamento das edições; edições não retreinam os modelos.
- Rotas, ranking de categorias e base vazia.

### Conferência manual da interface

1. Em Novo pedido, escolher pratos, informar a fila e calcular; conferir a conta de cada modelo. Testar fila acima de 12 (aviso de extrapolação) e envio sem pratos.
2. Abrir um pedido; adicionar uma sugestão e conferir que a estimativa para os itens atuais muda e que o prato vai para Itens do pedido.
3. Remover o prato e recarregar a página; conferir a persistência.
4. Em Análises, conferir a reta, a tabela manual × polyfit, os gráficos real × previsto e os agrupamentos.
5. Navegar pelas abas com o teclado e conferir uma tela estreita.

## Diagnóstico rápido

| Sintoma | Verificação |
| --- | --- |
| CSV não encontrado | Confirmar os quatro arquivos em `dados/` ou rodar `preparar_dados.py` |
| Alterei um CSV, mas a tela continua igual | Banco já inicializado não recarrega; apague `restaurante.db` só se puder perder as edições, ou crie uma migração |
| Modelo múltiplo indisponível | Conferir se alguma variável ficou constante ou dependente das outras |
| Estimativa com aviso de extrapolação | Itens, fila ou categorias fora do intervalo observado nos dados |
| Nenhuma sugestão | O pedido já inclui todo o cardápio |
| Porta 5000 ocupada | Identificar o servidor local existente antes de iniciar outro |
| Estilo antigo no navegador | Atualizar com Ctrl + F5 |
