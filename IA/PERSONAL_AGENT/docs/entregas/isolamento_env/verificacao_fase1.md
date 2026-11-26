# Verificação de aceite — fase 1 do isolamento do .env

Plano: `docs/plans/isolamento_env.md`, passo 4.
Branch `isolamento-env`, HEAD `0313e3b`.
Modelo executor: Haiku 5.5 (`claude-haiku-5-5`).

## Regras observadas
- `.env` real não foi lido, copiado nem impresso.
- `ORACLE_SANDBOX` verificada vazia antes de cada execução de pytest (nunca definida).
- `.env` fictícios contêm apenas as quatro linhas de sentinela, sem `ORACLE_SANDBOX`.
- Sem conexão Oracle. Nenhum arquivo do repositório foi editado.
- Gravação restrita a `docs/entregas/isolamento_env/`.

## Passo 1 — cópias temporárias via git archive

Pastas criadas em `%TEMP%\sentinela_isolamento\` (vazias antes da extração):

```
git -C <raiz> archive --format=tar -o <tmp>.tar 0313e3b IA/PERSONAL_AGENT
git -C <raiz> archive --format=tar -o <tmp>.tar 673ceb1 IA/PERSONAL_AGENT
tar -xf <tmp>.tar -C <pasta>
```

Raiz do repositório git: `C:/Users/<usuario>/OneDrive - <organizacao>/Workspace`

| Cópia | Rev | Arquivos extraídos | `.env` herdado |
|---|---|---|---|
| sentinela_head | 0313e3b | 167 | não |
| sentinela_673ceb1 | 673ceb1 | 165 | não |

## Passo 2 — `.env` fictício

Conteúdo idêntico nas duas cópias:

```
SENTINELA_ISOLAMENTO_ENV=1
ORACLE_SENTINELA_FICTICIA=1
EMAIL_SENTINELA_FICTICIA=1
GEMINI_SENTINELA_FICTICIA=1
```

## Passo 3 — teste de isolamento nas cópias

Comando (cwd = raiz de cada cópia):
`python -m pytest -q -p no:cacheprovider tests/test_isolamento_env.py`

Saídas brutas completas:
- `docs/entregas/isolamento_env/pytest_sentinela_head_0313e3b.txt`
- `docs/entregas/isolamento_env/pytest_sentinela_673ceb1_controle.txt`

Resultado HEAD 0313e3b (exit 0):
```
.                                                                        [100%]
1 passed, 13 warnings in 3.48s
```

Resultado controle 673ceb1 (exit 1):
```
F                                                                        [100%]
FAILED tests/test_isolamento_env.py::test_imports_de_teste_nao_alteram_environ
E       AssertionError: adicionadas_n=3, removidas_n=0, alteradas_n=0, nomes_nao_sensiveis=[]
tests\test_isolamento_env.py:59: AssertionError
1 failed, 13 warnings in 4.00s
```

## Passo 4 — checagens no repositório real

### git status --short
Saída idêntica à do início da sessão (`M README.md`, não rastreados de `docs/entregas/1.11/`, `docs/plans/`, `docs/entregas/isolamento_env/`, `db/ops_kill.sqlbkp`, `../ARCANA_REALM/`, `../MAHJONG_GAME/`). Nenhuma alteração feita por esta verificação em arquivos rastreados.

### git diff 673ceb1 -- tests/test_isolamento_env.py
Saída vazia (0 linhas). O teste em HEAD é o mesmo do controle.

### grep `load_dotenv|dotenv_values|find_dotenv` em src/*.py e app.py
```
src\main.py:8:  from dotenv import load_dotenv
src\main.py:18: load_dotenv(ROOT_DIR / ".env")
app.py:19:      from dotenv import load_dotenv
app.py:33:      load_dotenv(ROOT_DIR / ".env")
```
Esperado: apenas `src/main.py` e `app.py`. Encontrado: exatamente esses dois. Arquivos varridos: 20.

### grep `override\s*=\s*True` em src/*.py e app.py
Ocorrências: 0.

### grep `ORACLE_SANDBOX` em app.py e src/*.py
Ocorrências: 0.

## Veredito por item

| Item | Critério | Resultado |
|---|---|---|
| 1. Cópias via git archive sem `.env` herdado | extração ok, sem `.env` | APROVADO |
| 2. `.env` fictício com as quatro linhas | conteúdo exato, sem ORACLE_SANDBOX | APROVADO |
| 3a. HEAD 0313e3b | 1 passed | APROVADO (1 passed, exit 0) |
| 3b. Controle 673ceb1 | FAILED com adicionadas_n >= 1 | APROVADO (FAILED, adicionadas_n=3) |
| 4a. git status | sem alteração nova no repositório | APROVADO |
| 4b. git diff 673ceb1 do teste | vazio | APROVADO (0 linhas) |
| 4c. grep load_dotenv/dotenv_values/find_dotenv | só src/main.py e app.py | APROVADO |
| 4d. grep override=True | zero | APROVADO (0) |
| 4e. grep ORACLE_SANDBOX em app.py e src/ | zero | APROVADO (0) |
| 5. Remoção das pastas temporárias | removidas ao final | ver seção de limpeza |

## Limpeza
Pastas `%TEMP%\sentinela_isolamento\sentinela_head` e `%TEMP%\sentinela_isolamento\sentinela_673ceb1` removidas após a gravação deste relatório.

## Veredito geral
**APROVADO.** A fase 1 do isolamento passa: o teste do HEAD passa, a sentinela é detectada no commit anterior (controle negativo) e as greps de regressão batem com o esperado.
