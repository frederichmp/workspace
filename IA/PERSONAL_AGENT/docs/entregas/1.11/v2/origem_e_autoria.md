# 1.11-V2 — Origem do diff e autoria por sessão/modelo (commit `aa9a0a5`)

Status de `aa9a0a5`: **NÃO ACEITO** (bloqueio do responsável, 2026-11-17) até a revisão deste material.
Levantamento feito só com leitura de `git` e das transcrições locais do Claude Code em `~/.claude/projects/`. Nada foi executado no Oracle. A parte 2 não foi executada e `db/` não foi alterado.

## 1. Origem do diff de `src/tools/oracle_dba.py` encontrado no working tree

**Origem: identificada.** O diff não veio de commit, stash nem branch:
- `git stash list` vazio;
- o reflog não tem nenhum commit entre `67c01e8` (20:08:55) e `aa9a0a5` (22:57:24);
- o único commit órfão (`2c3531b`, 2026-11-16, `fix(executor): D1-D5`) não toca `oracle_dba.py`.

| Campo | Valor |
|---|---|
| Sessão Claude Code | `2b99e3cb-6c9e-4b40-822d-48115de7a30a` (transcrição local `2b99e3cb-….jsonl`) |
| Modelo que escreveu | `claude-sonnet-5-5`, **na thread principal** da sessão, não num subagente |
| Como escreveu | o script `scratchpad/patch_v2.py` (208 linhas, sha256 `1ca12f636afed6b91cafbd1cb2f042ae599a4beae08c26e8b0d7072e0b27cbaa`), rodado com `python -I` às **2026-11-17 20:15:16 -0300** (23:15:16Z). Ele só faz substituições de texto em `src/tools/oracle_dba.py` |
| Resultado registrado na sessão | `1 file changed, 120 insertions(+), 14 deletions(-)`, igual ao stat encontrado no início da 1.11-V2 |
| Depois disso | a sessão lançou um agente de testes e um de revisão, e **os dois falharam** (23:15:39Z). O modelo foi trocado para Opus via `/model` às 23:15:21Z. Nada foi commitado nem registrado no GOVERNANCA_LOG |
| Autor git | nenhum; o diff nunca foi commitado por essa sessão |

**Prova de identidade (reprodução).**
- `patch_v2.py` foi aplicado a uma cópia isolada de `ed75f0f:src/tools/oracle_dba.py`, no scratchpad desta sessão.
- A saída é **idêntica** a `aa9a0a5:src/tools/oracle_dba.py` com a minha única edição revertida.
- A diferença entre o script e `aa9a0a5` é **uma linha** (1286): `dados_exec["id_intervencao"] = id_intervencao`, que foi trocada por um comentário (ajuste "a" do `seguranca`).

**Desvio de processo registrado.** O código de segurança (assinatura do kill, validação de identidade e `CAMPOS_IDENTIDADE_ALVO`, que é o hash) foi escrito por **Sonnet**. O CLAUDE.md reserva Sonnet ao trabalho mecânico, e o agente `mecanico` é proibido de alterar hash e autorização. Mitigação até aqui: revisão pela sessão principal (Opus) e pelo `seguranca` (Opus). **Não substitui a revisão do responsável.**

## 2. Quem escreveu o quê no commit `aa9a0a5`

Sessão principal da 1.11-V2: `3e81acfa-6e6c-4aa7-a03d-9c71741a4892`. Modelos conferidos nas transcrições.

| Arquivo | Autor (sessão / papel / modelo) | O quê |
|---|---|---|
| `src/tools/oracle_dba.py` | `2b99e3cb`, thread principal, **claude-sonnet-5-5** | Todo o diff v2, exceto a linha 1286 |
| `src/tools/oracle_dba.py` | `3e81acfa`, principal, **claude-opus-5-5** | Linha 1286: `id_intervencao` retirado do `resultado_tool` |
| `src/main.py` | `3e81acfa`, principal, claude-opus-5-5 | Linha `Logon (hora BD)` no prompt HITL |
| `app.py` | `3e81acfa`, principal, claude-opus-5-5 | Linha `Logon` no painel; `logon_time` no texto do hash |
| `tests/fakes_oracle.py` | `3e81acfa`, subagente `mecanico`, **claude-sonnet-5-5** | `LOGON_TIME`, `erro_kill`, `vars_criadas`, `assert_kill_binds`, `BINDS_KILL_V2` (escritos por scripts Python via Bash) |
| `tests/test_oracle_kill.py` | `3e81acfa`, subagente `mecanico`, claude-sonnet-5-5 | Testes novos, chamadas com `**KW_V2`, sandbox v2 |
| `tests/test_oracle_kill.py` | `3e81acfa`, principal, claude-opus-5-5 | Remoção do sandbox NLS (`ALTER SESSION`) e do parâmetro `antes` do helper |
| `docs/GOVERNANCA_LOG.md`, `docs/plans/1.11.md` | `3e81acfa`, principal, claude-opus-5-5 | Registro da 1.11-V2 |
| `docs/entregas/1.11/v2/verificacao.md` | `3e81acfa`, subagente `verificador`, **claude-haiku-5-5** | Saída do aceite |
| — | `3e81acfa`, subagente `seguranca`, claude-opus-5-5 | Decisões D1–D4; **nenhuma edição** |

Commit `aa9a0a5`: feito pela sessão principal `3e81acfa` (claude-opus-5-5), com o autor git `frederichmp` e a linha `Co-Authored-By: Claude Opus 5.5`. **Correção:** a coautoria do commit não menciona o Sonnet, que escreveu a maior parte do `oracle_dba.py`. Fica registrado aqui.

## 3. Os outros commits de `oracle_dba.py` no intervalo `e2c0696..aa9a0a5`

`e2c0696` (2026-11-17 15:52, `COMMIT antes do commit 1a`) é ancestral de HEAD e só altera `CLAUDE.md`. O intervalo traz **4** commits em `oracle_dba.py`, não só o `aa9a0a5`. A atribuição foi confirmada por conteúdo: o `new_string` de cada `Edit` da transcrição está no commit e não está no pai dele.

| Commit | Data | Assunto | Sessão / modelo que editou |
|---|---|---|---|
| `4ff32ce` | 16:25:02 | fix(kill): isola log de aprovacao nos testes (C7) | `474bbbe3`, subagente, **claude-sonnet-5-5** (2 edições) |
| `4e23212` | 16:28:45 | fix(kill): inst_id sem default em matar_sessao_oracle | `474bbbe3`, subagente, **claude-sonnet-5-5** (1 edição) |
| `ed75f0f` | 16:34:24 | feat(kill): expiracao de aprovacao (TIMEOUT) | `474bbbe3`, principal, **claude-opus-5-5** (6 edições) |
| `aa9a0a5` | 22:57:24 | feat(kill): Python v2 do item 6 (PENDENTE APROVAÇÃO) | seções 1 e 2 acima |

## 4. Diff completo para revisão

- `diff_oracle_dba_e2c0696_aa9a0a5.diff`: `git diff e2c0696 aa9a0a5 -- src/tools/oracle_dba.py`, com 183 inserções e 20 remoções (429 linhas). sha256 `6c91be0ad12ae566c98d862307619cf9785290f9b09fd0e3aff1601c41b2023a`.
- `diff_oracle_dba_por_commit.diff`: o mesmo intervalo separado pelos 4 commits (`git log -p --reverse`). sha256 `c4905c842ce211eecc254c4b4f1976d4cf968dc3ac8c82a78202a1b7deba4f8c`.
