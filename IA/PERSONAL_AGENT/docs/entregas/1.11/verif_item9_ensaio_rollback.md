# Verificação item 9 (1.11): ensaio de rollback de db/ops_kill.sql e regravação CRLF

- Data: 2026-11-17
- Modelo executor: claude-haiku-5-5 (Haiku 5.5)
- Ambiente: projeto real `PERSONAL_AGENT` (somente leitura) e clone de scratch para o ensaio
- Variáveis: `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1`; pytest com `-p no:cacheprovider`
- Nenhum comando alterou índice, árvore ou configuração do repositório real. Nenhum `.env` foi lido. Nenhuma conexão Oracle.

Nota: Os testes sandbox de kill não foram executados: exigem ORACLE_SANDBOX=1 e conexão Oracle, proibidas nesta rodada.

---

## PARTE A: projeto real após o commit ab28cc3

### A1. Estado do Git

Comandos:

```
git log --oneline -3
git status --short .
git check-attr text eol -- scripts/procedure_t7.sql
git ls-files --eol -- '*.sql' | awk '{print $2}' | sort | uniq -c
```

Saída:

```
ab28cc3 chore(git): *.sql eol=lf
3a17496 docs(entregas): janela do item 6, origem de p_ref_aprovacao e verificacao CRLF
149658b docs(entregas): cabecalho do ops_kill.sql v2 aponta para a migracao em 2 partes
--- git status --short . (vazio)
--- check-attr
scripts/procedure_t7.sql: text: set
scripts/procedure_t7.sql: eol: lf
--- ls-files eol
     25 w/lf
     50 w/none
```

Resultado: igual ao esperado (25 w/lf, 50 w/none, nenhum w/crlf; status vazio).

### A2. Verificador CRLF

Comando:

```
python -I "$W/verifica_crlf.py" "<projeto real>"
```

Saída:

```
RAIZ=C:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT
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

Resultado: igual ao esperado (COM_CRLF=0, RESULTADO: PASSA).

### A3. Suíte sem conexão

Comando:

```
python -m pytest -q -p no:cacheprovider
```

Saída (final):

```
..................................................sss..s..ss.ss......... [ 52%]
.........................................................ssssssss        [100%]
============================== warnings summary ===============================
..\..\..\..\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: 13 warnings
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    if asyncio.iscoroutinefunction(func):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
121 passed, 16 skipped, 13 warnings in 19.35s
EXIT=0
```

Resultado: 121 passed, 16 skipped, código de saída 0. Igual ao esperado.

### A4. Greps de regressão

Comandos e saídas:

```
grep -rn 'inst_id", 1' src app.py --exclude-dir=__pycache__ | wc -l
0
grep -n '"default"' src/tools/oracle_dba.py | wc -l
0
grep -rn 'status_banco' src app.py --exclude-dir=__pycache__ | wc -l
13
grep -rn 'status_banco' src app.py --exclude-dir=__pycache__ | cut -d: -f1 | sort | uniq -c
     13 src/tools/oracle_dba.py
grep -rn --include='*.py' --exclude-dir=.venv --exclude-dir=venv --exclude-dir=site-packages --exclude-dir=.git --exclude-dir=__pycache__ 'ALTER SYSTEM' . | wc -l
0
```

Resultado: igual ao esperado (0, 0, 13 só em oracle_dba.py, 0).

### A5. Logs (três caminhos distintos)

Comando:

```
stat -c '%n size=%s mtime=%y' data/logs/kill_approval.log auditoria_oracle.log data/logs/auditoria_oracle.log
```

Saída:

```
data/logs/kill_approval.log size=303 mtime=2026-11-17 12:39:39.063003600 -0300
auditoria_oracle.log size=38366 mtime=2026-11-15 17:35:17.265046800 -0300
data/logs/auditoria_oracle.log size=38366 mtime=2026-11-15 17:35:17.265046800 -0300
```

Resultado: igual ao esperado.

---

## PARTE B: ensaio do rollback de db/ops_kill.sql no clone (sem Oracle)

### B1. Ensaio

Comando:

```
python -I "$W/ensaio_rollback.py" "<projeto real>" "$C"
```

Saída:

```
== 0. estado inicial do clone
db/ops_kill.sql clone: bloco v1 sha=4823ecca4cfd8b21 | real HEAD v1 sha=4823ecca4cfd8b21 | igual=True
== 1. aplica v2 (proposta) em db/ops_kill.sql no clone
bloco atual sha=3bc1e26e111a0c8c | v2 sha=3bc1e26e111a0c8c | argumentos kill_session na spec=0

022198b ensaio: aplica v2
== 2. rollback: substitui spec+body pelo bloco de rollback_ops_kill_v1.sql (tabela v2 mantida)

6348f21 ensaio: rollback spec/body v1
022198b ensaio: aplica v2
cc1751a simulacao item 9
== 3. conferência
bloco spec+body apos rollback sha=4823ecca4cfd8b21 | v1 do repositorio real sha=4823ecca4cfd8b21 | IDENTICO=True
assinatura kill_session apos rollback:
  PROCEDURE kill_session (
    p_inst_id IN  NUMBER,
    p_sid     IN  NUMBER,
    p_serial  IN  NUMBER,
    p_status  OUT VARCHAR2
colunas v2 da tabela mantidas: True
INSERT do registra v1 usa lista de colunas explícita: True
RESULTADO: PASSA
EXIT=0
```

Resultado: RESULTADO: PASSA, código de saída 0.

### B2. Log e último commit do clone

Comandos:

```
git -C "$W/clone" log --oneline -4
git -C "$W/clone" show --stat HEAD
```

Saída:

```
6348f21 ensaio: rollback spec/body v1
022198b ensaio: aplica v2
cc1751a simulacao item 9
149658b docs(entregas): cabecalho do ops_kill.sql v2 aponta para a migracao em 2 partes

commit 6348f21cf359ca6a2d5bc0eeed2d24c5944b1a0d
Author: ensaio <ensaio@local>
Date:   Tue Nov 17 17:58:17 2026 -0300

    ensaio: rollback spec/body v1

 IA/PERSONAL_AGENT/db/ops_kill.sql | 101 ++++++--------------------------------
 1 file changed, 16 insertions(+), 85 deletions(-)
```

### B3. Testes de kill no clone

Comando:

```
python -m pytest -p no:cacheprovider -rs -v tests/test_oracle_kill.py
```

Saída:

```
============================= test session starts =============================
platform win32 -- Python 3.15.2, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\python.exe
rootdir: C:\Users\<usuario>\AppData\Local\Temp\claude\db29872ef7336ab6\474bbbe3-4d4e-49c8-bd9d-de39a3da8825\scratchpad\crlf_1_11\clone\IA\PERSONAL_AGENT
configfile: pytest.ini
plugins: anyio-4.16.0, langsmith-0.14.17
collecting ... collected 39 items

tests/test_oracle_kill.py::test_kill_param_invalido_sem_conexao PASSED   [  2%]
tests/test_oracle_kill.py::test_consultar_alvo_param_invalido_sem_conexao PASSED [  5%]
tests/test_oracle_kill.py::test_coletar_plano_sql_id_invalido_sem_conexao PASSED [  7%]
tests/test_oracle_kill.py::test_ausencia_oracle_user_diag_sem_conexao PASSED [ 10%]
tests/test_oracle_kill.py::test_ausencia_oracle_user_kill_sem_conexao PASSED [ 12%]
tests/test_oracle_kill.py::test_aprovacao_negada_ou_sem_identificacao_sem_chamada_kill PASSED [ 15%]
tests/test_oracle_kill.py::test_hash_canonico_determinismo_e_formato_log PASSED [ 17%]
tests/test_oracle_kill.py::test_alvo_background_retorna_nao_usuario_sem_prompt PASSED [ 20%]
tests/test_oracle_kill.py::test_usuario_protegido_retorna_usuario_protegido_sem_prompt[SYS] PASSED [ 23%]
tests/test_oracle_kill.py::test_usuario_protegido_retorna_usuario_protegido_sem_prompt[SYSTEM] PASSED [ 25%]
tests/test_oracle_kill.py::test_usuario_protegido_retorna_usuario_protegido_sem_prompt[DBSNMP] PASSED [ 28%]
tests/test_oracle_kill.py::test_usuario_protegido_retorna_usuario_protegido_sem_prompt[SYSMAN] PASSED [ 30%]
tests/test_oracle_kill.py::test_usuario_protegido_retorna_usuario_protegido_sem_prompt[OUTLN] PASSED [ 33%]
tests/test_oracle_kill.py::test_usuario_protegido_retorna_usuario_protegido_sem_prompt[STARTUPADMIN] PASSED [ 35%]
tests/test_oracle_kill.py::test_usuario_protegido_retorna_usuario_protegido_sem_prompt[OPS_OWNER] PASSED [ 38%]
tests/test_oracle_kill.py::test_usuario_protegido_retorna_usuario_protegido_sem_prompt[sys] PASSED [ 41%]
tests/test_oracle_kill.py::test_usuario_protegido_retorna_usuario_protegido_sem_prompt[Startupadmin] PASSED [ 43%]
tests/test_oracle_kill.py::test_usuario_nulo_tipo_user_retorna_usuario_protegido PASSED [ 46%]
tests/test_oracle_kill.py::test_lista_protegida_alinhada_ao_pacote PASSED [ 48%]
tests/test_oracle_kill.py::test_hash_divergente_na_reconsulta_retorna_alvo_alterado_sem_conta_kill PASSED [ 51%]
tests/test_oracle_kill.py::test_hash_identidade_ignora_campos_volateis PASSED [ 53%]
tests/test_oracle_kill.py::test_inst_id_ausente_param_invalido_sem_conexao PASSED [ 56%]
tests/test_oracle_kill.py::test_assinatura_sem_default_para_inst_id PASSED [ 58%]
tests/test_oracle_kill.py::test_aprovacao_expirada_vira_timeout[fronteira_300s] PASSED [ 61%]
tests/test_oracle_kill.py::test_aprovacao_expirada_vira_timeout[301s] PASSED [ 64%]
tests/test_oracle_kill.py::test_aprovacao_expirada_vira_timeout[1_dia] PASSED [ 66%]
tests/test_oracle_kill.py::test_aprovacao_expirada_vira_timeout[futuro] PASSED [ 69%]
tests/test_oracle_kill.py::test_aprovacao_dentro_do_ttl_executa[0s] PASSED [ 71%]
tests/test_oracle_kill.py::test_aprovacao_dentro_do_ttl_executa[299_999999s] PASSED [ 74%]
tests/test_oracle_kill.py::test_resultado_nao_usuario_com_aprovacao_nao_envia_email_de_aprovada PASSED [ 76%]
tests/test_oracle_kill.py::test_registro_log_contem_decisao_e_resultado_banco_separados PASSED [ 79%]
tests/test_oracle_kill.py::test_log_real_de_aprovacao_intacto PASSED     [ 82%]
tests/test_oracle_kill.py::test_caminho_padrao_redirecionado PASSED      [ 84%]
tests/test_oracle_kill.py::test_sandbox_kill_sessao_valida_encerrada SKIPPED [ 87%]
tests/test_oracle_kill.py::test_sandbox_kill_alvo_nao_encontrado SKIPPED [ 89%]
tests/test_oracle_kill.py::test_sandbox_kill_param_invalido SKIPPED      [ 92%]
tests/test_oracle_kill.py::test_sandbox_kill_propria_sessao_ou_usuario_protegido SKIPPED [ 94%]
tests/test_oracle_kill.py::test_sandbox_privilegio_negativo_startup_diag SKIPPED [ 97%]
tests/test_oracle_kill.py::test_sandbox_privilegio_negativo_startup_kill SKIPPED [100%]

============================== warnings summary ===============================
..\..\..\..\..\..\..\..\..\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: 13 warnings
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    if asyncio.iscoroutinefunction(func):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
SKIPPED [6] tests\conftest.py:71: Teste ignorado: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)
================= 33 passed, 6 skipped, 13 warnings in 0.81s ==================
EXIT=0
```

Resultado: 33 passed, 6 skipped. Os 6 skips são os `test_sandbox_*` de kill, com motivo "requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)".

---

## Resumo

| Passo | Esperado | Resultado |
|---|---|---|
| A1 | 25 w/lf, 50 w/none, status vazio | Igual |
| A2 | COM_CRLF=0, PASSA | Igual |
| A3 | 121 passed, 16 skipped | Igual (exit 0) |
| A4 | 0 / 0 / 13 em oracle_dba.py / 0 | Igual |
| A5 | kill_approval 303 B; auditoria 38366 B | Igual |
| B1 | PASSA | PASSA (exit 0) |
| B3 | testes sem conexão passam; sandbox de kill SKIPPED | 33 passed, 6 skipped |

Testes sandbox de kill pulados (ORACLE_SANDBOX ausente):
- test_sandbox_kill_sessao_valida_encerrada
- test_sandbox_kill_alvo_nao_encontrado
- test_sandbox_kill_param_invalido
- test_sandbox_kill_propria_sessao_ou_usuario_protegido
- test_sandbox_privilegio_negativo_startup_diag
- test_sandbox_privilegio_negativo_startup_kill

Nota: Os testes sandbox de kill não foram executados: exigem ORACLE_SANDBOX=1 e conexão Oracle, proibidas nesta rodada.

## Nota da sessão principal sobre a saída do B1

A linha `argumentos kill_session na spec=0` do passo 1 do ensaio está **errada por defeito do script de ensaio**: a expressão regular foi escrita com barra invertida duplicada dentro de string bruta (`\w`) e procura uma barra invertida literal, que não existe no texto, então conta zero. A spec v2 aplicada tem 9 parâmetros (ver `docs/entregas/1.11/item6/ops_kill.sql`). Essa contagem era só informativa; o critério de PASSA/FALHA do ensaio é a comparação textual do bloco spec+body restaurado com a v1 do repositório (`IDENTICO=True`), que não depende dela.

## Nota da sessão principal sobre o alcance da parte B

A parte B é um ensaio **só de arquivo**. Ela prova que o texto da spec e do body restaurados é idêntico ao da v1, mas **não prova que a v1 restaurada compila**. A checagem de `DBA_ERRORS` (vazio), VALID e `DBA_ARGUMENTS` com 4 argumentos só tem valor no **ensaio de banco em sandbox**, descrito em `docs/entregas/1.11/item6/implantacao.md`, seção 4.1. Esse ensaio é pré-requisito da janela de implantação.
