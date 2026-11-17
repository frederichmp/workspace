# Registro de Governança de Alteração de Hash e Conteúdo de Scripts

Histórico auditável de modificações de conteúdo, tipos e hashes em `registry/` e ferramentas associadas.
Conforme política de governança estrita, nenhuma alteração em ambiente operacional é considerada homologada sem aprovação formal por PR pelo responsável.

| Data | Commit | Autor | Arquivo / Item | Tipo de Alteração | Detalhe / Hash Anterior -> Hash Novo | Status |
|---|---|---|---|---|---|---|
| 2026-11-16 00:09:43 -0300 | `2fb0c27` | frederichmp | `registry/scripts.yaml` (`dml_tentativa_read_t11`) | Alteração de Hash | Recalculado automaticamente: `8e090aedac851979974da332a12f7c0e4836df335797f6dfa2e4b2efa17048f3` -> `1d5f0a70f17b95ab2bad38361d6e85efa2742a2aa3439b16c86c1e95b9d650d1` | NÃO APROVADO |
| 2026-11-16 00:09:43 -0300 | `2fb0c27` | frederichmp | `registry/scripts.yaml` (`select_como_dml_t18`) | Alteração de Hash | Recalculado automaticamente: `3d49728aba5d2f3ffd91c23ea3fb884f0de3d3ef847f02e3c5e3848f79aa5c0f` -> `0cde98d6d00bc8891e12bf6bcf8cf953099fc8240f89068b3e8ada9e04715ba1` | NÃO APROVADO |
| 2026-11-16 00:09:43 -0300 | `2fb0c27` | frederichmp | `registry/scripts.yaml` (`procedure_t7`) | Alteração de Metadado | Tipo alterado de DDL para PLSQL no registro | NÃO APROVADO |
| 2026-11-16 00:09:43 -0300 | `2fb0c27` | frederichmp | `registry/scripts.yaml` (`procedure_complex_t16`) | Alteração de Metadado | Tipo alterado de DDL para PLSQL no registro | NÃO APROVADO |
| 2026-11-16 00:09:43 -0300 | `2fb0c27` | frederichmp | `registry/scripts.yaml` (`select_como_dml_t18`) | Alteração de Metadado | Tipo alterado de DML para SELECT no registro | NÃO APROVADO |
| 2026-11-16 01:29:46 -0300 | `70d6b49` | frederichmp | `tools/verificar_registro.py` | Modificação de Código | Remoção da flag `--atualizar` e de lógica de mutação automática de hashes no registry | NÃO APROVADO |
| 2026-11-16 01:37:53 -0300 | `4defb91` | frederichmp | `registry/test_scripts.yaml` | Criação de Arquivo | Criação do arquivo de registro de testes com 19 fixtures separadas de homologados | NÃO APROVADO |
| 2026-11-16 01:37:53 -0300 | `4defb91` | frederichmp | `registry/scripts.yaml` | Modificação Estrutural | Reestruturação de entradas e remoção de cabeçalho de governança | NÃO APROVADO |
| 2026-11-16 01:37:53 -0300 | `4defb91` | frederichmp | `registry/test_scripts.yaml` (`select_como_dml_t18`) | Reversão de Hash | Hash revertido para `3d49728aba5d2f3ffd91c23ea3fb884f0de3d3ef847f02e3c5e3848f79aa5c0f` e tipo DML | NÃO APROVADO |
| 2026-11-16 01:37:53 -0300 | `4defb91` | frederichmp | `registry/test_scripts.yaml` (`dml_tentativa_read_t11`) | Alteração de Hash | Registrado hash `1d5f0a70f17b95ab2bad38361d6e85efa2742a2aa3439b16c86c1e95b9d650d1` | NÃO APROVADO |
| 2026-11-16 02:06:28 -0300 | `3b79ba7` | frederichmp | `registry/scripts.yaml` | Remoção de Conteúdo | Remoção de 118 linhas de fixtures de testes de `scripts.yaml`, mantendo apenas scripts de produção | NÃO APROVADO |
| 2026-11-16 02:06:37 -0300 | `d95a3e2` | frederichmp | `src/tools/oracle_dba.py` | Remoção de Conteúdo | Remoção da função legada `executar_script_customizado(sql_query)` | NÃO APROVADO |
| 2026-11-16 02:06:37 -0300 | `d95a3e2` | frederichmp | `app.py` e `src/main.py` | Remoção de Conteúdo | Remoção de roteamentos e referências a `executar_script_customizado` | NÃO APROVADO |
| 2026-11-16 02:06:37 -0300 | `d95a3e2` | frederichmp | `docs/CODIGO_COMPLETO_REVISAO.md` | Criação de Arquivo | Documentação snapshot de revisão contendo menções a ferramentas anteriores | NÃO APROVADO |
