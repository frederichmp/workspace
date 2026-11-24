# Verificação padrão (docs/PROCESSO.md §5, passos 0 a 3)

HEAD `bb9f74b` (branch `item6/v2`); base `921e6ef`; esperado 1378 passed e 16 skipped; `ORACLE_SANDBOX` no shell: ausente.

| Passo | Checagem | Esperado | Obtido | Status |
|---|---|---|---|---|
| 0 | perfil do Windows (só nomes) | nenhum nome proibido | nenhum | OK |
| 1 | git status | só o previsto | só o previsto | OK |
| 2 | pytest sem conexão | 0 failed, 1378 passed, 16 skipped | 1378 passed, 16 skipped, 0 failed | OK |
| 3.1 | conta Oracle legada | nenhuma linha | nenhuma linha | OK |
| 3.2 | SQL de sessão no Python | nenhuma linha | 1 linha(s) (1ª: src/tools/oracle_dba.py:85) | FALHA |
| 3.3 | recarga do .env | nenhuma linha | nenhuma linha | OK |
| 3.5 | código que liga o sandbox | nenhuma linha | nenhuma linha | OK |
| 3.6 | credencial em print ou log | nenhuma linha | 1 linha(s) (1ª: docs/entregas/revisao-subagentes-v2/medir_subagentes.py:58) | FALHA |
| 3.4 | load_dotenv | app.py e src/main.py, override=False | app.py e src/main.py, override=False | OK |
| 3.7 | registry/ e db/ | vazio, salvo PENDENTE APROVAÇÃO | vazio | OK |
| 3.8 | .env versionado | nenhum | nenhum | OK |

Resultado: FALHA. Saídas: docs/entregas/1.11/v2_refeito/correcao/verif_c8_perfil.txt, docs/entregas/1.11/v2_refeito/correcao/verif_c8_git_status.txt, docs/entregas/1.11/v2_refeito/correcao/verif_c8_pytest.txt, docs/entregas/1.11/v2_refeito/correcao/verif_c8_greps.txt.
