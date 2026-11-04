# Documentação do Comanda

Este diretório descreve a implementação para quem usa, estuda ou modifica o projeto, incluindo agentes de IA.

## Roteiro de leitura

1. [Guia didático](../GUIA_DIDATICO.md): o caso explicado passo a passo, com dados, regressão manual, comparação com o NumPy, interpretação e página web.
2. [README principal](../README.md): instalação, execução e visão geral.
3. [Funcionamento, pesos e regressões](../DOCUMENTACAO.md): como a estimativa é feita e como comparar os dois modelos.
4. [Cálculo manual × numpy.polyfit](../COMPARACAO_MANUAL_NUMPY.md): verificação da regressão manual.
5. [Como foi implementado](implementacao.md): dados, banco, fórmulas, API e interface.
6. [Manutenção para humanos e IA](manutencao.md): pontos de alteração, regras a preservar, testes e diagnóstico.

## Mapa do projeto

```text
projeto/
├── app.py                  Rotas HTTP, validação e criação da aplicação
├── banco.py                SQLite, caminhos e carga inicial
├── regressao.py            Regressão simples manual (Python puro), polyfit, múltipla e previsão
├── recomendacao.py         Similaridades, agrupamentos e sugestões de pratos
├── preparar_dados.py       Cardápio com tempo de cada prato e pedidos (cozinha em paralelo)
├── popular_banco.py        Inicialização manual opcional
├── consultar_banco.py      Lista pedidos, itens e tempos no terminal
├── requirements.txt        Dependências Python
├── restaurante.db          Estado persistente local (criado na primeira execução)
├── dados/                  CSVs da base sintética
├── docs/                   Estes guias
├── templates/              Admin, novo pedido, análises, cardápio e pedidos
├── static/style.css        Aparência e responsividade
├── static/common.js        Formatação, HTTP e exibição da estimativa
├── static/novo_pedido.js   Seleção de pratos e cálculo do tempo
├── static/script.js        Página de um pedido: itens, sugestões e estimativa
├── static/graficos.js      Dispersão, reta e real × previsto em SVG
├── static/analises.js      Agrupamento de categorias
├── static/tabelas.js       Busca e filtros das tabelas
└── tests/                  Testes do projeto e do painel Admin
```

Os CSVs inicializam uma base nova; o SQLite guarda o estado durante a execução. As regressões usam os tempos registrados e a fotografia fixa `itens_originais`. As sugestões, os totais e a estimativa dos itens atuais usam `itens_pedido`, que pode ser editada.
