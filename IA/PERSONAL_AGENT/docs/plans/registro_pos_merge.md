# Plano — registro pós-merge (protocolo, refs, .gitignore, testes T1/T2, aceite da fase 4)

Destino no repositório: `docs/plans/registro_pos_merge.md` (cópia literal deste arquivo; entra no commit do **P1**, por decisão do responsável em 2026-11-18).
Estado (revisão 4, 2026-11-18): **executados** P0 `a3362f2` (+ tag `ref/docs-protocolo-27d135d`), P1 `8cc3773`, P3 `fa9e390`, T1 `e692788`, T2 `66a15d7`, suíte (272 passed, 16 skipped, 0 failed em `66a15d7`) e S1 `3ca8f98`. **P2 autorizado** pelo responsável depois da comprovação do momento da suíte 269/16 (F13) e da correção do desvio e da L21; sem push. Fora de commit: pendente.

## 1. Contexto

Pedido do responsável (2026-11-18): depois do merge fast-forward `19f19f2 → 8810b6e` em `main`, trazer o protocolo de subagentes (`27d135d`, branch `docs/protocolo`), registrar desvios e o aceite da fase 4, ignorar `*.sqlbkp`, cobrir com testes dois pontos da carga do `.env` levantados na investigação (F11) e, fora de commit, limpar stash e branches. Um commit por passo.

Fatos levantados (só leitura):

- **F1. `27d135d`** (2026-11-18 00:54, `docs: protocolo curto de instrucao e resposta de subagentes`): só na branch `docs/protocolo` (1 commit fora de `main`, base `19f19f2`). Toca `docs/PROTOCOLO.md` (novo, 22 linhas), `CLAUDE.md` (+1 linha: "Mensagens a subagentes e respostas seguem docs/PROTOCOLO.md.") e `docs/GOVERNANCA_LOG.md` (+1 linha).
- **F2. Conflitos** do cherry-pick: `docs/GOVERNANCA_LOG.md` e `CLAUDE.md` (confirmados na execução do P0).
- **F3. PROTOCOLO × PROCESSO §3.** O `PROTOCOLO.md` usa `T:/A:/R:/S:`, resposta em uma linha `OK|…`/`ERRO|…` e "Subagente novo por tarefa. Não reutilizar com SendMessage para outra tarefa." O `PROCESSO.md` §3, em vigor em `main`, usa o bloco em prosa. Na fase 4 a sessão seguiu o §3 e reutilizou subagentes com SendMessage (`verificador`: passo 0, baseline e verificações dos passos 1 a 4; `mecanico`: passos 1 e 4).
- **F4. Ordem cronológica** (data de autor): `c22a928` item 1 (00:35) → **`27d135d` (00:54)** → `ec647cf` retira O1 (00:58).
- **F5. `refs/codex/*`**: 3 refs `refs/codex/turn-diffs/checkpoints/…` para objetos tree (`4124d96`, `aac0d00`, `154f07d`); ferramenta externa. Não alteradas.
- **F6. `refs/heads/´`**: `54f813c "Primeiro commit"`, contida em `main`.
- **F7. `stash@{0}`** = `8fd6678` (item 1 v1 sobre `aa9a0a5`, NÃO ACEITO; referência), 3 pais.
- **F8. Branches**: `revert/aa9a0a5`, `isolamento-env`, `item1/reaplicado`, `´` contidas em `main` (`-d`); `docs/protocolo` exige `-D` (D3).
- **F9. `*.sqlbkp`**: só `db/ops_kill.sqlbkp` (não rastreado); nenhuma regra nos dois `.gitignore`.
- **F10. Itens 1–3 do P2**: não chegaram como texto; o responsável indicou que a investigação F11 "alimenta o P2". **A confirmar:** se F11 substitui os itens 1–3.
- **F11. Investigação só leitura em `8810b6e`** (2026-11-18, claude-opus-5-5):
  1. `.env` ausente ⇒ `_carregar_env` devolve `None` sem escrita (`app.py:74-77`); a `ORACLE_SANDBOX` herdada **não é removida** (`app.py:90`, `:99`; `src/main.py:75`, `:84`), por desenho (`app.py:44`); a subida aborta com "Nova tentativa" (`app.py:104-108`). COMPROVADO por leitura. Sem teste dessa combinação: `test_f4c2_env_ausente_nova_tentativa` (`tests/test_carga_env_entrada.py:605-614`) não passa `sandbox_shell` e só roda CLI; o único teste com valor herdado (`:367-372`, `"0"`) usa `.env` presente.
  2. Blocos `>>> carga-env`/`<<< carga-env` (`app.py:37-114`, `src/main.py:22-99`): idênticos (78 linhas, md5 `3819fb24…`); **nenhum teste** de igualdade. COMPROVADO.
  3. chromadb `Settings` (pydantic-settings) **só lê**: `dotenv_values` (`pydantic_settings/sources/providers/dotenv.py:92`) devolve dicionário (`dotenv/main.py:465-472`); escrita em `os.environ` só em `dotenv/main.py:108` via `load_dotenv` (`:435`). COMPROVADO por código e execução (cwd fictício: `os.environ` inalterado). **7 leituras** de `cwd/.env` no `import chromadb`, todas `Settings()` avaliadas no import: `api/shared_system_client.py:22`, `api/client.py:67`, `api/client.py:669`, `api/async_client.py:65`, `api/async_client.py:526`, `__init__.py:112`, `__init__.py:465`. Versões: chromadb 1.5.9, pydantic-settings 2.16.3, python-dotenv 1.2.4. Momento: 1ª busca RAG (import tardio em `src/tools/rag_search.py:37`), CORRELAÇÃO; import via `langchain_community.vectorstores` (`rag_search.py:14`): HIPÓTESE.
- **F12. `"1"` × `"0"` no bloco `carga-env`:** nenhum ramo distingue o valor. `_sandbox_do_shell` e o descarte testam só presença (`app.py:90`, `:99`; `src/main.py:75`, `:84`); o aviso DESCARTADA depende só de `sandbox_descartada` (`app.py:100`, `:133-134`, `:595-596`; `src/main.py:85`, `:120-123`); as sombreadas comparam com o valor do arquivo, não com `"1"` (`app.py:70`), e não existem com `.env` ausente. Nenhuma outra leitura de `ORACLE_SANDBOX` em `src/`, `app.py` ou `tools/`. O único ponto que compara com `"1"` é o portão de testes `tests/conftest.py:187`, fora do bloco. **Conclusão:** o T2 com `"0"` exercita o mesmo ramo que `"1"` exercitaria. COMPROVADO por leitura (não executado com `"1"`, proibido pelo CLAUDE.md).
- **F13. Momento da suíte 269/16 (2026-11-18, horário -03:00): COMPROVADO antes do FF.** Reflog: commit `8810b6e` às 19:16:42 (`HEAD@{2026-11-18T19:16:42-03:00}`); FF `19f19f2 → 8810b6e` às 20:10:37 (`main@{2026-11-18T20:10:37-03:00}: merge isolamento-env: Fast-forward`). Transcrição da sessão `4a6117d2`: às 19:16:42, `git status --short -- .` sem modificação rastreada; às 19:16:50, `ORACLE_SANDBOX no shell: 0`, `git log -1` = `8810b6e` e pytest com resultado às 19:22:29: **269 passed, 16 skipped** (os 16 skips com o motivo padrão). Antes, o `verificador` obteve 269/16 às 19:14:15 no working tree `ede678a` + testes do passo 4 (`docs/entregas/isolamento_env/fase4/verificacao_passo4.md:11`). Sem Edit nem Write na sessão entre 19:16:42 e o FF; o FF foi comando do responsável às 20:10:29. O FF não cria árvore: a integrada é a testada. Os itens 1–3 aparecem pela primeira vez às 20:48:42 e foram respondidos pela F11 às 21:51–21:54, depois do FF. A execução em `8810b6e` só consta da transcrição (sem arquivo em `docs/entregas/`).

## 2. Base

`main` = `8810b6e`; tag `pre-merge-isolamento` → `19f19f2`. Último pytest antes do merge: 269 passed, 16 skipped em `8810b6e` (19:16:50–19:22:29; FF às 20:10:37), COMPROVADO (F13). Sem push.

## 3. Arquivos por passo (todos pela sessão principal, claude-opus-5-5; sem subagente que escreva)

| Ordem | Passo | Arquivos | Commit |
|---|---|---|---|
| 1 | P0 | `CLAUDE.md`, `docs/GOVERNANCA_LOG.md`, `docs/PROTOCOLO.md` (via cherry-pick) | o do cherry-pick (`-x`) |
| 2 | P1 | `CLAUDE.md` (regra de precedência), `docs/GOVERNANCA_LOG.md`, `docs/plans/registro_pos_merge.md` | `docs:` |
| 3 | P3 | `IA/PERSONAL_AGENT/.gitignore`, `docs/GOVERNANCA_LOG.md` | `chore:` |
| 4 | T1 | `tests/test_carga_env_entrada.py` | `test:` |
| 5 | T2 | `tests/test_carga_env_entrada.py` | `test:` |
| 6 | Suíte | nenhum (saídas em `docs/entregas/registro_pos_merge/`, não rastreado) | — |
| 6b | S1 | `tests/test_carga_env_entrada.py` (2 linhas em branco antes do decorador do T2, PEP 8) | `style:` |
| 7 | P2 | `docs/GOVERNANCA_LOG.md`, `docs/PROCESSO.md` §7 (L21 a L23), `docs/plans/registro_pos_merge.md` (sincronizado por hash) | `docs:` (PARE antes do commit) |

`CLAUDE.md`, `.gitignore` e os testes não são produção do §2; `app.py`, `src/main.py`, `conftest.py` e `db/` não são tocados. Testes da área "Pontos de entrada" escritos pela sessão principal (Opus).

## 4. Passos

**P0 — Cherry-pick do protocolo** (em execução). `git cherry-pick -x 27d135d`.
- `GOVERNANCA_LOG.md`: todas as linhas de `main`; a de `27d135d` entre "item 1, reaplicação" e "retira O1" (F4). Nenhuma alterada.
- `CLAUDE.md`: as duas linhas de `main` + a de `27d135d`, literal, logo depois.
- `--continue` com a mensagem original + `(cherry picked from commit 27d135d…)` + "Conflitos resolvidos (GOVERNANCA_LOG por ordem cronológica; CLAUDE.md literal), claude-opus-5-5".
- Conferir: `git show --stat HEAD` = 3 arquivos; `git diff 27d135d HEAD -- docs/PROTOCOLO.md` vazio; +1 linha em cada um dos outros dois em relação a `8810b6e` (já conferido no índice).
- **D3 (aprovada):** logo após o commit do P0, `git tag ref/docs-protocolo-27d135d 27d135d` (só cria; nada é apagado neste lote).

**P1 — Precedência, desvios e refs.**
- `CLAUDE.md`, logo após a linha do protocolo: "- Em divergência, PROCESSO.md §3 prevalece sobre PROTOCOLO.md até a tarefa de reconciliação." (texto do responsável).
- `GOVERNANCA_LOG.md` (formato do PROCESSO §6), uma linha por item:
  - **Divergência T/A/R/S × PROCESSO §3** (F3): registrada; regra de precedência no `CLAUDE.md`; mapa `27d135d` → hash do P0; tag `ref/docs-protocolo-27d135d`.
  - **Reutilização via SendMessage na fase 4: FATO**, não desvio: o `PROTOCOLO.md` não estava em `main` de `27d135d` (00:54) até o P0; a fase 4 seguiu o §3 em vigor.
  - **Tarefa de reconciliação PROTOCOLO × PROCESSO §3: pendente.**
  - **`refs/codex/*`** (F5) registradas, não alteradas; **`refs/heads/´`** (F6) espúria, remoção fora de commit.
  - Cópia do plano em `docs/plans/registro_pos_merge.md` no P1 (o rascunho v1 dizia P2).
- Conferir: `git show --stat HEAD` = 3 arquivos; `CLAUDE.md` +1 linha.

**P3 — Ignorar `*.sqlbkp`.** `*.sqlbkp` no `IA/PERSONAL_AGENT/.gitignore` (bloco de banco). Linha curta no log (motivo: backup local de `db/ops_kill.sql`). Conferir: `git check-ignore -v db/ops_kill.sqlbkp` → regra nova; `git status --short -- .` sem o arquivo; `git ls-files db/` inalterado.

**T1 — Igualdade dos blocos `carga-env`** (F11.2).
- Teste novo em `tests/test_carga_env_entrada.py`: lê `app.py` e `src/main.py` em bytes; exige exatamente um par de marcadores (linha que começa com `# >>> carga-env` e com `# <<< carga-env`) em cada arquivo, bloco não vazio, e bytes iguais entre os dois (inclui fim de linha). Sem subprocesso, sem `.env`, sem `ORACLE_SANDBOX`.
- Hoje passa (F11.2). **Controle negativo** em cópia (`git archive` do HEAD, PROCESSO §5 passo 4, sem `.env`): (a) trocar 1 caractere dentro do bloco de `src/main.py` e (b) remover o marcador `<<<` de `app.py`; `assert` de 1 substituição e fim de linha medido em bytes (L3, L16); só o T1 na cópia; esperado: FALHA nas duas. Saídas gravadas em arquivo (L20).
- Rodar só o T1 na árvore real antes do commit; `git diff` mostrado.

**T2 — `.env` ausente preserva `ORACLE_SANDBOX` do shell** (F11.1, F12).
- Variante do `test_f4c2`, parametrizada em `cli` e `web`: `_rodar(entrada, tmp_path, "", runs=2, ficticio_tipo="ausente", sandbox_shell="0")` (o `"0"` só no ambiente do subprocesso). Asserções: nas 2 subidas, exceção com `MENSAGEM_FALHA_CARGA`, `FileNotFoundError` e `MENSAGEM_NOVA_TENTATIVA`, e `sandbox == "0"`; final `sandbox == "0"`; nenhum aviso com "DESCARTADA" (`avisos` e `warning_tela`); `stats_por_run[1] >= 1`; `chamadas == []`; `leituras_efetivas_por_run == [0, 0]`; `leituras_reais == []`. O `test_f4c2` existente não muda.
- Risco: o `test_f4c2` original só roda CLI e o motivo não está registrado (HIPÓTESE: limitação do harness Web com `.env` ausente). Se a variante Web falhar por harness: **PARE** e reportar; sem enfraquecer nem retirar a Web sem decisão.
- **Controle negativo** em cópia: trocar `if not _sandbox_do_shell and os.environ.pop(` por `if os.environ.pop(` em `app.py` e `src/main.py` (1 substituição em cada, bytes conferidos); esperado: as **duas** variantes falham (L14); se alguma passar, PARE (L18). Saídas gravadas (L20).

**Suíte (após o T2).** `verificador` (Haiku), PROCESSO §5 passos 0 a 3, sem `ORACLE_SANDBOX`. Esperado: **272 passed (269 + 1 do T1 + 2 do T2), 16 skipped**, todo skip com o motivo padrão; skipped abaixo de 16: parar e avisar, sem rodar de novo. G7: `git diff --stat 8810b6e -- registry/ db/` vazio. Contagem registrada no P2.

**S1 — Estilo do T2** (aprovado em 2026-11-18). Só `tests/test_carga_env_entrada.py`: a linha em branco que faltava antes do decorador do T2. Prova de ausência de `ORACLE_SANDBOX` antes; só o arquivo afetado: 38 passed. Commit `3ca8f98`.

**P2 — Aceite da fase 4 e registro** (aprovado em 2026-11-18; executar até o `git add` e PARAR antes do commit, mostrando o `git diff --cached`). Requisitos do responsável: cópia do plano sincronizada (hash); log com T1/T2/S1, suíte 272/16/0 com a prova de ausência, controles negativos (1 linha cada) e o caminho `docs/entregas/registro_pos_merge/` (não rastreado); risco aberto vinculado ao R-F2-2 com status "cobertura a confirmar pelo responsável"; linha antiga do I3 (`:122`) preservada, a nova a complementa. Conteúdo:
- Linha de **aceite da fase 4** (`216a6fd`, `f5692f0`, `ede678a`, `b293706`, `8810b6e`), sem reescrever linhas existentes.
- Linha de **desvio: merge antes das 3 verificações do aceite condicional e antes do registro do aceite; árvore integrada idêntica à testada (FF)** (texto do responsável, com a evidência da F13). Sequência correta: verificações do aceite → registro do aceite → merge → pytest pós-merge. Tag `pre-merge-isolamento`.
- **Decisões P1/P2 da fase 4**, com data; comportamento de F11.1 (valor do shell preservado com `.env` ausente) como esperado por desenho.
- **T1 e T2:** commits, asserções novas, "nenhuma asserção removida ou enfraquecida", controles negativos e resultados. Executados em 2026-11-18: T1 `e692788` (controle: 1 caractere no bloco de `src/main.py` → FALHA; marcador `<<<` removido de `app.py` → FALHA); T2 `66a15d7` (controle: descarte sem a condição `_sandbox_do_shell` em `app.py` e `src/main.py` → as 2 variantes FALHAM em `tests/test_carga_env_entrada.py:627`). Saídas em `docs/entregas/registro_pos_merge/`. A linha em branco que faltava antes do decorador do T2 foi corrigida no S1.
- **Risco aberto (acréscimo do responsável):** o valor de `ORACLE_SANDBOX` presente no ambiente antes da carga prevalece (`app.py:90`, `:99`; `src/main.py:75`, `:84`; agora coberto pelo T2), e o portão dos testes `tests/conftest.py:187` depende só do ambiente do processo (`os.getenv("ORACLE_SANDBOX") != "1"`). Nada distingue "definida pelo operador no shell" de "injetada no ambiente por outra via antes do processo" (ex.: `python.envFile` do VS Code, residual **R-F2-2**, L5; perfil do Windows, L6). Vinculado ao R-F2-2; **cobertura a confirmar pelo responsável** (hoje: regra de rodar pytest só pelo terminal com `env -u ORACLE_SANDBOX` e o passo 0 do PROCESSO §5).
- **Resultado da suíte** (passed/skipped contra 269/16).
- **I3 detalhado** (linha nova que complementa a de `GOVERNANCA_LOG.md:122`, preservada): 7 pontos de chamada, versões, "só lê" COMPROVADO, momento = 1ª busca RAG (CORRELAÇÃO), import via langchain = HIPÓTESE.
- **L21:** merge antes das verificações do aceite condicional e do registro do aceite (árvore integrada = testada, F13). **L22:** caminho de falha da carga testado sem a variável do operador (T2). **L23:** promessa de igualdade só em comentário (T1).

**Fora de commit (depois do aceite deste plano executado, com autorização explícita):**
1. `git tag ref/item1-v1-nao-aceito stash@{0}` → conferir = `8fd6678`; então `git stash drop stash@{0}`.
2. `git branch -d revert/aa9a0a5 isolamento-env item1/reaplicado` e `git branch -d '´'`.
3. `git branch -D docs/protocolo` (tag D3 já criada no P0).
4. Conferir: só `main` em `refs/heads/`; stash vazio; tags `pre-merge-isolamento`, `ref/item1-v1-nao-aceito`, `ref/docs-protocolo-27d135d`. Sem push.

## 5. Decisões do responsável

Aprovadas (2026-11-18): P2 pendente; `CLAUDE.md` literal + registro; execução de P0, P1 e P3 nesta ordem; cópia do plano no P1; D1 (ordem cronológica no log); D2 (divergência só registrada, precedência do §3 no `CLAUDE.md`, reconciliação pendente); D3 = tag `ref/docs-protocolo-27d135d`; reutilização via SendMessage = FATO; `*.sqlbkp` no `.gitignore` do projeto; T1 e T2 após P3 e antes de P2.

Aprovadas depois (2026-11-18): **D4** = sim (T1 e T2 como descritos); **D5** = sim (F11 substitui os itens 1–3); acréscimo (a): prova de ausência de `ORACLE_SANDBOX` antes do pytest da suíte; acréscimo (b): risco aberto no P2, vinculado ao R-F2-2; S1; P2 até o `git add`, PARE antes do commit. Em seguida: aceite da fase 4 confirmado pelo responsável ("Fase 4 aceita pelo responsável em 2026-11-18."); risco aberto mantido, não bloqueante; desvio e L21 corrigidos conforme F13; commit do P2 autorizado, sem push.

Pendentes: fora de commit (stash e branches); cobertura do risco aberto (R-F2-2), não bloqueante.

## 6. Verificação

- Por passo: `git status --short -- .` (só os arquivos do passo + os não rastreados da abertura), `git diff --cached --stat`, `git show --stat HEAD`, `git diff HEAD~1` mostrado.
- Não rastreados da abertura (previstos, não entram em commit): `db/ops_kill.sqlbkp` (some após o P3), `docs/entregas/1.11/item1/{abc/,diff_producao.diff,diff_revisao_gemini.diff,diff_testes.diff,diff_tests.txt,greps.txt,o1o2/,pytest_run1.txt,pytest_run2.txt,revisao_adversarial_gemini.md,verificacao.md}`, `docs/entregas/isolamento_env/fase4/diff_passo{1,2,4}.diff`, `docs/entregas/processo-subagentes/`, `docs/plans/1.11-item1-B-refeito.md`; novo e previsto: `docs/entregas/registro_pos_merge/`.
- P0: `git grep -n 'PROTOCOLO' -- CLAUDE.md docs/GOVERNANCA_LOG.md` → a linha do CLAUDE.md e a do log.
- T1/T2: controles negativos do §4; suíte conforme o §4.

## 7. GOVERNANCA_LOG

P0 traz a linha original de `27d135d`; P1 e P3 trazem as suas; T1 e T2 são registrados no P2 (com o resultado da suíte), por decisão do responsável.

## 8. Fora de escopo

Reconciliar PROTOCOLO × PROCESSO §3 (tarefa própria); `refs/codex/*`; push; `db/ops_kill.sqlbkp` em si; mudar a produção da carga do `.env`; mitigar as 7 leituras do chromadb (I3 continua residual).
