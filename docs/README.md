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
├── regressao.py            Regressão linear múltipla
├── preparar_dados.py        Geração manual dos dados demonstrativos
├── popular_banco.py         Inicialização manual opcional
├── consultar_banco.py       Consulta de usuários e vistos no terminal
├── requirements.txt        Dependências Python
├── streaming.db            Estado persistente local
├── dados/                  CSVs fixos e planilha original
├── docs/                   Estes guias
├── templates/index.html    Estrutura da interface
├── static/style.css        Aparência e responsividade
├── static/script.js        Interação e chamadas à API
└── tests/test_projeto.py    Testes automatizados
```

Os CSVs inicializam uma base nova; o SQLite guarda o estado utilizado durante a execução. A recomendação usa as marcações atuais. A regressão usa o histórico inicial preservado. Essas três responsabilidades são diferentes e orientam a organização do projeto.
