# Guia de manutenção para humanos e IA

## Antes de alterar

Leia [a implementação](implementacao.md) e confira o código atual. Esta documentação explica o projeto; não substitui requisitos novos nem instruções do usuário. Não há dependência de serviço de IA: este guia apenas facilita o trabalho de pessoas e agentes que editam o repositório.

Verifique `git status --short` para distinguir alterações existentes das suas. Preserve os dados e o histórico local ao realizar tarefas de código ou documentação.

## Onde mexer

| Necessidade | Local principal | Pontos relacionados |
| --- | --- | --- |
| Alterar leitura dos CSVs | `banco.py`, constante `DIRETORIO_DADOS` | `preparar_dados.py` usa a mesma constante |
| Alterar tabelas ou carga | `banco.py`, `inicializar_banco()` | Preservação do histórico e tabela `migracoes` |
| Alterar ranking ou vizinhos | `recomendacao.py`, `recomendar()` | Motivos exibidos e testes de pontuação |
| Alterar clusters | `recomendacao.py`, `agrupar()` e `obter_clusters()` | Distâncias, desempates e interface de análises |
| Alterar regressão | `regressao.py` | Validação em `app.py`, formulário e documentação |
| Alterar API | `app.py` | Consumidores em `static/script.js` e testes |
| Alterar visual e navegação | `templates/index.html`, `static/style.css`, `static/script.js` | IDs, eventos, acessibilidade e estados de carregamento |
| Reproduzir dados demonstrativos | `preparar_dados.py` | Sobrescreve usuários e histórico em `dados/`, preservando catálogo e gêneros; não atualiza SQLite existente |

## Regras que preservam o comportamento

1. Não recomendar conteúdos já vistos pelo usuário selecionado.
2. Não usar o próprio usuário como vizinho nem vizinhos de similaridade zero.
3. Manter os desempates determinísticos. O ranking desempata por popularidade e ID; vizinhos e proximidades usam IDs.
4. Não apresentar pontuação como probabilidade. As explicações devem corresponder ao consumo observado.
5. Não repor o histórico inicial em cada inicialização. `visualizacoes` é editável e `historico_inicial` é a fotografia da regressão.
6. Não usar as novas marcações para modificar silenciosamente o treinamento da regressão.
7. Preservar `streaming.db` e a tabela legada `engajamento`. Alterações de esquema devem ter migração explícita e testes de preservação.
8. Resolver caminhos de dados pelo diretório do código, não pelo diretório corrente do processo.
9. Manter as marcações idempotentes e validar entradas no backend, mesmo que os controles HTML já imponham limites.
10. Evitar que uma resposta de um perfil anterior sobrescreva a seleção atual no frontend.

## Dados fixos e migrações

Os arquivos em `dados/` são a fonte para criar bancos novos. O SQLite é a fonte do estado em execução. Copiar CSVs para outra pasta exigiu apenas ajustar os caminhos; não foi necessário recriar o banco.

Se uma tarefa futura mudar dados fixos em uma instalação existente, não basta editar o CSV nem executar `popular_banco.py`. Planeje uma nova versão de migração que atualize as entidades necessárias e preserve os vistos. Não apague o banco ou o marcador da versão 1 para forçar uma carga: isso pode perder histórico ou colidir com IDs existentes.

O gerador pressupõe a base demonstrativa original de 100 IDs e usa listas fixas para nomes e lê os títulos de `dados/conteudos.csv`. Não é um importador genérico. Executá-lo sobrescreve os CSVs de usuários e histórico com os dados gerados; preserva conteúdos e gêneros. Para experimentos, use cópias temporárias, não os arquivos do usuário.

## Executar e testar

Comandos a partir da raiz do projeto, em PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Abra http://127.0.0.1:5000. Se o ambiente já existe e as dependências estão instaladas, basta o último comando. `.venv` e caches são ignorados pelo Git.

Para os testes:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
node --check static/script.js
```

O segundo comando só é necessário ao alterar JavaScript e requer Node.js instalado; Node não é requisito para executar o aplicativo. `-B` evita gerar novo bytecode nos testes.

Os testes redirecionam `banco.CAMINHO_BANCO` para bancos temporários antes da criação da aplicação. Isso exercita a carga real dos CSVs sem modificar `streaming.db`.

### O que os testes cobrem

- Tamanho do catálogo, dados e rotas principais.
- Marcar/desmarcar repetidamente, isolamento de usuários e persistência após reinicializar.
- Exclusão de vistos, ranking determinístico e contribuição colaborativa conhecida.
- Usuário sem histórico, sem vizinhos, gênero sem consumo e catálogo inteiramente visto.
- Cosseno, ligação média e agrupamentos com resultados conhecidos.
- Validações da API, modelo indisponível e extrapolação.
- Regressão com coeficientes conhecidos, alvo constante, amostra insuficiente e posto deficiente.
- Preservação da tabela antiga de engajamento.

### Conferência manual da interface

1. Trocar entre um perfil com histórico e um sem histórico.
2. Marcar uma sugestão; confirmar que ela sai das recomendações e aparece no histórico.
3. Desmarcar e recarregar a página; conferir a persistência da remoção.
4. Combinar busca por título, gênero e status; limpar os filtros.
5. Abrir explicações, pessoas semelhantes, clusters e a regressão.
6. Navegar nas abas por teclado e conferir tela estreita.

Testes automatizados de backend não substituem inspeção visual. Ao relatar validação, diferencie testes executados, revisão estática e fluxos efetivamente verificados no navegador.

## Diagnóstico rápido

| Sintoma | Verificação |
| --- | --- |
| CSV não encontrado | Confirmar os quatro arquivos ativos em `dados/` e o valor de `DIRETORIO_DADOS` |
| Alterei CSV, mas a tela continua igual | Banco já inicializado não recarrega automaticamente; avaliar migração |
| Regenerar CSVs não mudou a regressão | O ajuste lê a fotografia inicial salva no banco |
| Nenhuma recomendação | Conferir se todo o catálogo já está marcado como visto |
| Não há usuários semelhantes | Verificar histórico vazio ou ausência de similaridade positiva |
| Modelo indisponível | Conferir quantidade de observações e independência das três variáveis |
| Porta 5000 ocupada | Identificar o servidor local existente antes de iniciar outro |
| Estilo antigo no navegador | Atualizar com Ctrl + F5 |

## Ao concluir uma alteração

Atualize a documentação quando mudar caminhos, regras, contratos ou comandos. Rode as verificações relevantes e descreva o que foi alterado, o que foi testado e qualquer validação pendente. Não inclua ambientes virtuais ou caches nos commits.
