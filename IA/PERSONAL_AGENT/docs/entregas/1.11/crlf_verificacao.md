# Tarefa 1.11, item 9 (CRLF) — verificação antes/depois

**Data:** 2026-11-17
**Modelo:** claude-haiku-5-5 (Haiku 5.5)

## Ambiente

- Sistema: Windows 11 Pro 10.0.26300
- Shell: Git Bash (comandos em Bash); `cygpath` para conversão de caminhos
- Python: `pythoncore-3.15-64` (caminho de site-packages observado no pytest)
- Verificador: `verifica_crlf.py` no scratchpad (`crlf_1_11`), executado com `python -I`, `PYTHONDONTWRITEBYTECODE=1` e `env -u ORACLE_SANDBOX`
- Projeto real: `c:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT`
- Clone de simulação: `<scratchpad>\crlf_1_11\clone\IA\PERSONAL_AGENT` (sparse-checkout, com commit de simulação que adiciona `.gitattributes` com `*.sql text eol=lf`)

**Escopo do "antes" e do "depois":**

- O "antes" do passo 1 é a **árvore real** do repositório (somente leitura).
- O "antes" do passo 2 é o **clone de simulação** antes da regravação.
- O "depois" (passo 4) é o **clone de simulação** após a regravação.
- O `.gitattributes` **ainda não existe no repositório real**. O "depois" não representa o estado do repositório real; representa o efeito esperado da regra `*.sql text eol=lf` no clone.

---

## Passo 1 — ANTES, árvore real (somente leitura)

**Comando:**

```bash
cd "/c/Users/<usuario>/OneDrive - <organizacao>/Workspace/IA/PERSONAL_AGENT" && env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -I "$W/verifica_crlf.py" "$P"; echo "EXIT=$?"
```

(`$W` = scratchpad `crlf_1_11`; `$P` = projeto real, convertido com `cygpath -u`.)

**Saída bruta:**

```
RAIZ=C:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT
core.autocrlf=true
check-attr: scripts/procedure_t7.sql: text: unspecified | scripts/procedure_t7.sql: eol: unspecified
CRLF 128 db/ops_kill.sql
CRLF 1 tests/corpus_adversarial/a01_update_set_internal.sql
CRLF 2 tests/corpus_adversarial/a02_start_with_connect_by.sql
CRLF 2 tests/corpus_adversarial/a03_order_by_desc_own_line.sql
CRLF 2 tests/corpus_adversarial/a04_execute_immediate_in_block.sql
CRLF 2 tests/corpus_adversarial/a05_create_package_body.sql
CRLF 2 tests/corpus_adversarial/a06_comment_with_end.sql
CRLF 3 tests/corpus_adversarial/a07_string_literal_end.sql
CRLF 3 tests/corpus_adversarial/a08_string_q_literal_end.sql
CRLF 2 tests/corpus_adversarial/a10_plsql_case_when.sql
CRLF 4 tests/corpus_adversarial/a11_extra_semicolon.sql
CRLF 2 tests/corpus_adversarial/a14_select_with_slash_line.sql
CRLF 4 tests/corpus_adversarial/a28_slash_on_line_in_block.sql
TOTAL_SQL=75 COM_CRLF=13
HASH_DIVERGENTE test_scripts.yaml:script_hash_divergente ESPERADO
IGNORADO_FIXTURE_PATH test_scripts.yaml:path_traversal_parent_t17
IGNORADO_FIXTURE_PATH test_scripts.yaml:path_traversal_abs_t17
HASH_OK=19 HASH_DIVERGENTE=1 (inesperados=0)
RESULTADO: FALHA
EXIT=1
```

**Resultado:** COM_CRLF=13, RESULTADO: FALHA, exit 1. Arquivos com CRLF: `db/ops_kill.sql` e 12 arquivos em `tests/corpus_adversarial/`. Coincide com o esperado.

---

## Passo 2 — ANTES, clone de simulação (antes da regravação)

**Comando:**

```bash
env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -I "$W/verifica_crlf.py" "$W/clone/IA/PERSONAL_AGENT"; echo "EXIT=$?"
```

**Saída bruta:**

```
RAIZ=C:\Users\<usuario>\AppData\Local\Temp\claude\db29872ef7336ab6\474bbbe3-4d4e-49c8-bd9d-de39a3da8825\scratchpad\crlf_1_11\clone\IA\PERSONAL_AGENT
core.autocrlf=true
check-attr: scripts/procedure_t7.sql: text: set | scripts/procedure_t7.sql: eol: lf
CRLF 128 db/ops_kill.sql
CRLF 202 docs/entregas/1.11/item6/ops_kill.sql
CRLF 65 docs/entregas/1.11/item6/ops_kill_v2_migracao_parte1.sql
CRLF 191 docs/entregas/1.11/item6/ops_kill_v2_migracao_parte2.sql
CRLF 134 docs/entregas/1.11/item6/rollback_ops_kill_v1.sql
CRLF 1 scripts/diretiva_slash_t8.sql
CRLF 1 scripts/diretiva_sqlplus_t8.sql
CRLF 3 scripts/dml_com_erro_t13.sql
CRLF 3 scripts/plsql_bloco_t6.sql
CRLF 9 scripts/plsql_if_stmt_t15.sql
CRLF 12 scripts/procedure_complex_t16.sql
CRLF 3 scripts/procedure_t7.sql
CRLF 1 scripts/select_t5_complexo.sql
CRLF 1 tests/corpus_adversarial/a01_update_set_internal.sql
CRLF 2 tests/corpus_adversarial/a02_start_with_connect_by.sql
CRLF 2 tests/corpus_adversarial/a03_order_by_desc_own_line.sql
CRLF 2 tests/corpus_adversarial/a04_execute_immediate_in_block.sql
CRLF 2 tests/corpus_adversarial/a05_create_package_body.sql
CRLF 2 tests/corpus_adversarial/a06_comment_with_end.sql
CRLF 3 tests/corpus_adversarial/a07_string_literal_end.sql
CRLF 3 tests/corpus_adversarial/a08_string_q_literal_end.sql
CRLF 2 tests/corpus_adversarial/a10_plsql_case_when.sql
CRLF 4 tests/corpus_adversarial/a11_extra_semicolon.sql
CRLF 2 tests/corpus_adversarial/a14_select_with_slash_line.sql
CRLF 4 tests/corpus_adversarial/a28_slash_on_line_in_block.sql
TOTAL_SQL=75 COM_CRLF=25
HASH_DIVERGENTE test_scripts.yaml:select_t5_complexo
HASH_DIVERGENTE test_scripts.yaml:plsql_bloco_t6
HASH_DIVERGENTE test_scripts.yaml:procedure_t7
HASH_DIVERGENTE test_scripts.yaml:diretiva_sqlplus_t8
HASH_DIVERGENTE test_scripts.yaml:diretiva_slash_t8
HASH_DIVERGENTE test_scripts.yaml:dml_com_erro_t13
HASH_DIVERGENTE test_scripts.yaml:plsql_if_stmt_t15
HASH_DIVERGENTE test_scripts.yaml:procedure_complex_t16
HASH_DIVERGENTE test_scripts.yaml:script_hash_divergente ESPERADO
IGNORADO_FIXTURE_PATH test_scripts.yaml:path_traversal_parent_t17
IGNORADO_FIXTURE_PATH test_scripts.yaml:path_traversal_abs_t17
HASH_OK=11 HASH_DIVERGENTE=9 (inesperados=8)
RESULTADO: FALHA
EXIT=1
```

**Resultado:** COM_CRLF=25, HASH_DIVERGENTE inesperados=8, RESULTADO: FALHA, exit 1. No clone, antes da regravação, o `.gitattributes` de simulação já está no HEAD, mas o índice ainda tem os arquivos com CRLF gravados. Os 8 hashes divergentes inesperados correspondem aos scripts de `scripts/` que passam a ser normalizados para LF.

---

## Passo 3 — REGRAVAÇÃO no clone de simulação

**Comandos:**

```bash
git -C "$W/clone" rm -r -q --cached IA/PERSONAL_AGENT && git -C "$W/clone" reset -q --hard; echo "EXIT=$?"
git -C "$W/clone" status --short | head
git -C "$W/clone" ls-files --eol -- 'IA/PERSONAL_AGENT/*.sql' | awk '{print $2}' | sort | uniq -c
```

**Saída bruta:**

```
EXIT=0
--- status:
--- eol:
     25 w/lf
     50 w/none
```

**Resultado:** regravação com exit 0. `git status --short` vazio, como esperado. Em `ls-files --eol` (coluna da árvore de trabalho): 25 arquivos `w/lf` e 50 `w/none`. `w/none` indica arquivos sem terminador de linha (ex.: uma linha ou vazios); não há `w/crlf` entre os `.sql`.

---

## Passo 4 — DEPOIS, clone de simulação

**Comando:**

```bash
env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -I "$W/verifica_crlf.py" "$W/clone/IA/PERSONAL_AGENT"; echo "EXIT=$?"
```

**Saída bruta:**

```
RAIZ=C:\Users\<usuario>\AppData\Local\Temp\claude\db29872ef7336ab6\474bbbe3-4d4e-49c8-bd9d-de39a3da8825\scratchpad\crlf_1_11\clone\IA\PERSONAL_AGENT
core.autocrlf=true
check-attr: scripts/procedure_t7.sql: text: set | scripts/procedure_t7.sql: eol: lf
TOTAL_SQL=75 COM_CRLF=0
HASH_DIVERGENTE test_scripts.yaml:script_hash_divergente ESPERADO
IGNORADO_FIXTURE_PATH test_scripts.yaml:path_traversal_parent_t17
IGNORADO_FIXTURE_PATH test_scripts.yaml:path_traversal_abs_t17
HASH_OK=19 HASH_DIVERGENTE=1 (inesperados=0)
RESULTADO: PASSA
EXIT=0
```

**Resultado:** COM_CRLF=0, HASH_DIVERGENTE inesperados=0 (apenas o `script_hash_divergente` esperado), RESULTADO: PASSA, exit 0.

---

## Passo 5 — DEPOIS, suíte no clone de simulação

**Comando:**

```bash
cd "$W/clone/IA/PERSONAL_AGENT" && env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
```

**Saída bruta:**

```
..................................................sss..s..ss.ss......... [ 52%]
.........................................................ssssssss        [100%]
============================== warnings summary ===============================
..\..\..\..\..\..\..\..\..\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: 13 warnings
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    if asyncio.iscoroutinefunction(func):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
121 passed, 16 skipped, 13 warnings in 19.73s
EXIT=0
```

**Resultado:** 121 passed, 16 skipped, 0 failed, exit 0. Igual ao projeto real (121 passed, 16 skipped). Nenhuma falha, portanto nenhum HASH_DIVERGENTE de teste a registrar.

---

## Passo 6 — Projeto real, `git status` (esperado vazio antes de gravar o .md)

**Comando:**

```bash
cd "c:/Users/<usuario>/OneDrive - <organizacao>/Workspace/IA/PERSONAL_AGENT" && git status --short .; echo "EXIT=$?"
```

**Saída bruta:**

```
 M docs/entregas/1.11/item6/implantacao.md
 M docs/entregas/1.11/item6/ops_kill.sql
 M docs/entregas/1.11/item6/ops_kill_v2_migracao_parte2.sql
EXIT=0
```

**Resultado:** NÃO vazio, divergindo do esperado. Os dois primeiros arquivos já constavam no `gitStatus` inicial da sessão. `docs/entregas/1.11/item6/ops_kill_v2_migracao_parte2.sql` não constava no status inicial e aparece agora como modificado. Não foi investigado a causa (sem comandos que alterem índice ou árvore). Nenhum desses arquivos é tocado pelos passos 1 a 5, que só leram o projeto real. Este arquivo `crlf_verificacao.md` é gravado após este passo e não aparece no status por ser novo (não rastreado e não listado com `--short .` sem `-u`, mas será criado de qualquer forma).

---

## Tabela final ANTES / DEPOIS

| Medida | ANTES (passo 1: árvore real) | ANTES (passo 2: clone, pré-regravação) | DEPOIS (passo 4: clone, pós-regravação) |
|---|---|---|---|
| COM_CRLF | 13 | 25 | 0 |
| HASH_DIVERGENTE inesperados | 0 (1 esperado: `script_hash_divergente`) | 8 (`select_t5_complexo`, `plsql_bloco_t6`, `procedure_t7`, `diretiva_sqlplus_t8`, `diretiva_slash_t8`, `dml_com_erro_t13`, `plsql_if_stmt_t15`, `procedure_complex_t16`) | 0 (1 esperado: `script_hash_divergente`) |
| RESULTADO | FALHA (exit 1) | FALHA (exit 1) | PASSA (exit 0) |
| pytest | não executado no passo 1 (ver passo 5 no projeto real, não pedido) | não executado | 121 passed, 16 skipped, 0 failed (exit 0) |

**Observações:**

- O "ANTES" do passo 1 é a árvore real; o "DEPOIS" é o clone de simulação. O `.gitattributes` com `*.sql text eol=lf` ainda não existe no repositório real.
- Passo 6: `git status --short .` não ficou vazio (3 arquivos modificados em `docs/entregas/1.11/item6/`), contrariando o esperado. Pendente de análise pelo responsável.
