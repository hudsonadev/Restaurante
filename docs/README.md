# Documentação do Comanda

Este diretório descreve a implementação para quem usa, estuda ou modifica o projeto, incluindo agentes de IA.

## Roteiro de leitura

1. [Guia didático](../GUIA_DIDATICO.md): **a versão simples**. O caso em poucas páginas: dados, regressão à mão, resultado, site e como rodar.
2. [README principal](../README.md): instalação, execução, páginas e API.
3. [Documentação completa](../DOCUMENTACAO.md): como a estimativa é feita, os pesos das sugestões, a regressão em detalhe e como avaliar o modelo.
4. [Cálculo manual × numpy.linalg.lstsq](../COMPARACAO_MANUAL_NUMPY.md): verificação da regressão manual.
5. [Como foi implementado](implementacao.md): organização do código, dados, banco, API e interface.
6. [Manutenção para humanos e IA](manutencao.md): onde mexer, regras a preservar, testes e diagnóstico.

## Mapa do projeto

```text
projeto/
├── app.py                       Inicia o servidor Flask (chama comanda.criar_app)
├── gerenciar.py                 Terminal: inicializar, consultar, modelo, dados, resetar
├── requirements.txt             Dependências Python
├── restaurante.db               Estado persistente local (criado na primeira execução)
├── comanda/                     Backend
│   ├── __init__.py              criar_app(): inicializa o banco e registra os blueprints
│   ├── db.py                    Caminhos, conexão SQLite e leitura dos CSVs
│   ├── migracoes.py             Esquema, migrações v1–v3, inicializar_banco e resetar_banco
│   ├── cozinha.py               Cardápio com o tempo de cada prato e a regra sintética da cozinha
│   ├── dados.py                 Geração dos CSVs de dados/ (semente fixa)
│   ├── acompanhamento.py        Pedidos enviados à Cozinha: relógio simulado, Pronto, previsão × realidade
│   ├── recomendacao.py          Similaridades, agrupamentos e sugestões de pratos
│   ├── modelo/
│   │   ├── minimos_quadrados.py Regressão manual (Python puro) e conferência com o NumPy, sem banco
│   │   ├── variaveis.py         As quatro variáveis, aplicar() e variaveis_do_pedido()
│   │   ├── coeficientes.py      β personalizados: ler, salvar, limpar
│   │   └── previsao.py          Treino com os 100 pedidos, resumo, análises e prever_tempo
│   └── web/
│       ├── paginas.py           Blueprint das páginas HTML e da página 404
│       ├── api.py               Blueprint de /api/...
│       ├── validacao.py         Validação das entradas (EntradaInvalida → 400) e limites
│       ├── consultas.py         Consultas de leitura: cardápio, ranking, indicadores
│       └── formatacao.py        Filtros dos templates e data por extenso
├── dados/                       CSVs da base sintética
├── docs/                        Estes guias
├── templates/                   Páginas e blocos reutilizáveis (Jinja)
├── static/
│   ├── style.css                Aparência e responsividade
│   ├── common.js                Formatação, HTTP e exibição da estimativa
│   ├── novo_pedido.js           Seleção de pratos e estimativa ao vivo
│   ├── cozinha.js               Cronômetro, botão Pronto e Simular pedidos
│   ├── script.js                Página de um pedido: itens, sugestões e estimativa
│   ├── graficos.js              Gráfico real × previsto em SVG
│   ├── analises.js              Agrupamento de categorias e edição dos coeficientes
│   └── tabelas.js               Busca e filtros das tabelas
└── tests/                       Testes do projeto e do painel
```

Os CSVs inicializam uma base nova; o SQLite guarda o estado durante a execução. A regressão usa os tempos registrados e a fotografia fixa `itens_originais`. As sugestões, os totais e a estimativa dos itens atuais usam `itens_pedido`, que pode ser editada.
