# Processo de tarefa e delegação (PERSONAL_AGENT)

Complementa o `CLAUDE.md`: lá ficam as regras; aqui, como cumpri-las. A sessão principal lê este documento antes de planejar ou delegar. Os agentes leem o §2 e o §7, e o `verificador` também o §5.

Revisado em 2026-11-18 (tarefa `processo-subagentes`). Mudança neste arquivo segue o processo normal: plano, commit e linha no `docs/GOVERNANCA_LOG.md`.

## 1. Ciclo da tarefa

| Etapa | Quem | Saída |
|---|---|---|
| 0. Abertura | sessão principal | `git status`; origem de todo diff não commitado; modelo da sessão conferido se a tarefa tocar o §2 |
| 1. Plano | sessão principal, em `/plan` | `docs/plans/<tarefa>.md` no modelo do §4; execução só depois da aprovação |
| 2. Decisão | `seguranca` | `docs/entregas/<tarefa>/decisao*.md`, quando a tarefa toca o §2 |
| 3. Execução | sessão principal (Opus) no §2; `mecanico` no resto | só os arquivos do plano; agentes em paralelo só com arquivos disjuntos |
| 4. Revisão | sessão principal | diff inteiro do subagente lido; classificação das mudanças em testes conferida |
| 5. Verificação | `verificador` | sequência do §5; saída em `docs/entregas/<tarefa>/` |
| 6. Commit | sessão principal | um por correção; `git diff` mostrado; caminhos explícitos; coautoria de todo modelo que escreveu |
| 7. Registro | sessão principal | linha no `docs/GOVERNANCA_LOG.md` (§6); lições novas no §7 |
| 8. Aceite | responsável | aceite ou recusa; `git push` só com autorização explícita |

Origem de diff não commitado (etapa 0): reflog, stash e as transcrições em `~/.claude/projects/<projeto>/*.jsonl` (chamadas Edit, Write e Bash, e o campo `model`). Sem origem confirmada, não construa sobre o diff e registre "origem desconhecida".

Tarefa só de leitura (revisão, diagnóstico, levantamento) pula as etapas 1, 6 e 7: saída curta no chat, longa em `docs/entregas/<tarefa>/` (não rastreada). Qualquer outra gravação no repositório volta ao `/plan`.

## 2. Mapa de código de segurança

Produção nestas áreas só é escrita por Opus (sessão principal), que confere o próprio modelo antes de começar. O `mecanico` só a edita com a autorização literal do responsável citada no pedido. Testes dessas áreas podem ser do `mecanico`, com revisão da sessão principal.

| Área | Onde |
|---|---|
| Kill e auditoria | `src/tools/oracle_dba.py`: validação (`validar_parametros_kill`), consulta DIAG (`consultar_alvo_sessao_diag`), conta KILL (`matar_sessao_oracle`), identidade e hash (`CAMPOS_IDENTIDADE_ALVO`, `calcular_hash_identidade`, `executar_kill_verificado`), TTL (`APROVACAO_TTL_SEGUNDOS`, `_aprovacao_expirada`), log de aprovação (lock, fsync, `registrar_log_aprovacao_kill`, `reconciliar_intencoes_orfas`), decisão (`registrar_decisao_kill`, `preparar_intervencao_kill`, `conduzir_kill_hitl`) e `USUARIOS_PROTEGIDOS` |
| Pacote no banco | `db/ops_kill.sql` (`PKG_OPS_KILL`, `c_protegidos`, grants): só em tarefa própria, com commit "PENDENTE APROVAÇÃO" |
| Pontos de entrada | topo de `app.py` e de `src/main.py` (carga única do `.env`, descarte de `ORACLE_SANDBOX`); painel e decisão HITL nas duas interfaces (`processar_decisao_hitl` na Web) |
| Guard dos testes | `tests/conftest.py`: `ORACLE_SANDBOX_DO_OPERADOR`, `CHAVES_ENV_SANDBOX`, `guard_oracle_sandbox`, `pytest_sessionfinish`, `isolar_log_aprovacao` |
| Execução de scripts | `src/tools/executor.py` (tokenização, tipo real do SQL, hash, conta READ ou MUT), `src/tools/registry.py`, `registry/*.yaml`, `tools/verificar_registro.py` |
| Contas e chaves | `.env.example` (só nomes, nunca valores) |

## 3. Delegação

| Agente | Modelo e effort | Usar para | Não usar para | Grava em |
|---|---|---|---|---|
| `mecanico` | sonnet, high | passo já decidido: testes sem conexão, refatoração, documentação | decidir; produção do §2 sem autorização literal | só os arquivos do pedido; não commita |
| `seguranca` | opus, xhigh | decidir ou conferir algo do §2; revisar diff dessas áreas | implementar | `docs/entregas/<tarefa>/decisao*.md` e `conferencia*.md` |
| `verificador` | haiku, padrão | antes de cada commit ou aceite | corrigir qualquer coisa | `docs/entregas/<tarefa>/`, não rastreado |

As regras fixas (`.env`, `ORACLE_SANDBOX`, sem Oracle, sem commit, formato de retorno) já estão nas definições dos agentes e no `CLAUDE.md`, que eles recebem automaticamente. O pedido traz só o que é da tarefa:

```text
Tarefa: <id>, passo <n> de docs/plans/<tarefa>.md (ler §<x>).
Base: branch <b>, HEAD <hash>. Baseline: <P> passed, <S> skipped.
Arquivos permitidos: <lista>. Todo o resto fica fora.
Objetivo e critério de aceite: <1 a 3 linhas>.
Autorização especial: <texto literal do responsável | nenhuma>.
Saída: <docs/entregas/<tarefa>/<arquivo> | só o retorno>.
```

- **Paralelismo:** só com conjuntos de arquivos disjuntos; nunca dois agentes em `oracle_dba.py`, `main.py` ou `app.py`.
- **Conferência do retorno:** o ID do modelo veio; as contagens batem com o baseline; o diff inteiro foi lido; a classificação das mudanças em testes confere com o diff. O que o subagente afirma é afirmação a conferir; o modelo que ele informa se confirma na transcrição.
- **Retorno com PARE:** resolver com o responsável. Não redelegar a mesma coisa sem mudar o pedido.
- **Definições novas:** depois de mudar `.claude/agents/`, confirmar no próximo chat, com `/agents`, que modelo, effort, cor e ferramentas valem.

## 4. Modelo de plano (`docs/plans/<tarefa>.md`)

1. **Contexto:** pedido do responsável, problema e achados da investigação (só leitura).
2. **Base:** branch, HEAD e baseline (passed e skipped).
3. **Arquivos:** por passo, com agente e modelo; disjuntos quando em paralelo.
4. **Passos:** o que muda, o teste que prova e o controle negativo (o teste novo deve falhar no código atual).
5. **Decisões do responsável:** pendentes e aprovadas, com data.
6. **Verificação:** comandos exatos, greps e contagem esperada. O `verificador` usa esta seção.
7. **GOVERNANCA_LOG:** linha prevista.
8. **Fora de escopo:** o que fica para item próprio.

## 5. Verificação padrão

Ordem: perfil, estado do git, pytest, greps. FALHA no passo 0 ou no 2: parar e informar, sem rodar de novo.

**0. Perfil do Windows, só nomes** (PowerShell). Esperado: nenhuma linha. Com `override=False`, variável do perfil vence o `.env`.

```powershell
@((Get-Item 'HKCU:\Environment').Property) + @((Get-Item 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment').Property) | Where-Object { $_ -match '^(ORACLE_|EMAIL_|GEMINI_|AGENTDBA_|SCRIPTS_)' }
```

**1. Estado do git.** Esperado: só os arquivos previstos no plano. A raiz do git é `Workspace/`; o `-- .` limita ao projeto.

```bash
git status --short -- .
```

**2. pytest sem conexão** (Git Bash). Esperado: 0 failed; skipped igual ao baseline; todo skip com o motivo "requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)". Skipped menor indica possível execução em sandbox. Erro ao importar o `oracledb` (DLL bloqueada pelo Controle de Aplicativo) significa "não verificado".

```bash
env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider
```

Em PowerShell: `Remove-Item Env:ORACLE_SANDBOX -ErrorAction SilentlyContinue; $env:PYTHONDONTWRITEBYTECODE = '1'; python -m pytest -q -rs -p no:cacheprovider`.

**3. Greps de regressão.** O `git grep` só varre arquivos versionados, então o `.env` fica de fora. Conferidos em `11767be`.

```bash
# Esperado: nenhuma linha, salvo indicação no comentário.
git grep -n -E 'ORACLE_USER\b' -- 'src/*.py' app.py 'tools/*.py'                 # ORACLE_USER legado
git grep -n -i -E 'alter[[:space:]]+(system|session)' -- '*.py'                  # SQL de sessão no Python
git grep -n 'override=True' -- 'src/*.py' app.py 'tools/*.py'                    # recarga do .env
git grep -n -E 'load_dotenv\(' -- 'src/*.py' app.py                              # 2 linhas: app.py e src/main.py, override=False
git grep -n -E "setenv\(['\"]ORACLE_SANDBOX['\"], *['\"]1|environ\[['\"]ORACLE_SANDBOX['\"]\] *= *['\"]1" -- 'tests/*.py'   # teste que liga o sandbox
git grep -n -i -E '(print|logger\.\w+)\(.*(passw|senha|pwd|secret|token|api_key)' -- '*.py'                                  # credencial em print ou log
git diff --stat <base> -- registry/ db/                                          # vazio, salvo plano com "PENDENTE APROVAÇÃO"
git ls-files | grep -E '(^|/)\.env$'                                             # .env versionado
```

**4. Isolamento do `.env`** (tarefas que mexem em carga de ambiente). Rodar em cópia sem o `.env` real, com `.env` fictício só de nomes-sentinela, nunca com `ORACLE_SANDBOX`. O controle negativo é a mesma cópia no commit anterior, que deve falhar.

```bash
R="$(git rev-parse --show-toplevel)"     # raiz do git (Workspace/)
git -C "$R" archive --format=tar -o "<tmp>/copia.tar" <commit> IA/PERSONAL_AGENT
mkdir -p "<tmp>/copia" && tar --force-local -xf "<tmp>/copia.tar" -C "<tmp>/copia"
```

Sem `--force-local`, o `tar` do Git Bash lê `C:` como host remoto. A forma `<commit>:IA/PERSONAL_AGENT` gerou arquivo vazio no Git Bash (2026-11-18); use o caminho como pathspec, como acima.

## 6. Registro no GOVERNANCA_LOG

Colunas: `Data | Commit | Autor | Arquivo / Item | Tipo de Alteração | Detalhe / Hash Anterior -> Hash Novo | Status`. Commit ainda sem hash: `ver commit "<mensagem>"`.

O "Detalhe" responde, nesta ordem:
1. O que mudou, com `arquivo:linha` reconferido.
2. Origem de diff que já estava no working tree, se houve.
3. Mudanças em testes: expectativas alteradas (com justificativa), só chamada, asserções acrescentadas e "nenhuma asserção removida ou enfraquecida" (ou a lista, com justificativa).
4. Controle negativo ou de mutação e o resultado.
5. `pytest -q`: passed e skipped, com o baseline.
6. Autoria por arquivo com o ID do modelo; quem revisou e quem commitou.
7. O que não foi feito ou verificado (sandbox, Oracle, pytest bloqueado).

Status usuais: aplicado; aguardando revisão; PENDENTE APROVAÇÃO; NÃO ACEITO; aceito.

## 7. Lições aprendidas

Curadas pela sessão principal ao fechar cada tarefa; entram no commit e não são escritas pelos agentes. Formato: o que houve → como evitar → como detectar.

- **L1. Sandbox indevido (2026-11-18 01:27; `264000f`, revertido em `20bdc82`).** Um teste de carga de `.env` fez `monkeypatch.delenv(raising=False)` sobre `ORACLE_SANDBOX` ausente, o que não registra restauração; um `delenv` posterior, com a variável já presente, registrou "1", e o teardown deixou `ORACLE_SANDBOX=1` no processo. 8 testes `sandbox_only` rodaram contra o MODELO, com 1 kill real de sessão descartável. → Teste nunca define `ORACLE_SANDBOX=1` no processo; variável de teste com outro nome. → Skipped abaixo do baseline (16 → 8).
- **L2. Diff sem origem (2026-11-17; `aa9a0a5`).** Um diff de segurança deixado sem commit por uma sessão principal em Sonnet (`patch_v2.py`) foi commitado por outra sessão como "sem registro de autoria"; ficou NÃO ACEITO e foi revertido. → Origem de todo diff pré-existente antes de construir sobre ele; modelo por arquivo no commit e no log; a sessão principal confere o próprio modelo antes do §2. → `git status` na abertura; campo `model` nas transcrições.
- **L3. Mutação sem efeito (2026-11-18; `350aee4`).** A primeira mutação de controle não aplicou a troca por causa de CRLF; foi descartada e refeita. → Conferir a contagem de substituições e o fim de linha da cópia. → Diff vazio entre original e mutante.
- **L4. pytest bloqueado (2026-11-18; B refeito).** A DLL do `oracledb` foi bloqueada pelo Controle de Aplicativo do Windows e o pytest não rodou. → Registrar "não verificado por pytest"; nunca declarar sucesso. → Erro de import do `oracledb` na coleta.
- **L5. `.env` pelo VS Code (2026-11-18; residual R-F2-2).** A extensão Python do VS Code carrega `python.envFile` (padrão `${workspaceFolder}/.env`) em testes e debug; `ORACLE_SANDBOX` do arquivo chegaria ao pytest como se viesse do shell. → pytest só pelo terminal, com `env -u ORACLE_SANDBOX`. → Skipped abaixo do baseline.
- **L6. Perfil do Windows vence o `.env` (2026-11-18).** Com `override=False`, variável do perfil prevalece sobre o arquivo. → §5, passo 0, depois de mudar o perfil e antes de testes, CLI e Web. → Nome com prefixo proibido no perfil.
- **L7. Fato de banco (2026-11-17; item 6, leituras 0.2b, 0.4 e 7.3).** Conclusões foram corrigidas várias vezes: concessão direta × herdada por papel; origem de cursores atribuída sem confirmação. → Fato de banco só com leitura fornecida pelo responsável e com a consulta exata registrada; separar "verificado" de "esperado pela documentação". → Conclusão sem a consulta que a sustenta.
- **L8. Rerun do Streamlit (2026-11-18; errata R1).** O registro afirmou "sem DIAG/KILL" no clique de aprovar, mas o rerun refaz 3 sondas e 2 conexões DIAG antes da decisão. → Antes de afirmar "não conecta", rastrear o rerun inteiro do `app.py` (uma thread por aba, `os.environ` compartilhado). → Contar conexões no teste Web sem trocar as coletas por no-op.
- **L9. Linhas envelhecem (recorrente).** `arquivo:linha` citado em plano e log muda a cada commit. → Reconferir antes de citar ou decidir. → Trecho citado que não bate com a linha.
- **L10. Raiz do git (estrutura).** A raiz é `Workspace/`: os diffs mostram `IA/PERSONAL_AGENT/...` e outros projetos aparecem como não rastreados. → `git add` com caminhos explícitos, nunca `-A` ou `.`. → `git diff --cached --stat` antes do commit.
- **L11. Frontmatter frágil (2026-11-18; `124e12c`).** As descrições de `mecanico` e `seguranca` tinham ": " sem aspas, YAML inválido num parser estrito; o Claude Code tolerava, mas YAML que não faz parse descarta o agente sem aviso. → Descrições entre aspas; validar com PyYAML. → Agente ausente em `/agents`.

## 8. Abertura de chat (para o responsável)

Quatro linhas bastam para a sessão principal decidir se vai ao `/plan`, montar os pedidos do §3 sem perguntar o óbvio e parar no limite:

```text
Tarefa <id>: <objetivo em uma linha>. Tipo: leitura | alteração.
Base: branch <b> (HEAD <hash>, se importar).
Restrições e autorização: <texto literal | nenhuma>.
Limite de tempo: <minutos>. Entregável: <chat | docs/entregas/... | commit>.
```
