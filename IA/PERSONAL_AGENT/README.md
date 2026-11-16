# PERSONAL AGENT

Projeto de Agente Pessoal de IA em Python, focado em orquestração, uso de ferramentas (*tools*), gestão de memória e prompts modulares.

## Estrutura de Diretórios

```text
PERSONAL_AGENT/
├── data/
│   ├── logs/              # Logs de execução do agente
│   └── memory/            # Armazenamento local de memória (JSON, SQLite, etc.)
├── docs/                  # Documentações de arquitetura e fluxos
├── scripts/               # Scripts utilitários e de automação
├── src/
│   ├── agent/             # Core do agente, loop de execução e orquestração
│   ├── config/            # Configurações e variáveis de ambiente (settings.py)
│   ├── memory/            # Gerenciamento de memória de curto e longo prazo
│   ├── prompts/           # Templates de system prompts e instruções
│   ├── tools/             # Ferramentas e habilidades customizadas do agente
│   ├── utils/             # Funções auxiliares e loggers
│   └── main.py            # Ponto de entrada da aplicação
├── tests/                 # Testes unitários e de integração
├── .env.example           # Exemplo de variáveis de ambiente
├── .gitignore             # Arquivos ignorados pelo Git
├── requirements.txt       # Dependências Python
└── README.md              # Documentação principal
```

## Como Começar

1. Crie e ative o ambiente virtual:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Instale as dependências:
   ```powershell
   pip install -r requirements.txt
   ```
3. Copie o arquivo `.env.example` para `.env` e configure suas chaves de API:
   ```powershell
   Copy-Item .env.example .env
   ```
4. Execute o agente:
   ```powershell
   python -m src.main
   ```
