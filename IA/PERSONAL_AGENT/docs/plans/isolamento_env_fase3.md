# Plano — isolamento do .env, fase 3 (achados da revisão Gemini)

**Status: APROVADO pelo responsável em 2026-11-18 13:37** (decisões 1 a 3 abaixo). Passo 0 (leitura) executado antes da aprovação.

## 1. Contexto

Pedido do responsável (2026-11-18): corrigir os achados da revisão adversarial do Gemini (`docs/entregas/revisao_fases_1_2/revisao_adversarial_gemini.md`) sobre as fases 1 e 2. Restrições: sem Oracle; sem ler, alterar ou criar `.env`; sem alterar `.vscode/settings.json`; sem push.

**Origem do arquivo de revisão:** não rastreado, criado às 12:28 fora desta sessão (registrado em L12 do `docs/PROCESSO.md`); indicado pelo responsável como fonte. Entra no commit deste plano sem alteração.

**Passo 0, reprodução** (`verificador`, claude-haiku-5-5; `docs/entregas/isolamento_env/reproducao_fase3.md`, 9 subprocessos isolados, returncode 0, perfil sem nomes proibidos, `git status` sem caminho fora do previsto):

| Achado | Cenário | Resultado |
|---|---|---|
| B4 | Web, chave nova no `.env` entre dois reruns do AppTest | **REPRODUZ**: `ORACLE_USER_KILL` ausente no run 1 e `kill_tardio_ficticio` no run 2 |
| B4 | CLI | não se aplica: sem rerun, nada recarrega (1 chamada) |
| C1 | `load_dotenv` mínimo com byte NUL | **REPRODUZ**: `ValueError: embedded null character` e a chave anterior já gravada |
| C1 | Web, `.env` fictício `ORACLE_SANDBOX=1` + linha com NUL, 2 reruns | **REPRODUZ**: `ORACLE_SANDBOX='1'` nos 2 runs e nenhum WARNING de descarte |
| C1 | CLI, mesmo fictício | **REPRODUZ**: `ValueError` no import e `ORACLE_SANDBOX='1'` em `os.environ` |
| A3 | `src.tools.oracle_dba` importado **antes** da entrada (cenário do revisor; é o que a suíte faz via `conftest.py:143`) | **REPRODUZ**: `DIRETORIO_LOG_APROVACAO` e `GEMINI_API_KEY` diferentes entre `src.tools.*` e `tools.*` |
| A3 | ordem de produção (só a entrada) | **NÃO REPRODUZIDO**: nenhum `src.tools.*` em `sys.modules` na carga; cópias iguais |

Os demais achados do revisor (B3, C2, C3, C4, D3, D6) são de desenho ou de cobertura e não exigem reprodução: os passos 3 e 4 os cobrem com teste e controle negativo.

## 2. Base

- Branch `isolamento-env`, HEAD `ba598f0`. Ela inclui os commits `49ad795`, `3cc241b` e `ba598f0` da tarefa `processo-subagentes`, de outra sessão (claude-opus-5-5), só de docs, com CLAUDE.md e `docs/PROCESSO.md` novos.
- Baseline: **199 passed, 16 skipped** (verificação da tarefa `processo-subagentes`; será reconferida pelo `verificador` antes do passo 1).
- Não rastreado de outra tarefa, que fica fora: `docs/entregas/processo-subagentes/`.

## 3. Arquivos por passo

| Passo | Arquivos | Quem (modelo) |
|---|---|---|
| 0 | `docs/entregas/isolamento_env/reproducao_fase3.md` | `verificador` (claude-haiku-5-5), **feito** |
| 1-D | `docs/entregas/isolamento_env/decisao_fase3.md` | `seguranca` (claude-opus-5-5): decide os passos 1, 2 e 3 (todos no §2 do PROCESSO) |
| 1 | `app.py`, `src/main.py`, teste novo `tests/test_carga_env_entrada.py` (casos novos) | sessão principal (claude-opus-5-5); teste pelo `mecanico` (claude-sonnet-5-5), em sequência |
| 2 | `src/tools/oracle_dba.py` (só a resolução do diretório de log); testes que leem `DIRETORIO_LOG_APROVACAO`/`CAMINHO_LOG_APROVACAO_PADRAO` | sessão principal; testes pelo `mecanico` |
| 3 | `app.py`, `src/main.py`; teste novo | sessão principal; teste pelo `mecanico` |
| 4 | `tests/test_conftest_sandbox_env.py`, `tests/test_env_em_execucao.py`, `tests/test_carga_env_entrada.py`, `tests/test_guard_sessao_sandbox.py`, `tests/test_isolamento_env.py`, `tests/test_oracle_kill.py`, `tests/test_executor.py` | `mecanico` |
| 5 | `docs/GOVERNANCA_LOG.md`, `docs/PROCESSO.md` §7, entregas | sessão principal |

Nunca dois agentes em `app.py`, `src/main.py` ou `oracle_dba.py`. Os passos 1, 2 e 3 são sequenciais.

## 4. Passos

**Prova exigida pelo responsável:** cada teste novo falha contra `d05577e`, em cópia fora do repositório (`git archive`, §5.4 do PROCESSO).
- Testes de comportamento novo (passos 1 a 3): falham na cópia de `d05577e` sem alteração.
- Testes de cobertura (passo 4, D6/D3): falham na cópia de `d05577e` com a mutação que o revisor apontou (contagem de substituições conferida, L3).

### Passo 1-D: decisão (`seguranca`)
Pontos a decidir:
- forma da sentinela de processo (atributo em `sys`/módulo em cache × variável de ambiente; lock entre threads do Streamlit);
- `try/finally` com `os.environ.pop("ORACLE_SANDBOX")` quando ela não veio do shell;
- comportamento quando `load_dotenv` levanta exceção (seguir com o que carregou ou abortar a subida);
- desenho do passo 2 e do passo 3. Ver as decisões 2 e 3 do responsável, abaixo.

### Passo 1: carga única por processo + `try/finally` (fecha B4, C1, R-F2-1, C2a)
- `app.py` e `src/main.py`: o bloco de carga roda uma vez por processo (sentinela de processo). O teste "veio do shell?" e a carga ficam dentro de `try/finally`, que remove `ORACLE_SANDBOX` quando ela não veio do shell, inclusive se `load_dotenv` levantar exceção. Na Web, os reruns não recarregam.
- Testes (subprocesso, `.env` fictício):
  - B4 Web: chave nova entre dois reruns não entra no processo;
  - C1 Web e CLI: `ORACLE_SANDBOX=1` + linha com NUL → `ORACLE_SANDBOX` ausente depois do run 1 e do run 2;
  - C2a: no rerun seguinte a uma exceção, a variável não é tratada como "do shell".
- Controle negativo: os três falham na cópia de `d05577e` (os mesmos cenários que reproduziram no passo 0).

### Passo 2: A3, diretório do log resolvido em tempo de chamada
- `src/tools/oracle_dba.py`: o destino do log de aprovação é calculado em tempo de chamada a partir de `AGENTDBA_LOG_DIR`, em vez de fixado no import. Fica preservado o gancho que os testes usam para redirecionar o log, conforme a decisão do `seguranca`.
- Teste: `src.tools` importado antes da entrada (cenário A3a) → as duas cópias resolvem o mesmo diretório. Falha na cópia de `d05577e`.
- **Efeito em testes:** `test_item1_intencao.py:1001-1003, 1046` e `test_oracle_kill.py:657` leem as constantes do módulo. Mudança de expectativa só se a decisão a exigir, declarada com justificativa.
- **Limite:** o passo não corrige `GEMINI_API_KEY` divergente entre cópias (A3a). Fica como item próprio, junto com a duplicação `tools.*` × `src.tools.*`.

### Passo 3: B3 e C3, avisos visíveis
- **B3:** depois do `basicConfig`, WARNING com os **nomes** (nunca valores) das chaves do `.env` sombreadas pelo ambiente, ou seja, presentes no processo antes da carga com valor diferente do arquivo.
- **C3:** quando `ORACLE_SANDBOX` for descartada, além do log, um aviso fixo em `stderr` (CLI) e um `st.warning` (Web). Na Web, o aviso aparece em todo rerun enquanto a condição valer no processo.
- Testes (subprocesso):
  - B3: shell `ORACLE_DSN=dsn_shell` e fictício `ORACLE_DSN=dsn_arquivo` → WARNING com `ORACLE_DSN` e sem `dsn_`;
  - C3 CLI: aviso em `stderr`;
  - C3 Web: `at.warning` com o texto fixo;
  - C3 com logger raiz pré-configurado em ERROR: o aviso em `stderr` continua.
- Controle negativo: falham na cópia de `d05577e`.

### Passo 4: D6 e D3 (`mecanico`, só testes)
- **D6.1** `test_conftest_sandbox_env.py`:
  - caso com valor vazio (`ORACLE_DSN=`);
  - teste em subprocesso da ligação real do conftest. O `.env` fictício só tem chaves da lista e nomes-sentinela, e o operador usa `"0"`/ausente: a carga não acontece.

  Mutações: remover `and v`; trocar a ligação por `load_dotenv(override=True)`.
- **D6.2** `test_env_em_execucao.py`:
  - falhar se `dotenv.load_dotenv` ou `dotenv.dotenv_values` forem chamados durante o fluxo;
  - exercitar `analisar_log_complexo`, com o Gemini neutralizado.

  Mutações: `load_dotenv` com caminho explícito em `notificador.py`; `load_dotenv(override=True)` em `gemini_router.py`.
- **D6.3** `test_carga_env_entrada.py`:
  - o valor lido no import (`tools.gemini_router.GEMINI_API_KEY` fictício) prova a carga antes dos imports;
  - o WARNING sai depois do `basicConfig` (ordem registrada).

  Mutações: carga depois dos imports; WARNING antes do `basicConfig`.
- **D6.4** `test_guard_sessao_sandbox.py`: testar `guard_oracle_sandbox` (`pytest.exit` quando o operador e o início divergem) com "0"/ausente. Mutações: corpo apagado; `ORACLE_SANDBOX_DO_OPERADOR = None` fixo.
- **D6.5** `test_isolamento_env.py`: acrescentar `src.config.settings`, `test_privilegio_read` e `test_privilegio_write_sandbox` à lista importada. É uma alteração do teste para ampliar a cobertura, sem afrouxar asserção; fica declarada no log. Mutação: `load_dotenv()` de volta em `settings.py`.
- **D3:** `test_ausencia_oracle_user_diag_sem_conexao`, `test_ausencia_oracle_user_kill_sem_conexao` e `test_t19_oracle_user_read_ausente_com_select` passam a definir `ORACLE_PASSWORD_*`/`ORACLE_DSN` fictícios com `setenv`, deixando ausente só o `ORACLE_USER_*`. Mutação: retirar `user` da checagem (`oracle_dba.py` na `matar_sessao_oracle` e equivalentes) → os testes falham.

## 5. Decisões do responsável

| # | Decisão | Status |
|---|---|---|
| 1 | Aprovar este plano | **aprovado** (2026-11-18 13:37) |
| 2 | **A3:** executar o passo 2. Cada expectativa alterada é listada com justificativa; nenhuma asserção é enfraquecida. A divergência de `GEMINI_API_KEY` entre cópias vira item próprio no GOVERNANCA_LOG | **aprovado** (2026-11-18 13:37) |
| 3 | **B3:** aceito bloquear `dotenv_values` nas fixtures de `test_fluxo_cli` e `test_fluxo_web`; o bloqueio **falha o teste** se chamado com o `.env` real. Em produção, os valores de `dotenv_values` ficam só em memória; log, tela e e-mail recebem apenas nomes | **aprovado** (2026-11-18 13:37) |
| 4 | R-F2-1 elevado a média e fechado pelo passo 1; C2b como item futuro; C4 decidido como "descartar + aviso visível" | dado pelo responsável em 2026-11-18 |

## 6. Verificação (`verificador`, antes de cada commit)
- `docs/PROCESSO.md` §5, passos 0 a 3. Esperado: 0 failed, **16 skipped**, passed = 199 + testes novos.
- §5.4 em cópia: o teste de isolamento passa no HEAD e falha em `673ceb1`.
- Controles negativos do §4: saídas brutas em `docs/entregas/isolamento_env/fase3_controles.md`.
- Greps extras:
  - `load_dotenv(` só em `app.py` e `src/main.py`, dentro do bloco de sentinela;
  - nenhum `ORACLE_SANDBOX` gravado com `"1"` em `tests/`;
  - nenhuma chamada ao logger com valor de chave sombreada.

## 7. GOVERNANCA_LOG (linhas previstas)
- Uma por commit: passos 1 a 4, com autoria por arquivo, controle negativo e pytest.
- R-F2-1: severidade elevada a média, **fechado** pelo passo 1.
- C2b: item futuro, opt-in explícito por invocação no pytest (flag `--sandbox`).
- C4: decidido "descartar + aviso visível" (passo 3).
- A3: conforme a decisão 2.

## 8. Fora de escopo
- Duplicação `tools.*` × `src.tools.*`, e `GEMINI_API_KEY` divergente entre cópias.
- `GenerativeModel` criado no import.
- C2b (opt-in por invocação).
- R-F2-2 (`python.envFile`), que depende do responsável e envolve `.vscode/settings.json`, fora desta tarefa.
