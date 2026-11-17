# Entregas da tarefa 1.10

Diffs gravados pela sessão principal antes de cada commit; saídas de verificação gravadas pelo agente verificador (somente leitura do código).

- `commit1.diff` a `commit6.diff`: diff de cada um dos commits 1 a 6 da tarefa.
- `verif_commit1.txt` a `verif_commit6.txt`: git status, pytest -q e greps de regressão de cada aceite.
- `pytest_v_rs_commit6.txt`: saída de `pytest -v -rs` após o commit 6 (motivos dos skips).

## Resumo final

- 121 passed, 16 skipped (todos por ORACLE_SANDBOX).
- Snapshot dos logs reais inalterado: `kill_approval.log` 303 bytes / 12:39:39; `auditoria_oracle.log` 38366 bytes / 2026-11-15 17:35:17.
- Greps de regressão limpos.
- Observação: o spike 5a (sem commit) foi POSITIVO e ficou fora do repositório.
