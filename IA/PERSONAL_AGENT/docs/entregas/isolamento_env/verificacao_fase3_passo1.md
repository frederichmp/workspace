# Verificação fase 3, passo 1 (isolamento-env)

- Data: 2026-11-18
- Modelo: claude-haiku-5-5
- Branch: isolamento-env. HEAD: c97a90f. Working tree: alterações previstas, sem commit.
- Base do plano: docs/plans/isolamento_env_fase3.md §6. Procedimento: docs/PROCESSO.md §5, passos 0 a 3, mais os greps extras do pedido.
- Passo 4 (§5.4, cópia em commit anterior) não foi executado, por estar fora do pedido.

## Resultado por item

| Checagem | Esperado | Obtido | OK/FALHA |
|---|---|---|---|
| 0. Variáveis do perfil Windows com prefixo ORACLE_, EMAIL_, GEMINI_, AGENTDBA_, SCRIPTS_ (HKCU e HKLM, só nomes) | nenhuma linha | nenhuma linha | OK |
| 1. `git status --short -- .` | só arquivos previstos | M app.py, M src/main.py, M tests/test_carga_env_entrada.py; ?? decisao_fase3.md, fase3_controles.md; não rastreados pré-existentes (docs/entregas/1.11/item1/*, db/ops_kill.sqlbkp, docs/plans/1.11-item1-B-refeito.md, docs/entregas/processo-subagentes/). Nenhum caminho fora da lista. | OK |
| 2. pytest sem ORACLE_SANDBOX | 205 passed, 16 skipped, 0 failed | 205 passed, 16 skipped, 0 failed | OK |
| 2. Motivo dos skips | todos "requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)" | 16 skips, todos em tests\conftest.py:188 com esse motivo | OK |
| 3. `ORACLE_USER\b` em src/*.py, app.py, tools/*.py | nenhuma linha | nenhuma linha | OK |
| 3. `alter system/session` em *.py | nenhuma linha | nenhuma linha | OK |
| 3. `override=True` em src/*.py, app.py, tools/*.py | nenhuma linha | nenhuma linha | OK |
| 3. `load_dotenv(` em src/*.py, app.py | 2 linhas: app.py e src/main.py, override=False | app.py:57 e src/main.py:42, ambas com override=False | OK |
| 3. `setenv`/`environ[...] = "1"` de ORACLE_SANDBOX em tests/*.py | nenhuma linha | nenhuma linha | OK |
| 3. Credencial em print/logger | nenhuma linha | nenhuma linha | OK |
| 3. `git diff --stat c97a90f -- registry/ db/` | vazio | vazio | OK |
| 3. `.env` versionado | nenhuma linha | nenhuma linha | OK |
| X1. `load_dotenv(` ou `dotenv_values(` em src/*.py, app.py (git grep) | só app.py e src/main.py, no bloco carga-env | app.py:57 e src/main.py:42, ambas dentro do bloco (app.py linhas 34 a 69; src/main.py linhas 19 a 54) | OK |
| X2. Bloco carga-env: diff entre app.py e src/main.py (working tree) | vazio | 36 linhas em cada, diff vazio | OK |
| X3. `_personal_agent_estado_env` em *.py de app.py, src, tests | só app.py e src/main.py | app.py:47 e src/main.py:32 (constantes de exportação). Também tests/test_carga_env_entrada.py:9, em comentário/docstring. | OK, com observação: a menção no teste é texto, não uso |
| X4. `ORACLE_SANDBOX` em app.py e src/*.py | só dentro do bloco carga-env e da constante _AVISO_SANDBOX_DESCARTADA | app.py: linhas 39, 43, 55, 62 (dentro do bloco 34 a 69; 43 é a constante). src/main.py: linhas 24, 28, 40, 47 (dentro do bloco 19 a 54; 28 é a constante). Nenhuma fora. | OK |
| X5. Teste que liga ORACLE_SANDBOX=1 no ambiente de processo | nenhuma gravação de "1" em tests/ | Nenhuma atribuição em os.environ (G5 limpo). Porém há 6 ocorrências de "ORACLE_SANDBOX=1" como conteúdo de .env fictício em tests/test_carga_env_entrada.py (linhas 189, 223, 243, 259, e 3 no docstring), lidas só dentro de subprocesso, conforme o comentário de segurança do próprio arquivo (linha 3). Também há uma ocorrência em linha 204 com "ORACLE_SANDBOX=1" no .env e sandbox_shell="0". | DIVERGE: decisão do responsável. O grep literal acusa; a intenção documentada do teste é outra. |
| X6. Logger com valor de chave sombreada (`_KEY`, `_TOKEN`, `_SENHA`, `PASSWORD`, `SECRET`) em app.py, src, tests | nenhuma linha | nenhuma linha | OK |

## pytest

- Comando: `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider`
- Resultado: 205 passed, 16 skipped, 0 failed, 13 warnings (DeprecationWarning do langsmith, sem relação com a tarefa). Exit 0.
- Baseline: 199 passed, 16 skipped. Diferença: +6 testes novos, esperado.
- Saída bruta: C:\Users\FREDER~1\AppData\Local\Temp\claude\db29872ef7336ab6\43453ace-ee57-4e27-b567-efc15821d1f9\scratchpad\pytest_passo1.txt (fora do projeto, por causa do limite de arquivo deste passo).

## Achados para o responsável

1. X5: o grep de `ORACLE_SANDBOX=1` em tests/ acusa conteúdo de .env fictício em test_carga_env_entrada.py. Não é atribuição ao ambiente, e o próprio arquivo documenta que essas strings só são lidas em subprocesso. Mas o plano §4 pede .env fictício "só de nomes-sentinela, nunca com ORACLE_SANDBOX". Esse ponto precisa de decisão antes do aceite.
2. Nenhuma ação foi tomada; esta verificação não altera código nem commita.
3. Passo 4 (§5.4) fica pendente, fora deste pedido.

## Veredito

Passos 0 a 3 e greps extras: OK, exceto X5, que diverge do esperado e fica para decisão do responsável. Passou o pytest: 205 passed, 16 skipped, 0 failed, igual ao esperado.
