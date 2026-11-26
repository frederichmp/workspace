# Tarefa 1.11, Passo 0: reproducao dos achados 1.1, 6.1 e 7.1

Fonte dos achados: `docs/entregas/1.10/revisao_gemini.md`, secoes 1, 6 e 7.

- Data: 2026-11-17
- Modelo que executou: Haiku 5.5 (claude-haiku-5-5)
- Python: `Python 3.15.2`
- Diretorio de trabalho do projeto: `c:\Users\<usuario>\OneDrive - <organizacao>\Workspace\IA\PERSONAL_AGENT`
- Material de reproducao (fora do projeto): `C:\Users\<usuario>\AppData\Local\Temp\claude\db29872ef7336ab6\474bbbe3-4d4e-49c8-bd9d-de39a3da8825\scratchpad\repro_1_11` (subpastas `limpa/`, `mut_rejeitado/`)
- Restricoes respeitadas: sem `ORACLE_SANDBOX`, sem leitura de `.env`, sem git que altere indice ou arvore, todas as execucoes com `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1`, pytest com `-p no:cacheprovider`.

## Git status antes

Comando: `git status --short .` (no diretorio do projeto)

```
(sem saida: arvore limpa dentro de "." antes da execucao)
```

## Achado 7.1: cópia limpa cria `auditoria_oracle.log` e `data/logs/` ao rodar pytest

### Comandos

```
cd "$R/limpa"
ls -la . data 2>&1
test -e auditoria_oracle.log; echo $?
test -e data/logs; echo $?
touch "$R/marcador_71"; sleep 1
env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
find . -newer "$R/marcador_71" \( -type f -o -type d \) | sort
test -e auditoria_oracle.log; echo $?
test -e data/logs; echo $?
ls -la auditoria_oracle.log data/logs 2>&1
```

### Saida bruta

```
== ls antes
.:
total 75
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:18 .
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:19 ..
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:17 .claude
-rw-r--r-- 1 <usuario> 197609  1653 Nov 17 17:17 .env.example
-rw-r--r-- 1 <usuario> 197609   447 Nov 17 17:17 .gitignore
-rw-r--r-- 1 <usuario> 197609  1663 Nov 17 17:17 CLAUDE.md
-rw-r--r-- 1 <usuario> 197609  1910 Nov 17 17:17 README.md
-rw-r--r-- 1 <usuario> 197609 30506 Nov 17 17:17 app.py
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:18 data
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:17 db
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:17 docs
-rw-r--r-- 1 <usuario> 197609   120 Nov 17 17:17 pytest.ini
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:17 registry
-rw-r--r-- 1 <usuario> 197609   314 Nov 17 17:17 requirements.txt
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:17 scripts
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:19 src
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:19 tests
drwxr-xr-x 1 <usuario> 197609     0 Nov 17 17:17 tools

data:
total 4
drwxr-xr-x 1 <usuario> 197609 0 Nov 17 17:18 .
drwxr-xr-x 1 <usuario> 197609 0 Nov 17 17:18 ..
drwxr-xr-x 1 <usuario> 197609 0 Nov 17 17:17 memory
auditoria_oracle.log exists rc=1
data/logs exists rc=1
== pytest
..................................................sssFFs..ss.ss......... [ 52%]
.........................................................ssssssss        [100%]
================================== FAILURES ===================================
________________ test_l1_procedure_t7_tipo_divergente_com_mock ________________

    def test_l1_procedure_t7_tipo_divergente_com_mock():
        """L1: Teste sem conexão para procedure_t7: tipo detectado == PLSQL, sem conexão quando registro for DDL."""
        from src.tools.registry import obter_caminho_scripts_dir, obter_script
    
        caminho_sql = obter_caminho_scripts_dir() / "procedure_t7.sql"
        conteudo_sql = caminho_sql.read_text(encoding="utf-8")
        valido, cod_motivo, msg_erro, sql_exec, tipo_detectado = tokenizar_e_validar_sql(conteudo_sql)
    
        assert valido is True
        assert tipo_detectado == "PLSQL"
    
        # Simula o registro declarando procedure_t7 como DDL
        entrada_real = obter_script("procedure_t7")
        assert entrada_real is not None
        entrada_mock = entrada_real.model_copy(update={"tipo": "DDL"})
    
        with patch("src.tools.executor.obter_script", return_value=entrada_mock), \
             patch("oracledb.connect") as mock_connect:
            saida_str = executar_script("procedure_t7", {})
            resultado = json.loads(saida_str)
    
            assert resultado["status"] == "recusado"
>           assert resultado["motivo"] == "TIPO_DIVERGENTE"
E           AssertionError: assert 'HASH_DIVERGENTE' == 'TIPO_DIVERGENTE'
E             
E             - TIPO_DIVERGENTE
E             + HASH_DIVERGENTE

tests\test_executor.py:228: AssertionError
_____________________ test_t8_diretivas_sqlplus_recusadas _____________________

    def test_t8_diretivas_sqlplus_recusadas():
        """T8: Diretivas exclusivas do SQL*Plus (SET, '/') são recusadas sem conectar."""
        with patch("oracledb.connect") as mock_connect:
            res_set = json.loads(executar_script("diretiva_sqlplus_t8", {}))
            assert res_set["status"] == "recusado"
>           assert res_set["motivo"] == "DIRETIVA_SQLPLUS"
E           AssertionError: assert 'HASH_DIVERGENTE' == 'DIRETIVA_SQLPLUS'
E             
E             - DIRETIVA_SQLPLUS
E             + HASH_DIVERGENTE

tests\test_executor.py:240: AssertionError
============================== warnings summary ===============================
..\..\..\..\..\..\..\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: 13 warnings
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    if asyncio.iscoroutinefunction(func):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/test_executor.py::test_l1_procedure_t7_tipo_divergente_com_mock
FAILED tests/test_executor.py::test_t8_diretivas_sqlplus_recusadas - Assertio...
2 failed, 119 passed, 16 skipped, 13 warnings in 19.39s
EXIT=1
== find newer
.
./auditoria_oracle.log
./data
./data/logs
./data/logs/auditoria_oracle.log
== test -e depois
auditoria_oracle.log rc=0
data/logs rc=0
-rw-r--r-- 1 <usuario> 197609 0 Nov 17 17:19 auditoria_oracle.log

data/logs:
total 0
drwxr-xr-x 1 <usuario> 197609 0 Nov 17 17:19 .
drwxr-xr-x 1 <usuario> 197609 0 Nov 17 17:19 ..
-rw-r--r-- 1 <usuario> 197609 0 Nov 17 17:19 auditoria_oracle.log
```

Observacao: as duas falhas da copia limpa (`test_l1_procedure_t7_tipo_divergente_com_mock` e `test_t8_diretivas_sqlplus_recusadas`, ambas com `HASH_DIVERGENTE`) nao fazem parte dos achados 1.1, 6.1 ou 7.1. Foram registradas por completude.

Reproduz: SIM. Criterio: apos o pytest na copia limpa, surgiram `auditoria_oracle.log` na raiz e `data/logs/auditoria_oracle.log` (ambos com 0 bytes), e `data/logs/` foi criado. Antes da execucao, os tres caminhos nao existiam (`test -e` retornou 1).

## Achado 6.1: kill executado no ramo REJEITADO/TIMEOUT

### Comandos

```
cat "$R/mutacao.diff"
cd "$R/mut_rejeitado"
env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider -rf
env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider "tests/test_oracle_kill.py::test_aprovacao_negada_ou_sem_identificacao_sem_chamada_kill"
```

### Mutacao aplicada (`mutacao.diff`)

```
--- limpa/src/tools/oracle_dba.py	2026-11-17 17:17:50.000000000 -0300
+++ mut_rejeitado/src/tools/oracle_dba.py	2026-11-17 17:19:04.088933000 -0300
@@ -1083,6 +1083,7 @@
         motivo = "APROVACAO_EXPIRADA"
 
     if decisao != "APROVADO":
+        executar_kill_verificado(inst_id=inst_id, sid=sid, serial=serial, hash_aprovado=hash_aprovado)  # MUTACAO 1.11 passo 0
         if motivo is None:
             motivo = "TIMEOUT_APROVACAO" if decisao == "TIMEOUT" else "REJEITADO_PELO_APROVADOR"
         aprovador_registro = aprovador_limpo or "NAO_INFORMADO"
```

### Saida bruta: pytest completo na copia mutada

```
..................................................sssFFs..ss.ss......... [ 52%]
..............FF.....F.........................FFFF......ssssssss        [100%]
================================== FAILURES ===================================
________________ test_l1_procedure_t7_tipo_divergente_com_mock ________________

    def test_l1_procedure_t7_tipo_divergente_com_mock():
        """L1: Teste sem conexão para procedure_t7: tipo detectado == PLSQL, sem conexão quando registro for DDL."""
        from src.tools.registry import obter_caminho_scripts_dir, obter_script
    
        caminho_sql = obter_caminho_scripts_dir() / "procedure_t7.sql"
        conteudo_sql = caminho_sql.read_text(encoding="utf-8")
        valido, cod_motivo, msg_erro, sql_exec, tipo_detectado = tokenizar_e_validar_sql(conteudo_sql)
    
        assert valido is True
        assert tipo_detectado == "PLSQL"
    
        # Simula o registro declarando procedure_t7 como DDL
        entrada_real = obter_script("procedure_t7")
        assert entrada_real is not None
        entrada_mock = entrada_real.model_copy(update={"tipo": "DDL"})
    
        with patch("src.tools.executor.obter_script", return_value=entrada_mock), \
             patch("oracledb.connect") as mock_connect:
            saida_str = executar_script("procedure_t7", {})
            resultado = json.loads(saida_str)
    
            assert resultado["status"] == "recusado"
>           assert resultado["motivo"] == "TIPO_DIVERGENTE"
E           AssertionError: assert 'HASH_DIVERGENTE' == 'TIPO_DIVERGENTE'
E             
E             - TIPO_DIVERGENTE
E             + HASH_DIVERGENTE

tests\test_executor.py:228: AssertionError
_____________________ test_t8_diretivas_sqlplus_recusadas _____________________

    def test_t8_diretivas_sqlplus_recusadas():
        """T8: Diretivas exclusivas do SQL*Plus (SET, '/') são recusadas sem conectar."""
        with patch("oracledb.connect") as mock_connect:
            res_set = json.loads(executar_script("diretiva_sqlplus_t8", {}))
            assert res_set["status"] == "recusado"
>           assert res_set["motivo"] == "DIRETIVA_SQLPLUS"
E           AssertionError: assert 'HASH_DIVERGENTE' == 'DIRETIVA_SQLPLUS'
E             
E             - DIRETIVA_SQLPLUS
E             + HASH_DIVERGENTE

tests\test_executor.py:240: AssertionError
_____________________________ test_cli_rejeitado ______________________________

cenario = <function cenario.<locals>.executar at 0x000001F074BC73D0>

    def test_cli_rejeitado(cenario):
        r = cenario([_linha_alvo()], None, ["dba", "N"], kill_permitido=False)
>       assert r.consultas_diag == 1
E       assert 2 == 1
E        +  where 2 = namespace(oracle=<tests.fakes_oracle._OracleFake object at 0x000001F074AA3750>, llm=<tests.test_fluxo_cli._LLMFalso ob...': "Intervenção não aprovada (REJEITADO/REJEITADO_PELO_APROVADOR) por 'dba'. Nenhuma chamada à conta KILL foi feita."}).consultas_diag

tests\test_fluxo_cli.py:197: AssertionError
------------------------------ Captured log call ------------------------------
INFO     root:main.py:214 AGENTE ACIONOU: matar_sessao_oracle | PARÂMETROS: {'inst_id': 1, 'sid': 101, 'serial': 202}
WARNING  tools.oracle_dba:oracle_dba.py:875 KILL BLOQUEADO NA RECONSULTA: ALVO_NAO_ENCONTRADO | inst_id=1, sid=101, serial=202 | hash_aprovado=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
WARNING  tools.oracle_dba:oracle_dba.py:1100 AUDITORIA HITL: REJEITADO (REJEITADO_PELO_APROVADOR) por dba (CLI) | inst_id=1, sid=101, serial=202 | Hash=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
INFO     root:main.py:279 RESULTADO ORACLE: {"status": "abortado", "decisao": "REJEITADO", "motivo": "REJEITADO_PELO_APROVADOR", "resultado_banco": null, "executado": false, "mensagem": "Intervenção não aprovada (REJEITADO/REJEITADO_PELO_APROVADOR) por 'dba'. Nenhuma chamada à conta KILL foi feita."}
__________________________ test_cli_aprovador_vazio ___________________________

cenario = <function cenario.<locals>.executar at 0x000001F074BD8300>

    def test_cli_aprovador_vazio(cenario):
        r = cenario([_linha_alvo()], None, [""], kill_permitido=False)
>       assert r.consultas_diag == 1
E       assert 2 == 1
E        +  where 2 = namespace(oracle=<tests.fakes_oracle._OracleFake object at 0x000001F074B27BB0>, llm=<tests.test_fluxo_cli._LLMFalso ob..."Intervenção não aprovada (REJEITADO/SEM_IDENTIFICACAO) por 'NAO_INFORMADO'. Nenhuma chamada à conta KILL foi feita."}).consultas_diag

tests\test_fluxo_cli.py:210: AssertionError
------------------------------ Captured log call ------------------------------
INFO     root:main.py:214 AGENTE ACIONOU: matar_sessao_oracle | PARÂMETROS: {'inst_id': 1, 'sid': 101, 'serial': 202}
WARNING  tools.oracle_dba:oracle_dba.py:875 KILL BLOQUEADO NA RECONSULTA: ALVO_NAO_ENCONTRADO | inst_id=1, sid=101, serial=202 | hash_aprovado=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
WARNING  tools.oracle_dba:oracle_dba.py:1100 AUDITORIA HITL: REJEITADO (SEM_IDENTIFICACAO) por NAO_INFORMADO (CLI) | inst_id=1, sid=101, serial=202 | Hash=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
INFO     root:main.py:279 RESULTADO ORACLE: {"status": "abortado", "decisao": "REJEITADO", "motivo": "SEM_IDENTIFICACAO", "resultado_banco": null, "executado": false, "mensagem": "Intervenção não aprovada (REJEITADO/SEM_IDENTIFICACAO) por 'NAO_INFORMADO'. Nenhuma chamada à conta KILL foi feita."}
_____________________________ test_web_rejeitado ______________________________

montar_web = <function montar_web.<locals>._fabrica at 0x000001F07A14C930>

    def test_web_rejeitado(montar_web):
        amb = montar_web([_linha_alvo()], kill_permitido=False)
        _ate_painel_hitl(amb)
        _decidir(amb, "btn_hitl_abort", "dba_teste")
    
>       assert amb.oracle.conexoes.count(USER_DIAG_FAKE) == 1
E       AssertionError: assert 2 == 1
E        +  where 2 = <built-in method count of list object at 0x000001F07A585E40>('diag_teste_fake')
E        +    where <built-in method count of list object at 0x000001F07A585E40> = ['diag_teste_fake', 'diag_teste_fake'].count
E        +      where ['diag_teste_fake', 'diag_teste_fake'] = <tests.fakes_oracle._OracleFake object at 0x000001F07A0B2F50>.conexoes
        +        where <tests.fakes_oracle._OracleFake object at 0x000001F07A0B2F50> = <tests.test_fluxo_web._Ambiente object at 0x000001F07A1290F0>.oracle

tests\test_fluxo_web.py:287: AssertionError
---------------------------- Captured stderr call -----------------------------
2026-11-17 17:20:18.648 Thread 'MainThread': missing ScriptRunContext! This warning can be ignored when running in bare mode.
------------------------------ Captured log call ------------------------------
WARNING  streamlit.runtime.scriptrunner_utils.script_run_context:script_run_context.py:522 Thread 'MainThread': missing ScriptRunContext! This warning can be ignored when running in bare mode.
WARNING  tools.oracle_dba:oracle_dba.py:875 KILL BLOQUEADO NA RECONSULTA: ALVO_NAO_ENCONTRADO | inst_id=1, sid=101, serial=202 | hash_aprovado=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
WARNING  tools.oracle_dba:oracle_dba.py:1100 AUDITORIA HITL: REJEITADO (REJEITADO_PELO_APROVADOR) por dba_teste (Web UI) | inst_id=1, sid=101, serial=202 | Hash=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
____________ test_aprovacao_expirada_vira_timeout[fronteira_300s] _____________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001F07A623000>
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-37/test_aprovacao_expirada_vira_t0')
ambiente_fake = [], delta = datetime.timedelta(seconds=300)

    @pytest.mark.parametrize(
        "delta",
        [timedelta(seconds=300), timedelta(seconds=301), timedelta(days=1), timedelta(seconds=-1)],
        ids=["fronteira_300s", "301s", "1_dia", "futuro"],
    )
    def test_aprovacao_expirada_vira_timeout(monkeypatch, tmp_path, ambiente_fake, delta):
        """APROVADO fora de [0, TTL) -> TIMEOUT/APROVACAO_EXPIRADA, sem reconsulta, 0 KILL, 0 e-mail."""
        assert oracle_dba.APROVACAO_TTL_SEGUNDOS == 300
        oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo()], kill_permitido=False))
        log = tmp_path / "kill.log"
        cap = {}
    
        desfecho = conduzir_kill_hitl(
            dict(ARGS_ALVO),
            solicitar_aprovacao=_solicitar_capturando(cap),
            canal="TESTE",
            caminho_log=log,
            agora=_relogio_relativo(cap, delta),
        )
    
        assert desfecho["prompt_exibido"] is True
        assert desfecho["decisao"] == "TIMEOUT"
        assert desfecho["motivo"] == "APROVACAO_EXPIRADA"
        assert desfecho["executado"] is False
        assert desfecho["resultado_banco"] is None
        assert desfecho["assunto_email"] is None
        assert oracle_fake.conexoes_kill == []
>       assert oracle_fake.conexoes.count(USER_DIAG_FAKE) == 1, "não deve haver reconsulta DIAG após expirar"
E       AssertionError: não deve haver reconsulta DIAG após expirar
E       assert 2 == 1
E        +  where 2 = <built-in method count of list object at 0x000001F07A741280>('diag_teste_fake')
E        +    where <built-in method count of list object at 0x000001F07A741280> = ['diag_teste_fake', 'diag_teste_fake'].count
E        +      where ['diag_teste_fake', 'diag_teste_fake'] = <tests.fakes_oracle._OracleFake object at 0x000001F07A621CC0>.conexoes

tests\test_oracle_kill.py:481: AssertionError
------------------------------ Captured log call ------------------------------
WARNING  src.tools.oracle_dba:oracle_dba.py:1078 AUDITORIA HITL: aprovação expirada (TESTE) | preparado_em='2026-11-17T20:20:26.699098+00:00' | decidido_em=2026-11-17T20:25:26.699098+00:00 | TTL=300s
WARNING  src.tools.oracle_dba:oracle_dba.py:875 KILL BLOQUEADO NA RECONSULTA: ALVO_NAO_ENCONTRADO | inst_id=1, sid=101, serial=202 | hash_aprovado=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
WARNING  src.tools.oracle_dba:oracle_dba.py:1100 AUDITORIA HITL: TIMEOUT (APROVACAO_EXPIRADA) por dba_teste (TESTE) | inst_id=1, sid=101, serial=202 | Hash=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
_________________ test_aprovacao_expirada_vira_timeout[301s] __________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001F07A158B40>
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-37/test_aprovacao_expirada_vira_t1')
ambiente_fake = [], delta = datetime.timedelta(seconds=301)

    @pytest.mark.parametrize(
        "delta",
        [timedelta(seconds=300), timedelta(seconds=301), timedelta(days=1), timedelta(seconds=-1)],
        ids=["fronteira_300s", "301s", "1_dia", "futuro"],
    )
    def test_aprovacao_expirada_vira_timeout(monkeypatch, tmp_path, ambiente_fake, delta):
        """APROVADO fora de [0, TTL) -> TIMEOUT/APROVACAO_EXPIRADA, sem reconsulta, 0 KILL, 0 e-mail."""
        assert oracle_dba.APROVACAO_TTL_SEGUNDOS == 300
        oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo()], kill_permitido=False))
        log = tmp_path / "kill.log"
        cap = {}
    
        desfecho = conduzir_kill_hitl(
            dict(ARGS_ALVO),
            solicitar_aprovacao=_solicitar_capturando(cap),
            canal="TESTE",
            caminho_log=log,
            agora=_relogio_relativo(cap, delta),
        )
    
        assert desfecho["prompt_exibido"] is True
        assert desfecho["decisao"] == "TIMEOUT"
        assert desfecho["motivo"] == "APROVACAO_EXPIRADA"
        assert desfecho["executado"] is False
        assert desfecho["resultado_banco"] is None
        assert desfecho["assunto_email"] is None
        assert oracle_fake.conexoes_kill == []
>       assert oracle_fake.conexoes.count(USER_DIAG_FAKE) == 1, "não deve haver reconsulta DIAG após expirar"
E       AssertionError: não deve haver reconsulta DIAG após expirar
E       assert 2 == 1
E        +  where 2 = <built-in method count of list object at 0x000001F07A70B0C0>('diag_teste_fake')
E        +    where <built-in method count of list object at 0x000001F07A70B0C0> = ['diag_teste_fake', 'diag_teste_fake'].count
E        +      where ['diag_teste_fake', 'diag_teste_fake'] = <tests.fakes_oracle._OracleFake object at 0x000001F07A158750>.conexoes

tests\test_oracle_kill.py:481: AssertionError
------------------------------ Captured log call ------------------------------
WARNING  src.tools.oracle_dba:oracle_dba.py:1078 AUDITORIA HITL: aprovação expirada (TESTE) | preparado_em='2026-11-17T20:20:26.711281+00:00' | decidido_em=2026-11-17T20:25:27.711281+00:00 | TTL=300s
WARNING  src.tools.oracle_dba:oracle_dba.py:875 KILL BLOQUEADO NA RECONSULTA: ALVO_NAO_ENCONTRADO | inst_id=1, sid=101, serial=202 | hash_aprovado=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
WARNING  src.tools.oracle_dba:oracle_dba.py:1100 AUDITORIA HITL: TIMEOUT (APROVACAO_EXPIRADA) por dba_teste (TESTE) | inst_id=1, sid=101, serial=202 | Hash=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
_________________ test_aprovacao_expirada_vira_timeout[1_dia] _________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001F07A158910>
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-37/test_aprovacao_expirada_vira_t2')
ambiente_fake = [], delta = datetime.timedelta(days=1)

    @pytest.mark.parametrize(
        "delta",
        [timedelta(seconds=300), timedelta(seconds=301), timedelta(days=1), timedelta(seconds=-1)],
        ids=["fronteira_300s", "301s", "1_dia", "futuro"],
    )
    def test_aprovacao_expirada_vira_timeout(monkeypatch, tmp_path, ambiente_fake, delta):
        """APROVADO fora de [0, TTL) -> TIMEOUT/APROVACAO_EXPIRADA, sem reconsulta, 0 KILL, 0 e-mail."""
        assert oracle_dba.APROVACAO_TTL_SEGUNDOS == 300
        oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo()], kill_permitido=False))
        log = tmp_path / "kill.log"
        cap = {}
    
        desfecho = conduzir_kill_hitl(
            dict(ARGS_ALVO),
            solicitar_aprovacao=_solicitar_capturando(cap),
            canal="TESTE",
            caminho_log=log,
            agora=_relogio_relativo(cap, delta),
        )
    
        assert desfecho["prompt_exibido"] is True
        assert desfecho["decisao"] == "TIMEOUT"
        assert desfecho["motivo"] == "APROVACAO_EXPIRADA"
        assert desfecho["executado"] is False
        assert desfecho["resultado_banco"] is None
        assert desfecho["assunto_email"] is None
        assert oracle_fake.conexoes_kill == []
>       assert oracle_fake.conexoes.count(USER_DIAG_FAKE) == 1, "não deve haver reconsulta DIAG após expirar"
E       AssertionError: não deve haver reconsulta DIAG após expirar
E       assert 2 == 1
E        +  where 2 = <built-in method count of list object at 0x000001F07A723C40>('diag_teste_fake')
E        +    where <built-in method count of list object at 0x000001F07A723C40> = ['diag_teste_fake', 'diag_teste_fake'].count
E        +      where ['diag_teste_fake', 'diag_teste_fake'] = <tests.fakes_oracle._OracleFake object at 0x000001F07A158980>.conexoes

tests\test_oracle_kill.py:481: AssertionError
------------------------------ Captured log call ------------------------------
WARNING  src.tools.oracle_dba:oracle_dba.py:1078 AUDITORIA HITL: aprovação expirada (TESTE) | preparado_em='2026-11-17T20:20:26.721484+00:00' | decidido_em=2026-11-18T20:20:26.721484+00:00 | TTL=300s
WARNING  src.tools.oracle_dba:oracle_dba.py:875 KILL BLOQUEADO NA RECONSULTA: ALVO_NAO_ENCONTRADO | inst_id=1, sid=101, serial=202 | hash_aprovado=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
WARNING  src.tools.oracle_dba:oracle_dba.py:1100 AUDITORIA HITL: TIMEOUT (APROVACAO_EXPIRADA) por dba_teste (TESTE) | inst_id=1, sid=101, serial=202 | Hash=bdf0476bc8e8f8def4e86f2980ab4cb9899b4d861cc3d26d354aead582c05681
________________ test_aprovacao_expirada_vira_timeout[futuro] _________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x000001F07A15BAF0>
tmp_path = WindowsPath('C:/Users/<usuario>/AppData/Local/Temp/pytest-of-<usuario>/pytest-37/test_aprovacao_expirada_vira_t3')
ambiente_fake = [], delta = datetime.timedelta(days=-1, seconds=86399)

    @pytest.mark.parametrize(
        "delta",
        [timedelta(seconds=300), timedelta(seconds=301), timedelta(days=1), timedelta(seconds=-1)],
        ids=["fronteira_300s", "301s", "1_dia", "futuro"],
    )
    def test_aprovacao_expirada_vira_timeout(monkeypatch, tmp_path, ambiente_fake, delta):
        """APROVADO fora de [0, TTL) -> TIMEOUT/APROVACAO_EXPIRADA, sem reconsulta, 0 KILL, 0 e-mail."""
        assert oracle_dba.APROVACAO_TTL_SEGUNDOS == 300
        oracle_fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo()], kill_permitido=False))
        log = tmp_path / "kill.log"
        cap = {}
    
        desfecho = conduzir_kill_hitl(
            dict(ARGS_ALVO),
            solicitar_aprovacao=_solicitar_capturando(cap),
            canal="TESTE",
            caminho_log=log,
            agora=_relogio_relativo(cap, delta),
        )
    
        assert desfecho["prompt_exibido"] is True
        assert desfecho["decisao"] == "TIMEOUT"
        assert desfecho["motivo"] == "APROVACAO_EXPIRADA"
        assert desfecho["executado"] is False
        assert desfecho["resultado_banco"] is None
        assert desfecho["assunto_email"] is None
        assert oracle_fake.conexoes_kill == []
>       assert oracle_fake.conexoes.count(USER_DIAG_FAKE) == 1, "não deve haver reconsulta DIAG após expirar"
E       AssertionError: não deve haver reconsulta DIAG após expirar
E       assert 2 == 1
E        +  where 2 = <built-in method count of list object at 0x000001F07A6626C0>('diag_teste_fake')
E        +    where <built-in method count of list object at 0x000001F07A6626C0> = ['diag_teste_fake', 'diag_teste_fake'].count
E        +      where ['diag_teste_fake', 'diag_teste_fake'] = <tests.fakes_oracle._OracleFake object at 0x000001F07A15B0E0>.conexoes

tests\test_oracle_kill.py:481: AssertionError
============================== warnings summary ===============================
..\..\..\..\..\..\..\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: 13 warnings
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    if asyncio.iscoroutinefunction(func):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED tests/test_executor.py::test_l1_procedure_t7_tipo_divergente_com_mock
FAILED tests/test_executor.py::test_t8_diretivas_sqlplus_recusadas - Assertio...
FAILED tests/test_fluxo_cli.py::test_cli_rejeitado - assert 2 == 1
FAILED tests/test_fluxo_cli.py::test_cli_aprovador_vazio - assert 2 == 1
FAILED tests/test_fluxo_web.py::test_web_rejeitado - AssertionError: assert 2...
FAILED tests/test_oracle_kill.py::test_aprovacao_expirada_vira_timeout[fronteira_300s]
FAILED tests/test_oracle_kill.py::test_aprovacao_expirada_vira_timeout[301s]
FAILED tests/test_oracle_kill.py::test_aprovacao_expirada_vira_timeout[1_dia]
FAILED tests/test_oracle_kill.py::test_aprovacao_expirada_vira_timeout[futuro]
9 failed, 112 passed, 16 skipped, 13 warnings in 19.18s
EXIT=1
```

### Saida bruta: teste pontual do item c, na copia mutada

```
.                                                                        [100%]
============================== warnings summary ===============================
..\..\..\..\..\..\..\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: 13 warnings
  C:\Users\<usuario>\AppData\Local\Python\pythoncore-3.15-64\Lib\site-packages\langsmith\_internal\_beta_decorator.py:92: DeprecationWarning: 'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead
    if asyncio.iscoroutinefunction(func):

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 13 warnings in 0.70s
EXIT=0
```

Resumo do 6.1:
- Copia mutada: 9 failed, 112 passed, 16 skipped (EXIT=1).
- Falhas que nao dependem da mutacao (ja existem na copia limpa): `test_l1_procedure_t7_tipo_divergente_com_mock`, `test_t8_diretivas_sqlplus_recusadas`.
- Falhas introduzidas pela mutacao (esperadas no ramo REJEITADO/TIMEOUT, com reconsulta DIAG extra): `test_cli_rejeitado`, `test_cli_aprovador_vazio`, `test_web_rejeitado`, `test_aprovacao_expirada_vira_timeout[fronteira_300s]`, `[301s]`, `[1_dia]`, `[futuro]`.
- Teste pontual `test_aprovacao_negada_ou_sem_identificacao_sem_chamada_kill`: PASSOU sob a mutacao (1 passed, EXIT=0). Ele nao detecta a chamada extra.

Reproduz: SIM. Criterio: o teste pontual `test_aprovacao_negada_ou_sem_identificacao_sem_chamada_kill` passa na copia mutada, embora a mutacao chame `executar_kill_verificado` no ramo REJEITADO/TIMEOUT. A chamada aparece nos logs como `KILL BLOQUEADO NA RECONSULTA: ALVO_NAO_ENCONTRADO` seguido de auditoria, e outros testes (`test_cli_rejeitado`, `test_web_rejeitado`) falham por contagem extra de reconsulta DIAG.

## Achado 1.1: kill executado antes do registro de log

### Comandos

```
cd "$R"
env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -I falha_log.py "$R/limpa"
```

### Saida bruta

```
conexoes: ['diag_teste_fake', 'diag_teste_fake', 'kill_teste_fake']
conexoes_kill: ['kill_teste_fake']
sql_executado (conta KILL):
   KILL | BEGIN OPS_OWNER.PKG_OPS_KILL.KILL_SESSION( p_inst_id => :p_inst_id, p_sid => :p_sid, p_serial => :p_serial, p_status => :p_status ); END; | {'p_inst_id': 1, 'p_sid': 101, 'p_serial': 202, 'p_status': <tests.fakes_oracle._VarFake object at 0x00000230FCB80590>}
excecao: OSError: disco cheio (simulado)
resultado: (n/a)
emails capturados: 0
```

Reproduz: SIM. Criterio: `conexoes_kill == ['kill_teste_fake']` (kill executado) e excecao `OSError` do registro de log, levantada depois do kill (`registrar_log_aprovacao_kill` substituido por funcao que falha). O `KILL_SESSION` ja foi emitido quando o log falhou.

## Git status depois

Comando: `git status --short .` (no diretorio do projeto), executado apos a gravacao deste arquivo.

```
?? docs/entregas/1.11/
```

## Veredito

| Achado | Reproduz | Evidencia |
|---|---|---|
| 1.1 | SIM | `conexoes_kill == ['kill_teste_fake']` e `OSError: disco cheio (simulado)` apos o kill |
| 6.1 | SIM | teste pontual `test_aprovacao_negada_ou_sem_identificacao_sem_chamada_kill` passa sob a mutacao; 7 testes adicionais falham por reconsulta DIAG extra |
| 7.1 | SIM | `auditoria_oracle.log` e `data/logs/auditoria_oracle.log` criados pelo pytest na copia limpa |
