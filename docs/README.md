# Documentação do StreamData

Este diretório descreve a implementação atual para quem usa, estuda ou modifica o projeto, incluindo agentes de IA.

## Roteiro de leitura

1. [README principal](../README.md): instalação, execução e visão geral.
2. [Como foi implementado](implementacao.md): arquitetura, dados, fórmulas, fluxo da interface e contratos da API.
3. [Manutenção para humanos e IA](manutencao.md): pontos de alteração, regras que precisam ser preservadas, testes e diagnóstico.

## Mapa do projeto

```text
projeto/
├── app.py                  Rotas HTTP e criação da aplicação
├── banco.py                SQLite, caminhos e carga inicial
├── recomendacao.py         Similaridades, clusters e ranking
├── regressao.py            Regressões simples/múltipla e métricas
├── preparar_dados.py        Geração manual dos dados demonstrativos
├── popular_banco.py         Inicialização manual opcional
├── consultar_banco.py       Consulta de usuários e vistos no terminal
├── requirements.txt        Dependências Python
├── streaming.db            Estado persistente local
├── dados/                  CSVs fixos e planilha original
├── docs/                   Estes guias
├── templates/              Admin, análises, catálogo e perfis
├── static/style.css        Aparência e responsividade
├── static/script.js        Interações do perfil individual
├── static/graficos.js      Dispersão, reta e comparação em SVG
├── static/analises.js      Simulador e agrupamentos
├── static/common.js        Formatação e consultas HTTP
├── static/tabelas.js       Busca e filtros globais
└── tests/                  Testes do projeto e do painel Admin
```

Os CSVs inicializam uma base nova; o SQLite guarda o estado utilizado durante a execução. A recomendação e os totais de consumo usam as marcações atuais. As regressões usam as horas originais; a múltipla também usa o histórico inicial preservado. O painel Admin reúne a visão geral, e os perfis permitem analisar e editar cada histórico individualmente.
