# Verificação do Passo 2 de docs/plans/isolamento_env_fase4.md

Working tree com o Passo 2 aplicado, sem commit. HEAD 216a6fd. Modelo: claude-haiku-5-5.
Base da decisão: docs/entregas/isolamento_env/fase4/decisao_fase4.md §4.

## Resultados

| Item | Checagem | Esperado | Obtido | OK/FALHA |
|---|---|---|---|---|
| 1.0 | Perfil do Windows, só nomes | nenhuma linha | nenhuma linha | OK |
| 1.1 | `git status --short -- .` | M app.py, M src/main.py, M tests/test_carga_env_entrada.py + não rastreados da abertura | exatamente isso; nada em tests/, src/ ou raiz fora do previsto | OK |
| 1.2 | pytest sem conexão (1 execução) | 0 failed; passed 266; skipped 16 | 266 passed, 16 skipped, 0 failed, 0 error | OK |
| 1.2 | Skip | motivo do sandbox | `SKIPPED [16] tests\conftest.py:188: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)` | OK |
| 1.3 | G1 ORACLE_USER legado | nenhuma linha | nenhuma linha | OK |
| 1.3 | G2 SQL de sessão no Python | nenhuma linha | nenhuma linha | OK |
| 1.3 | G3 `override=True` | nenhuma linha | nenhuma linha | OK |
| 1.3 | G4 `load_dotenv(` | app.py e src/main.py com `load_dotenv(stream=io.StringIO(texto), override=False)` | app.py:73 e src/main.py:58, ambas com essa forma | OK |
| 1.3 | G5 teste que liga o sandbox | nenhuma linha | nenhuma linha | OK |
| 1.3 | G6 credencial em print ou log | nenhuma linha | nenhuma linha | OK |
| 1.3 | G7 `git diff --stat b0ce169 -- registry/ db/` | vazio | vazio | OK |
| 1.3 | G8 `.env` versionado | nenhuma linha | nenhuma linha | OK |
| 2(i) | Entre `# >>> carga-env` e `# <<< carga-env`, sem `os.path.`, `.is_file(`, `.exists(`, `read_text` | 0 em cada arquivo | app.py: 0, 0, 0, 0; src/main.py: 0, 0, 0, 0 | OK |
| 2(ii) | `open(` exatamente 1 vez por bloco | 1 em cada | app.py: 1; src/main.py: 1 | OK |
| 2(iii) | `diff` dos dois blocos | vazio | vazio (blocos idênticos) | OK |
| 2(iv) | `git grep -n 'env_file=None' -- src/` | nenhuma linha | nenhuma linha | OK |

## Observações

- Marcador de abertura: `# >>> carga-env` tem texto depois do nome (`(texto idêntico em app.py e src/main.py; ...)`). O casamento exato falhou no primeiro script; refiz por prefixo. O marcador de fechamento `# <<< carga-env` é exato. Cada arquivo tem um par de marcadores.
- Fim de linha: app.py com 880 CRLF, src/main.py com 454 CRLF, sem LF puro medido nos blocos.
- Itens 1.1 a 1.3 e 2 rodados nesta ordem. Os controles de mutação não foram rodados (pedido da sessão principal).
- Greps da seção Verificação do plano (§6) não foram rodados nesta rodada; só os do §5 e os da decisão §4.
- Nenhum commit, `git add`, stash, checkout, reset ou push. Nada gravado no repositório além deste arquivo não rastreado.
- `ORACLE_SANDBOX` ausente em todos os comandos (`env -u ORACLE_SANDBOX`). O `.env` real não foi aberto. Sem Oracle.

## Saídas (scratchpad)

- `C:/Users/FREDER~1/AppData/Local/Temp/claude/db29872ef7336ab6/4a6117d2-8d87-4921-86bd-6291f042baa6/scratchpad/passo2/pytest_passo2.txt`: pytest completo.
- `.../scratchpad/passo2/greps_passo2.txt`: greps do §5.
- `.../scratchpad/passo2/blocos_passo2.py`: script dos greps da decisão.
