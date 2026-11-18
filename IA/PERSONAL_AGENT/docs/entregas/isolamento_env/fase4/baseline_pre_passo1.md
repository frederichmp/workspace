# Baseline antes do Passo 1 de docs/plans/isolamento_env_fase4.md

Repositório real, HEAD 3ff2b79, sem alteração de código. Modelo: claude-haiku-5-5.

| Passo | Checagem | Esperado | Obtido | OK/FALHA |
|---|---|---|---|---|
| 0 | Perfil do Windows, só nomes (ORACLE_, EMAIL_, GEMINI_, AGENTDBA_, SCRIPTS_) | nenhuma linha | nenhuma linha | OK |
| 1 | `git status --short -- .` | só não rastreados da abertura + `docs/plans/isolamento_env_fase4.md` + `docs/entregas/isolamento_env/fase4/`; nenhum rastreado modificado | todos os não rastreados da abertura, mais os dois previstos; nenhum rastreado modificado; nada em tests/, src/ ou raiz | OK |
| 2 | pytest sem conexão (1 execução) | 226 passed, 16 skipped, 0 failed; skip com motivo do sandbox | 226 passed, 16 skipped, 0 failed, 13 warnings; 1 linha de skip: `SKIPPED [16] tests\conftest.py:188: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)` | OK |
| 3 | G1 ORACLE_USER legado | nenhuma linha | nenhuma linha | OK |
| 3 | G2 SQL de sessão no Python | nenhuma linha | nenhuma linha | OK |
| 3 | G3 `override=True` | nenhuma linha | nenhuma linha | OK |
| 3 | G4 `load_dotenv(` | 2 linhas, override=False | `app.py:69` e `src/main.py:54`, ambas `override=False` | OK |
| 3 | G5 teste que liga o sandbox | nenhuma linha | nenhuma linha | OK |
| 3 | G6 credencial em print ou log | nenhuma linha | nenhuma linha | OK |
| 3 | G7 `git diff --stat b0ce169 -- registry/ db/` | vazio | vazio | OK |
| 3 | G8 `.env` versionado | nenhuma linha | nenhuma linha | OK |

## Observações

- Passo 0 e passo 1: executados antes do pytest, sem parada.
- Passo 2: uma única execução, sem repetição. 0 failed e 0 error.
- Base do `git diff --stat` do G7: b0ce169, como indicado. Os arquivos de `registry/` e `db/` não divergem de b0ce169.
- Não executado nesta rodada: a seção "Verificação" do plano docs/plans/isolamento_env_fase4.md, que não estava no pedido (só os greps do §5).
- Nenhum comando com `ORACLE_SANDBOX`; pytest com `env -u ORACLE_SANDBOX`. Sem Oracle, sem `.env` real aberto, sem commit, sem push, sem `git add`.
- Log bruto do pytest: scratchpad em `C:/Users/FREDER~1/AppData/Local/Temp/claude/db29872ef7336ab6/4a6117d2-8d87-4921-86bd-6291f042baa6/scratchpad/passo0/pytest_baseline.txt`.
