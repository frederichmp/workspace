# Verificação do Passo 3 de docs/plans/isolamento_env_fase4.md (Achado 4)

Working tree sem commit. HEAD f5692f0. Modelo: claude-haiku-5-5.

## Resultados

| Item | Checagem | Esperado | Obtido | OK/FALHA |
|---|---|---|---|---|
| 1.0 | Perfil do Windows, só nomes | nenhuma linha | nenhuma linha | OK |
| 1.1 | `git status --short -- .` | M src/tools/rag_search.py, ?? tests/test_rag_search_env.py + não rastreados da abertura | exatamente isso; nada fora do previsto | OK |
| 1.2 | pytest sem conexão (1 execução) | 0 failed; passed 268; skipped 16 | 268 passed, 16 skipped, 0 failed, 0 error | OK |
| 1.2 | Skip | motivo do sandbox | `SKIPPED [16] tests\conftest.py:188: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)` | OK |
| 1.3 | G1 ORACLE_USER legado | nenhuma linha | nenhuma linha | OK |
| 1.3 | G2 SQL de sessão no Python | nenhuma linha | nenhuma linha | OK |
| 1.3 | G3 `override=True` | nenhuma linha | nenhuma linha | OK |
| 1.3 | G4 `load_dotenv(` | app.py:73 e src/main.py:58, `override=False` | app.py:73 e src/main.py:58, `override=False` | OK |
| 1.3 | G5 teste que liga o sandbox | nenhuma linha | nenhuma linha | OK |
| 1.3 | G6 credencial em print ou log | nenhuma linha | nenhuma linha | OK |
| 1.3 | G7 `git diff --stat b0ce169 -- registry/ db/` | vazio | vazio | OK |
| 1.3 | G8 `.env` versionado | nenhuma linha | nenhuma linha | OK |
| 2(a) | `git grep -n 'env_file=None' -- src/` | exatamente 1 linha, com `_env_file=None` | 2 linhas: `src/tools/rag_search.py:42` (código, `_env_file=None`) e `src/tools/rag_search.py:33` (comentário, texto `` `env_file=None` seria ``) | FALHA (literal) |
| 2(b) | `git grep -n -E '^(import\|from) chromadb' -- src/ app.py` | nenhuma linha | nenhuma linha. O import está indentado na linha 37, dentro de `_obter_vectorstore` | OK |

## Detalhes do item 2(a)

- O critério pedia exatamente 1 linha e nenhum `env_file=None` sem sublinhado. A segunda ocorrência está em comentário, na linha 33, e cita o texto literal `env_file=None` como exemplo do que seria o erro.
- Código real: a única linha de código com o argumento é a 42, com `_env_file=None`. Nenhum `env_file=None` de código sem sublinhado.
- Se o critério for lido como "código, sem comentários", o resultado é OK. Como está escrito, o resultado é FALHA. Decidir na revisão se o comentário deve ser reformulado ou o critério ajustado; não alterei nada.

## Observações

- Warnings: 16 nesta execução, contra 13 no Passo 2. Não verificado se o aumento vem do novo teste; não investigado.
- Greps da seção Verificação do plano (§6) não rodados nesta rodada; só os do §5 e os do item 2.
- Nenhum commit, `git add`, stash, checkout, reset ou push. Nada gravado no repositório além deste arquivo não rastreado.
- `ORACLE_SANDBOX` ausente em todos os comandos (`env -u ORACLE_SANDBOX`). O `.env` real não foi aberto. Sem Oracle.

## Saídas (scratchpad)

- `C:/Users/FREDER~1/AppData/Local/Temp/claude/db29872ef7336ab6/4a6117d2-8d87-4921-86bd-6291f042baa6/scratchpad/passo3/pytest_passo3.txt`: pytest completo.
- `.../scratchpad/passo3/greps_passo3.txt`: greps do §5 e do item 2.
