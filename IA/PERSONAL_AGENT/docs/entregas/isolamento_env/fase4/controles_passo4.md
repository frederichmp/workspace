# Controles do Passo 4 (fase 4, D6.2 e D6.4)

Montados pelo `mecanico` (claude-sonnet-5-5) em scratchpad/passo4_ctrl/M0..M4 (git archive HEAD ede678a + os 2 testes do working tree, .env só `SENTINELA_P4=1`). As saídas do pytest não foram guardadas pelo agente; a sessão principal (claude-opus-5-5) reexecutou as 5 cópias, conferiu que os testes são idênticos ao working tree e conferiu o diff de cada mutação contra HEAD.

| Cópia | Mutação (diff contra HEAD) | Resultado (reexecução) |
|---|---|---|
| M0 | nenhuma | 14 passed |
| M1 | `executar_script`: `from dotenv import load_dotenv` + `load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env", override=True)` | 1 failed: `test_fluxo_nao_le_nem_recarrega_dotenv` |
| M2 | a mesma linha em `buscar_script_interno` | 1 failed: `test_fluxo_nao_le_nem_recarrega_dotenv` |
| M3 | conftest: `@pytest.fixture(scope="session")` (sem autouse) | 1 failed: `test_guard_oracle_sandbox_e_autouse_e_de_sessao` |
| M4 | conftest: `@pytest.fixture(autouse=True)` (sem scope) | 14 errors (ScopeMismatch na coleta; o agente relatou 12) |

L14:
- M3 com só `"guard_oracle_sandbox" in request.fixturenames` passaria: `inicializar_registro_testes` (autouse) depende da guard e a traz para `fixturenames`. A asserção sobre `_getautousenames` (API interna do pytest 9.2.0) fecha isso.
- M4 falha por construção (ScopeMismatch antes de qualquer asserção); `scope == "session"` fica como defesa redundante.
