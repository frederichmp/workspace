# Verificação padrão (docs/PROCESSO.md §5, passos 0 a 3)

HEAD `e2c0742` (branch `item6/v2`); base `3b0c08d`; esperado 1435 passed e 16 skipped; `ORACLE_SANDBOX` no shell: ausente.

| Passo | Checagem | Esperado | Obtido | Status |
|---|---|---|---|---|
| 0 | perfil do Windows (só nomes) | nenhum nome proibido | nenhum | OK |
| 1 | git status | só o previsto | só o previsto | OK |
| 2 | pytest sem conexão | 0 failed, 1435 passed, 16 skipped | 1435 passed, 16 skipped, 0 failed | OK |
| 3.1 | conta Oracle legada | nenhuma linha | nenhuma linha | OK |
| 3.2 | SQL de sessão no Python | nenhuma linha | nenhuma linha | OK |
| 3.3 | recarga do .env | nenhuma linha | nenhuma linha | OK |
| 3.5 | código que liga o sandbox | nenhuma linha | nenhuma linha | OK |
| 3.6 | credencial em print ou log | nenhuma linha | 1 linha(s) (1ª: docs/entregas/revisao-subagentes-v2/medir_subagentes.py:58) | FALHA |
| 3.4 | load_dotenv | app.py e src/main.py, override=False | app.py e src/main.py, override=False | OK |
| 3.7 | registry/ e db/ | vazio, salvo PENDENTE APROVAÇÃO | vazio | OK |
| 3.8 | .env versionado | nenhum | nenhum | OK |

Resultado: FALHA. Saídas: docs/entregas/1.11/v2_refeito/correcao/k6/verif_k66_perfil.txt, docs/entregas/1.11/v2_refeito/correcao/k6/verif_k66_git_status.txt, docs/entregas/1.11/v2_refeito/correcao/k6/verif_k66_pytest.txt, docs/entregas/1.11/v2_refeito/correcao/k6/verif_k66_greps.txt.
