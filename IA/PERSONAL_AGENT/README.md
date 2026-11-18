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
   **Carga do `.env`:**
   - O `.env` é lido só na subida da CLI (`src/main.py`) e da Web (`app.py`). Nenhum módulo de `src/tools/` o recarrega.
   - **Alterar o `.env` exige reiniciar a CLI e a Web.** Os processos em execução continuam com os valores lidos na subida, inclusive as credenciais Oracle e de e-mail.
   - Uma variável definida no shell ou no perfil do Windows **vence** o valor do `.env`. Depois de alterar variáveis do perfil, confira se há nomes `ORACLE_*`, `EMAIL_*`, `GEMINI_*`, `AGENTDBA_*` ou `SCRIPTS_*` definidos fora do `.env`.
4. Execute o agente:
   ```powershell
   python -m src.main
   ```
