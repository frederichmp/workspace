# Processo de tarefa e delegação (PERSONAL_AGENT)

Complementa o `CLAUDE.md`: lá ficam as regras; aqui, como cumpri-las. A sessão principal lê este documento antes de planejar ou delegar. Cada agente traz no corpo o que precisa sempre (o mapa do §2 e as lições do §7 que valem para ele) e lê aqui só o item citado no pedido; o `verificador` roda o §5 pelo script.

Revisado em 2026-11-18 (tarefas `processo-subagentes` e `revisao-subagentes-v2`). Mudança neste arquivo segue o processo normal: plano, commit e linha no `docs/GOVERNANCA_LOG.md`.

## 1. Ciclo da tarefa

| Etapa | Quem | Saída |
|---|---|---|
| 0. Abertura | sessão principal | `git status`; origem de todo diff não commitado; modelo da sessão conferido se a tarefa tocar o §2 |
| 1. Plano | sessão principal, em `/plan` | `docs/plans/<tarefa>.md` no modelo do §4; execução só depois da aprovação |
| 2. Decisão | `seguranca` | `docs/entregas/<tarefa>/decisao*.md`, quando a tarefa toca o §2 |
| 3. Execução | sessão principal (Opus) no §2; `mecanico` no resto, salvo passo pequeno (§3) | só os arquivos do plano; agentes em paralelo só com arquivos disjuntos |
| 4. Revisão | sessão principal | diff inteiro do subagente lido; classificação das mudanças em testes conferida |
| 5. Verificação | `verificador` | sequência do §5; saída em `docs/entregas/<tarefa>/` |
| 6. Commit | sessão principal | um por correção; `git diff` mostrado; caminhos explícitos; coautoria de todo modelo que escreveu |
| 7. Registro | sessão principal | linha no `docs/GOVERNANCA_LOG.md` (§6); lições novas no §7 |
| 8. Aceite | responsável | aceite ou recusa; `git push` só com autorização explícita |

Origem de diff não commitado (etapa 0): reflog, stash e as transcrições em `~/.claude/projects/<projeto>/*.jsonl` (chamadas Edit, Write e Bash, e o campo `model`). Sem origem confirmada, não construa sobre o diff e registre "origem desconhecida".

Tarefa só de leitura (revisão, diagnóstico, levantamento) pula as etapas 1, 6 e 7: saída curta no chat, longa em `docs/entregas/<tarefa>/` (não rastreada). Qualquer outra gravação no repositório volta ao `/plan`.

## 2. Mapa de código de segurança

Produção nestas áreas só é escrita por Opus (sessão principal), que confere o próprio modelo antes de começar. O `mecanico` só a edita com a autorização literal do responsável citada no pedido. A exceção é a fiação do guarda (`.claude/**`, `tools/guarda_agentes.py`): nenhum subagente a grava, nem com autorização literal. O guarda bloqueia essa gravação (R5, §3), conforme a decisão do responsável de 2026-11-19 (`docs/plans/guarda-r4-r5.md`). Testes dessas áreas podem ser do `mecanico`, com revisão da sessão principal.

| Área | Onde |
|---|---|
| Kill e auditoria | `src/tools/oracle_dba.py`: validação (`validar_parametros_kill`), consulta DIAG (`consultar_alvo_sessao_diag`), conta KILL (`matar_sessao_oracle`), identidade e hash (`CAMPOS_IDENTIDADE_ALVO`, `calcular_hash_identidade`, `executar_kill_verificado`), TTL (`APROVACAO_TTL_SEGUNDOS`, `_aprovacao_expirada`), log de aprovação (lock, fsync, `registrar_log_aprovacao_kill`, `reconciliar_intencoes_orfas`), decisão (`registrar_decisao_kill`, `preparar_intervencao_kill`, `conduzir_kill_hitl`) e `USUARIOS_PROTEGIDOS` |
| Pacote no banco | `db/ops_kill.sql` (`PKG_OPS_KILL`, `c_protegidos`, grants): só em tarefa própria, com commit "PENDENTE APROVAÇÃO" |
| Pontos de entrada | topo de `app.py` e de `src/main.py` (carga única do `.env`, descarte de `ORACLE_SANDBOX`); painel e decisão HITL nas duas interfaces (`processar_decisao_hitl` na Web) |
| Guard dos testes | `tests/conftest.py`: `ORACLE_SANDBOX_DO_OPERADOR`, `CHAVES_ENV_SANDBOX`, `guard_oracle_sandbox`, `pytest_sessionfinish`, `isolar_log_aprovacao` |
| Execução de scripts | `src/tools/executor.py` (tokenização, tipo real do SQL, hash, conta READ ou MUT), `src/tools/registry.py`, `registry/*.yaml`, `tools/verificar_registro.py` |
| Verificação, controle e guarda | `tools/verificacao_padrao.py` (passos 0 a 3 do §5), `tools/controle_mutacao.py` (controle de mutação) e `tools/guarda_agentes.py` (hook dos subagentes) |
| Contas e chaves | `.env.example` (só nomes, nunca valores) |
| Definição dos agentes e hooks | `.claude/agents/*.md` (modelo, ferramentas, `maxTurns`, hook do guarda) e `.claude/settings*.json`. É a fiação do guarda: nenhum subagente grava aqui (R5) |

Mudou o mapa? Atualize também a lista do `.claude/agents/mecanico.md`, o que só Opus faz, porque o arquivo é da fiação.

## 3. Delegação

| Agente | Modelo e effort | Usar para | Não usar para | Grava em |
|---|---|---|---|---|
| `mecanico` | sonnet, high; medium em passo só de documentação | passo já decidido: testes sem conexão, refatoração, documentação | decidir; produção do §2 sem autorização literal; passo pequeno | só os arquivos do pedido; não commita |
| `seguranca` | opus, xhigh em decisão nova; high em conferência de diff | decidir ou conferir algo do §2; revisar diff dessas áreas | implementar; leitura geral | `docs/entregas/<tarefa>/decisao*.md` e `conferencia*.md` |
| `verificador` | haiku, padrão | antes de commit ou aceite, com `tools/verificacao_padrao.py` | corrigir qualquer coisa | `docs/entregas/<tarefa>/`, não rastreado |

Effort diferente do padrão vai no parâmetro `effort` da chamada, por esta instrução.

As regras fixas (`.env`, `ORACLE_SANDBOX`, sem Oracle, sem commit, formato de retorno) já estão nas definições dos agentes e no `CLAUDE.md`, que eles recebem automaticamente. O pedido traz só o que é da tarefa:

```text
Tarefa: <id>, passo <n> de docs/plans/<tarefa>.md (ler §<x>).
Base: branch <b>, HEAD <hash>. Baseline: <P> passed, <S> skipped.
Arquivos permitidos: <lista>. Todo o resto fica fora.
Objetivo e critério de aceite: <1 a 3 linhas>.
Autorização especial: <texto literal do responsável | nenhuma>.
Saída: <docs/entregas/<tarefa>/<arquivo> | só o retorno>.
```

O pedido tem no máximo 1.000 caracteres: o que não couber vai no plano, citado por seção, e regra que já está no corpo do agente não se repete.

- **Passo pequeno** (até 3 edições em 1 ou 2 arquivos, sem rodar a suíte): a sessão principal faz direto, porque uma chamada de agente custa de 34 a 35 mil tokens só no 1º turno. O §2 continua só com Opus.
- **Tamanho da chamada:** uma por passo do plano e uma por controle ou mutação. O agente tem teto de chamadas de ferramenta (cerca de 30 no `mecanico`, 40 no `seguranca` e 15 no `verificador`) e, ao chegar nele, devolve o parcial; o que falta vira chamada nova.
- **Retorno** (incorporado do antigo `docs/PROTOCOLO.md`): a 1ª linha traz o status, e o detalhe fica em `docs/entregas/<tarefa>/`, nunca no retorno.

  | Agente | Status da 1ª linha | Teto |
  |---|---|---|
  | `mecanico` | `OK`, `PARE`, `ERRO`, `PARCIAL` | 1.200 caracteres |
  | `seguranca` | `CONFORME`, `NÃO CONFORME`, `PENDENTE`, `PARCIAL` | 1.500 caracteres |
  | `verificador` | `OK`, `FALHA`, `PARE`, `NÃO VERIFICADO` | 1.500 caracteres |
- **Travas no frontmatter:** o `maxTurns` (45 no `mecanico`, 60 no `seguranca`, 30 no `verificador`) corta a chamada e devolve a saída parcial; o que faltou vira chamada nova. O hook `tools/guarda_agentes.py` bloqueia, em todo agente:
  - git fora da lista de liberação, que só tem leitura (R1). A lista vale também para as opções (abreviação, `-O`, `-c` fora de `core.quotepath`, `i18n.logOutputEncoding` e `color.ui`) e barra configuração injetada pelo ambiente (`GIT_CONFIG_*`);
  - conteúdo do `.env` (R2);
  - `ORACLE_SANDBOX=1` em comando e, nas formas do grep 3.5, em qualquer arquivo que não seja documentação (`.md` e `.txt`) (R3);
  - gravação fora da pasta do perfil (R4), no `verificador` e no `seguranca`:
    - **onde gravam:** o `verificador` grava em `docs/entregas/`; o `seguranca`, só `decisao*.md` e `conferencia*.md` ali.
    - **pasta temporária:** os dois também gravam na pasta temporária (scratchpad), mas só pelo shell. A pasta temporária deixa de valer se contém a raiz do projeto.
    - **o que o guarda olha:** Write, Edit e, no Bash e no PowerShell (`guarda-r4-r5`), os destinos das formas comuns: redirecionamento; `tee`, `cp`, `mv`, `rm`, `mkdir`, `touch`, `sed -i`, `ln`, `tar -x`, `robocopy`, `xcopy`; e os cmdlets de conteúdo, item, cópia, remoção e arquivo, com aliases.
    - **variável e `cd`:** a variável vale só se foi atribuída com valor literal no começo do comando. O `cd` só conta com alvo literal.
    - **bloqueio por falha fechada:** destino que o guarda não resolve bloqueia. Comando não analisável também bloqueia: shell aninhado sem texto literal, `eval`, `iex`, `cmd /c`, `xargs` com gravação, splat, .NET que grava e aspas abertas.
  - gravação na fiação do guarda (R5), em todo perfil, por qualquer ferramenta:
    - em qualquer `.claude/` (o do projeto e o do usuário);
    - em `tools/guarda_agentes.py`;
    - no interpretador do hook: `sitecustomize.py`, `usercustomize.py`, `*.pth` em `site-packages`, executáveis `python`/`py` e as pastas `sys.prefix`.

    O guarda reconhece a fiação pelo nome, pelo caminho, pelo `realpath` e pelo ancestral em operação recursiva. Quando o destino não se resolve, o R5 também vale se o texto do comando citar a fiação. A leitura da fiação passa.

  Bloqueio volta como PARE. É guarda contra acidente, não sandbox (critério de 2026-11-23, `docs/plans/guarda-r4-r5.md` §5).

  **Residuais aceitos:**
  - gravação por interpretador (`python -c`, script);
  - programa que grava por opção própria fora da lista (N1);
  - no `mecanico`, destino não resolvido que não cita a fiação (N6);
  - as formas de evasão deliberada listadas nas conferências (`docs/entregas/guarda-r4-r5/conferencia_5b.md` a `conferencia_5e.md`).

  A detecção desses residuais é o `git status` e o hash da fiação (abaixo).

  **Formas que o guarda barra por falso positivo, com a alternativa:**
  - `$TEMP` no Bash: caminho literal;
  - `[IO.File]::Write*`: `Set-Content` ou `Out-File`;
  - destino com a variável do laço: gravar fora do laço;
  - no Git Bash, `robocopy /E`: `robocopy //E`, porque o Git Bash converte `/E` em `E:/`;
  - comando com `-Command -` ou `| bash`: texto literal em `-c`.

  **Sonda do `seguranca` que cita a fiação ou forma opaca:** é barrada, também no scratchpad, e o Write dele não grava fora de `decisao*`/`conferencia*`. Ele a descreve no arquivo da conferência, e a sessão principal a roda (L33).

  **Hash da fiação (N7):** antes e depois de cada delegação, a sessão principal grava o hash da fiação em `docs/entregas/<tarefa>/hash_fiacao_<antes|depois>.txt` e compara os dois. A fiação são os arquivos de `.claude/` do projeto, o `.claude/settings.local.json` (ignorado pelo git) e, no usuário, `~/.claude/agents/` e `~/.claude/settings*.json`. Diferença sem explicação é PARE, porque o `git status` não vê esses arquivos.

  ```bash
  find .claude ~/.claude/agents -type f 2>/dev/null | sort | xargs -r sha256sum; sha256sum ~/.claude/settings*.json 2>/dev/null
  ```

  Testado ao vivo em 2026-11-19 (`docs/entregas/ajuste-fino-subagentes/sondas.md`):
  - R1, R2 e R4 bloquearam, e o `git status` rodou;
  - hook que falha com código 1 bloqueia tanto com `onFailure: block` quanto com `|| exit 2`, cada um sozinho; os dois ficam no comando.

  Experimento com git que grava, ou que cite o `.env` ou o `dotenv`, também é bloqueado, mesmo num repositório de rascunho: o agente o descreve, e a sessão principal o roda.
- **SendMessage:** só para complemento curto do mesmo passo, com o agente abaixo do teto. Outra tarefa, outro passo ou agente perto do teto: agente novo.
- **`cd` na sessão principal:** no Bash da sessão principal, o `cd` persiste e muda o diretório de trabalho da sessão. Use caminho relativo à raiz ou `git -C`.
- **Paralelismo:** só com conjuntos de arquivos disjuntos; nunca dois agentes em `oracle_dba.py`, `main.py` ou `app.py`.
- **Conferência do retorno:** o ID do modelo veio; as contagens batem com o baseline; o diff inteiro foi lido; a classificação das mudanças em testes confere com o diff. O que o subagente afirma é afirmação a conferir; o modelo que ele informa se confirma na transcrição.
- **Retorno com PARE:** resolver com o responsável. Não redelegar a mesma coisa sem mudar o pedido.
- **Definições novas:** valem para o agente lançado depois da gravação. Em 2026-11-18, o 1º `verificador` depois da lista fechada de ferramentas teve 1º turno de 14,1 mil tokens, contra 34 a 35 mil antes. O `/agents` foi removido do Claude Code (2.1.327, 2026-11-19), e a confirmação passa a ser por evidência:
  1. YAML validado;
  2. modelo e 1º turno na transcrição, com `docs/entregas/revisao-subagentes-v2/medir_subagentes.py --desde <hora UTC>`;
  3. sonda do guarda, com um comando liberado e um bloqueado em chamadas separadas (L37).

  Para o `maxTurns`, use um agente temporário com limite baixo, como em `docs/entregas/aceite-subagentes/`.

## 4. Modelo de plano (`docs/plans/<tarefa>.md`)

1. **Contexto:** pedido do responsável, problema e achados da investigação (só leitura).
2. **Base:** branch, HEAD e baseline (passed e skipped).
3. **Arquivos:** por passo, com agente e modelo; disjuntos quando em paralelo.
4. **Passos:** o que muda, o teste que prova e o controle negativo (o teste novo deve falhar no código atual).
5. **Decisões do responsável:** pendentes e aprovadas, com data.
6. **Verificação:** comandos exatos, greps e contagem esperada. O `verificador` usa esta seção. Critério de campo opcional diz "quando presente", e o pedido ao `verificador` traz o valor esperado exato.
7. **GOVERNANCA_LOG:** linha prevista.
8. **Fora de escopo:** o que fica para item próprio.

## 5. Verificação padrão

Ordem: perfil, estado do git, pytest, greps. FALHA no passo 0 ou no 2: parar e informar, sem rodar de novo.

**Script.** Os passos 0 a 3 rodam com um comando, em primeiro plano e com timeout 600000:

```bash
python -I tools/verificacao_padrao.py --tarefa <t> --base <commit> --esperado <P>/<S> \
  [--previsto '<padrão>' ...] [--rotulo <r>] [--registry-pendente]
```

- **Saídas:** `docs/entregas/<t>/<rotulo>_*.txt` e `<rotulo>.md`. O script não sobrescreve: para rodar de novo, mude o `--rotulo`.
- **Código de saída:** 0 OK, 1 FALHA, 2 PARE ou NÃO VERIFICADO.
- **`--previsto`:** padrão fnmatch relativo ao projeto (`*` cruza `/`). A pasta da tarefa já entra como prevista.
- **`--registry-pendente`:** aceita mudança em `registry/` ou `db/` só se ela estiver commitada e todo commit trouxer "PENDENTE APROVAÇÃO".

Os comandos abaixo são a referência do script: mudou um, mude também o script e o `tests/test_verificacao_padrao.py`.

**Controle de mutação.** Um comando roda todas as mutações:

```bash
python -I tools/controle_mutacao.py --tarefa <t> --rotulo <r> --alvo <arquivo> --teste <arquivo de teste> \
  [--incluir <arquivo novo ou alterado> ...] --mutacoes-json docs/entregas/<t>/<r>.json
```

- **Como roda:** numa cópia `git archive HEAD` sem `.env`, mais os `--incluir`. O m0 (sem mutação) roda antes e precisa passar.
- **Cada mutação:** exatamente 1 substituição, com o fim de linha registrado; a saída vai para um arquivo próprio.
- **Código de saída:** 0 todas DETECTADAS, 1 alguma PASSOU (teste cego ou controle mal desenhado), 2 INVÁLIDA ou erro.
- **JSON de mutações:** grave com Write, porque o heredoc do Bash come a barra invertida.

**0. Perfil do Windows, só nomes** (PowerShell). Esperado: nenhuma linha. Com `override=False`, variável do perfil vence o `.env`.

```powershell
@((Get-Item 'HKCU:\Environment').Property) + @((Get-Item 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment').Property) | Where-Object { $_ -match '^(ORACLE_|EMAIL_|GEMINI_|AGENTDBA_|SCRIPTS_)' }
```

**1. Estado do git.** Esperado: só os arquivos previstos no plano. Caminho fora do previsto, rastreado ou não, é FALHA; em `tests/`, `src/` ou na raiz do projeto, parar antes do pytest. A raiz do git é `Workspace/`; o `-- .` limita ao projeto.

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
git grep -n -E "setenv\(['\"]ORACLE_SANDBOX['\"], *['\"]1|environ\[['\"]ORACLE_SANDBOX['\"]\] *= *['\"]1" -- '*.py'         # código que liga o sandbox
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
- **L12. Não rastreado fora da lista (2026-11-18; verificação da tarefa `processo-subagentes`).** O `verificador`, ainda com a definição antiga, marcou o `git status` como OK listando um não rastreado fora da lista prevista (`docs/entregas/revisao_fases_1_2/revisao_adversarial_gemini.md`, criado às 12:28 fora da sessão). → Caminho fora do previsto, rastreado ou não, é FALHA no retorno; em `tests/`, `src/` ou na raiz, parar antes do pytest; a sessão principal confere a lista do retorno. → Comparar o `git status` da abertura com o do retorno.

- **L13. Produção que passa a ler o `.env` (2026-11-18; fase 3, `427adfc`).** Quando a entrada passou a chamar `dotenv_values`, as fixtures de fluxo, que só neutralizavam `load_dotenv`, teriam lido o `.env` real na primeira execução em processo. → Primeiro proteger as fixtures (stub da função + guarda em `dotenv.main.DotEnv.__init__`, que pega todo leitor, inclusive nomes ligados no import), depois editar a produção; o guarda fica no leitor, não na função, porque a produção sempre passa o caminho real. → `leituras_env_reais != []` no teardown.
- **L14. Variante de teste cega à mutação (2026-11-18; fase 3, D6.4b).** Na mutação "`ORACLE_SANDBOX_DO_OPERADOR = None` fixo", a variante parametrizada "ausente" passou, porque `None` coincide com ausente; só a variante "0" detectou. → Em todo controle de mutação, confirmar que **ao menos uma** variante falha e registrar as que passam por construção. → Linha "com mutação" com passed na tabela de controle.
- **L15. Regra de um item aplicada ao arquivo inteiro (2026-11-18; fase 3, X5 do `verificador`).** A regra "fictício sem `ORACLE_SANDBOX`" do D6.1 foi lida como regra para todo `test_carga_env_entrada.py`, que tem `ORACLE_SANDBOX=1` em fictício de subprocesso, como o CLAUDE.md permite. → No pedido ao `verificador`, citar o escopo de cada regra (item, arquivo) e a regra do CLAUDE.md que vale. → DIVERGE sem arquivo:linha da regra violada.

- **L16. grep do Git Bash não enxerga CR (2026-11-18; fase 4, passo 1).** A contagem de linhas terminadas em CR com `grep -c` deu 0 linhas só-LF num arquivo LF; a mutação foi escrita com CRLF, não se aplicou (0 substituições) e a cópia passou. → Medir fim de linha em bytes com Python e `assert` na contagem de substituições. → Contagem 0 ou diff vazio entre original e mutante (L3).
- **L17. Correção sugerida sem efeito (2026-11-18; fase 4, Achado 4).** A revisão sugeriu `Settings(env_file=None)`; o pydantic-settings ignora o kwarg em silêncio (`extra="ignore"`) e o Chroma continuava lendo `.env`. O argumento certo é `_env_file`. → Medir o efeito da correção sugerida antes de adotá-la e usar a forma sugerida como mutação de controle. → Kwarg aceito sem erro e contagem igual à de antes.
- **L18. Controle que passa (2026-11-18; fase 4, passos 1 e 4).** Remover só o `pop` de antes da carga passou, porque os teardowns já restauravam o estado; `fixturenames` passou sem `autouse`, porque uma fixture autouse dependia da guarda. → Controle que passa exige decidir se o controle está mal desenhado (reproduzir o estado do commit-base, removendo todo o mecanismo) ou se o teste é cego (L14); conferir dependências implícitas. → Linha "com mutação" com passed.
- **L19. Modo de plano pausa agentes (2026-11-18; fase 4, passo 0).** O `verificador` lançado em segundo plano parou quando a sessão entrou em `/plan` e voltou PARCIAL. → Lançar agentes depois da aprovação do plano, ou entrar em `/plan` sem agente rodando. → Retorno "pausado pelo modo de plano".
- **L20. Controle sem saída gravada (2026-11-18; fase 4, passo 4).** O `mecanico` não guardou as saídas do pytest das mutações; a reexecução deu 14 errors onde o retorno dizia 12. → Pedir arquivo de saída por controle e conferir antes do commit. → Contagem do retorno sem arquivo que a sustente.
- **L21. Merge antes das verificações do aceite condicional (2026-11-18; pós-fase 4).** O fast-forward `19f19f2 → 8810b6e` (20:10) foi feito antes das 3 verificações do aceite condicional e antes do registro do aceite. A árvore integrada era a testada (269/16 em `8810b6e` às 19:22, registrado só na transcrição), e o primeiro pytest pós-merge só rodou em `66a15d7`. → Sequência: verificações do aceite → registro do aceite → merge → pytest pós-merge; saída da suíte do commit a integrar gravada em `docs/entregas/`. → `main` à frente sem linha de aceite no GOVERNANCA_LOG; suíte citada sem arquivo que a sustente.
- **L22. Caminho de falha sem a variável do operador (2026-11-18; `registro_pos_merge`, T2).** O teste do `.env` ausente (`test_f4c2`) rodava sem `ORACLE_SANDBOX` no filho e só na CLI; "valor do shell preservado" nesse caminho ficou sem teste até o T2. → Em teste de caminho da carga do `.env` (ok, ausente, falha), cobrir também a variável já presente no ambiente (sentinela `"0"`) e as duas entradas. → Teste da carga sem `sandbox_shell` ou sem `[cli]` e `[web]`.
- **L23. Invariante só em comentário (2026-11-18; `registro_pos_merge`, T1).** "texto idêntico em app.py e src/main.py" (`app.py:37`) não tinha teste; a igualdade dependia da revisão do diff. → Invariante escrita em comentário vira teste ou entra no §5. → Comentário com "idêntico", "sempre" ou "nunca" sem teste que o cite.
- **L24. Custo concentrado em chamadas longas (2026-11-18; `revisao-subagentes-v2`).** 7 de 66 chamadas de subagente, todas com mais de 60 turnos, somaram 63% dos 146 M tokens de entrada: cada turno relê o contexto inteiro, e a suíte de cerca de 4,5 min levou a pytest em segundo plano com Monitor e `sleep`. → Uma chamada por passo e por controle, teto de chamadas no agente, pytest em primeiro plano com timeout 600000 e verificação pelo `tools/verificacao_padrao.py`. → `medir_subagentes.py`: chamada com mais de 40 turnos.
- **L25. Medição de transcrição (2026-11-18; `revisao-subagentes-v2`, errata A2, A3 e A7).** A revisão comparou horas UTC da transcrição (`Z`) com o git em −03:00, concluiu "o PROCESSO.md não é lido" olhando só as chamadas Read (as 10 chamadas o citavam por Bash) e estimou o custo fixo pela média de chamadas curtas. → Mesmo fuso antes de comparar; ausência só depois de conferir Read, Grep e Bash; custo fixo pelo 1º turno. → Horário sem fuso numa comparação; ausência afirmada com uma só ferramenta conferida.
- **L26. `cd` na sessão principal (2026-11-18; `revisao-subagentes-v2`, passo 2).** Um `cd docs/entregas/...` no Bash da sessão principal mudou o diretório de trabalho da sessão; o `seguranca`, lançado em seguida, recebeu a correção de caminho por SendMessage. → Na sessão principal, sem `cd`: caminho relativo à raiz ou `git -C`. → Aviso de diretório de trabalho mudado.
- **L27. Verificação que falha aberta (2026-11-18; `revisao-subagentes-v2`, conferência do `seguranca`).** A 1ª versão do script dava OK com o PowerShell saindo com código 0 e erro só no stderr, com a origem de uma renomeação descartada e com `--base` que virava opção do git (`--output=` gravava fora de `docs/entregas`). → Todo dado externo (código, stderr, argumento) passa por função pura testada que falha fechado; argumento repassado ao git é validado e resolvido (`rev-parse --verify --end-of-options`); uma mutação por guarda. → Conferência do `seguranca` antes do commit do script.
- **L28. Definição nova vale já (2026-11-18; `revisao-subagentes-v2`, verificação final).** O §3 mandava confirmar definição nova só no próximo chat, mas o `verificador` lançado depois da reescrita já usou a nova: 1º turno de 14,1 mil tokens, contra 34 a 35 mil, e retorno no formato novo. O "ainda com a definição antiga" da L12 não foi medido. → Medir o 1º turno da 1ª chamada depois da mudança, em vez de supor a definição antiga. → 1º turno diferente do histórico logo depois da mudança.
- **L29. Marcador procurado em texto livre (2026-11-19; `ajuste-fino-subagentes`, controle do `controle_mutacao`).** "FALHA DE GOVERNANCA" era procurado em qualquer lugar da saída e casava com a fonte do teste que o pytest imprime ao falhar; o `verificacao_padrao` (`d2ebec8`) tinha o mesmo defeito. → Marcador de saída só na forma exata do produtor, medida antes (linha inteira; prefixo do `pytest.exit`), e teste com o texto citado num teste que falha. → Mutação INVÁLIDA por "FALHA DE GOVERNANCA" com testes caídos.
- **L30. Timeout do subprocess no Windows (2026-11-19; `ajuste-fino-subagentes`, smoke).** O `subprocess.run(timeout=560)` matou só o processo de cima e esperou os filhos: a suíte rodou 43 min, e o resultado só saiu no fim. → `Popen` e `taskkill /F /T` no estouro (`_executar`). → Duração do pytest acima do timeout com "tempo excedido".
- **L31. Gravação por Bash e por Python no Windows (2026-11-19; `ajuste-fino-subagentes`).** O heredoc do Bash da ferramenta passou `\\` como `\` (JSON inválido), e o `Path.write_text` gravou CRLF (mutação de várias linhas com 0 ocorrências, L16). → Arquivo com barra invertida ou cujo fim de linha importa: Write, ou `write_bytes`; medir o CRLF depois. → "Invalid \escape", `SyntaxWarning` de escape, ou "aparece 0 vez(es)" com CRLF > 0.
- **L32. Corte de comentário que esconde código (2026-11-19; `ajuste-fino-subagentes`, conferência v2 do guarda).** O guarda tirava o `# ...` zerando as aspas a cada linha e sem tratar `\"`; um `git commit` depois de um `#` dentro de string passaria. → Na dúvida, não cortar: comentário com aspas ou crase fica, o estado das aspas segue entre linhas e a continuação de linha é juntada antes. → Mutação que restaura o corte ingênuo deve dar DETECTADA.
- **L33. Guarda limita o experimento do `seguranca` (2026-11-19; `ajuste-fino-subagentes`).** O guarda bloqueou o script de ataque do `seguranca` (R2, `load_dotenv()` no texto), e a conferência ficou "por leitura". → Experimento bloqueado vai descrito no arquivo de conferência, e a sessão principal o roda. → "não medido (bloqueado pelo guarda)" na conferência.
- **L34. Tipo de agente novo aparece com atraso (2026-11-19; `ajuste-fino-subagentes`, sondas).** Arquivo novo em `.claude/agents/` deu "Agent type not found" na hora; o tipo só apareceu depois de alguns segundos. A edição de agente existente vale na próxima chamada (L28). → Para sonda, esperar o aviso de tipo novo antes de chamar. → "Agent type ... not found".
- **L35. Carga da máquina e suíte (2026-11-19; `ajuste-fino-subagentes`, smoke).** A suíte, de 271 s, levou 2.619 s com um `seguranca` de 49 min em paralelo, e 1 teste de subprocesso estourou o limite dele. → Suíte inteira sozinha, sem agente pesado em paralelo. → Duração muito acima da habitual; TimeoutExpired em teste de subprocesso.
- **L36. Lista de liberação também nas opções (2026-11-19; `guarda-r1-r3`).** A 1ª lista do R1 olhava só o subcomando. Com abreviação (`--no-exclude`), `-c grep.fallbackToNoIndex`, `--attr-source`, `xargs git`, flags combinadas (`-qd`, `-wt`) e `GIT_CONFIG_*` no ambiente, o git ainda lia o `.env` ou gravava. → Liberar por subcomando e por opção (prefixo de 6+ caracteres, `-c` por chave, configuração pelo ambiente barrada); a sessão principal roda a sonda no repositório de rascunho. → Conferência com "passa no guarda e o git aceita".
- **L37. Guarda barra o comando inteiro (2026-11-19; `guarda-r1-r3`, sonda ao vivo).** Um comando liberado e um barrado juntos numa chamada fazem o guarda barrar tudo. → Sonda e verificação em chamadas separadas quando uma delas pode ser barrada. → Bloqueio de comando que tem parte liberada.
- **L38. `/agents` removido (2026-11-19; `aceite-subagentes`).** O aceite dependia de conferir os agentes com `/agents`, que a versão 2.1.327 não tem mais. → Conferir por evidência: YAML, modelo e 1º turno na transcrição, sonda do guarda e `maxTurns` por agente temporário (§3). → "The /agents wizard has been removed".
- **L39. Heredoc que cita comando barrado (2026-11-19; `aceite-subagentes`, sonda do `mecanico`).** O guarda leu o texto de um heredoc que citava `git add` e barrou o comando que só gravava um arquivo. → Arquivo cujo texto cita comando barrado: gravar com Write. → Bloqueio R1 ou R2 em comando que só grava arquivo.

- **L40. Conferência que não converge (2026-11-23; `guarda-r4-r5`, 5 rodadas).** Contra um analisador do que grava, cada conferência do `seguranca` achou uma família nova (D1 a D16, E1 a E15, F1 a F3, G1 e G2), cada vez mais deliberada (`builtin cd`, `C"D"PATH`, `$a,$b =`). → Antes de abrir a conferência de código de guarda, fixar no pedido o modelo de ameaça (acidente ou evasão) e o critério de CONFORME; a última rodada é estreita, só sobre o diff. → Achado que só aparece em quem procura contornar.
- **L41. Comparação de versões com módulo carregado de cópia (2026-11-23; `guarda-r4-r5`, não regressão).** O guarda antigo, carregado do scratchpad, calculou a `RAIZ` pelo próprio `__file__` e barrava toda gravação em `docs/entregas/`: os bloqueios novos ficaram mascarados (o commit `819311b` disse 1; eram 10). → Passar a raiz explícita aos dois lados (`decidir(..., raiz=<projeto>)`) e contar nos dois sentidos (novos e sumidos). → "Deixaram de existir" grande e sem explicação.
- **L42. Git Bash converte `/X` em caminho (2026-11-23; `guarda-r4-r5`, N29f, medido).** `robocopy /E a b` virou origem `E:\` e destino `a`; `/NJH` virou `C:/Program Files/Git/NJH`. → No Git Bash, opção de programa Windows com `//X`; o guarda bloqueia `/X` de uma barra no Bash. → "Parâmetro Inválido" com caminho `C:/Program Files/Git/...`.
- **L43. Regra de bloqueio medida contra as chamadas reais (2026-11-19/23; `guarda-r4-r5`).** O 1º desenho do R4 no shell barrava 7 chamadas reais do `seguranca` e 29 do `verificador` (prefixo estrito, `cd` antes da atribuição, varredura larga de variáveis). → Antes do commit de regra nova do guarda, reprocessar as chamadas dos subagentes nas transcrições e explicar cada bloqueio novo. → Bloqueio de comando que o agente já usou em trabalho normal.
- **L44. Correção de falso positivo que abre falha (2026-11-23; `guarda-r4-r5`, G1).** Para liberar `BashOutput` (O2), o verbo passou a contar só como palavra inteira, e `overwrite_file`, `remove_file` e `text_editor` ficaram liberados. → Ao estreitar um casamento, rodar velho contra novo e exigir zero BLOQ→LIB fora dos casos pretendidos. → BLOQ→LIB na comparação.
- **L45. Sonda do `seguranca` no scratchpad (2026-11-23; `guarda-r4-r5`, conferências 5b e 5d).** O Write do `seguranca` só grava `decisao*`/`conferencia*` em `docs/entregas/`, e o shell barra a sonda que cita a fiação ou forma opaca; a recomendação "grave com Write" (L39) não vale para ele. → Sonda que cita a fiação fica descrita na conferência e a sessão principal a roda; sonda pura de `gs.decidir` vai em `python -I -c`, sem gravar. → PARE do `seguranca` por R4 ou R5 ao gravar sonda.
- **L46. Gerador de mutação em arquivo CRLF (2026-11-23; `1.11-V2-item6`, passo 6).** O gerador leu o `oracle_dba.py` com `read_text`, que converte para LF, e as 5 mutações de várias linhas não casaram no alvo em CRLF: o controle deu ERRO ("'de' aparece 0 vez(es)"). O blob no git está em LF e a árvore de trabalho em CRLF, e a cópia da mutação usa a árvore (`--incluir`). → Ler o alvo com `newline=""`, converter os trechos escritos à mão para o fim de linha do alvo e conferir que cada `de` casa 1 vez antes de delegar; medir o diff do mutante sobre a árvore de trabalho (L16, L31). → "aparece 0 vez(es)" com CRLF > 0.
- **L47. `verificador` em segundo plano (2026-11-23; `1.11-V2-item6`, passos 6 e 8).** O `verificador` mandou os comandos longos para segundo plano, contra a regra do agente, e no passo 8 devolveu PARE sem ver o resultado. Os resultados usados foram os arquivos gravados pelo script ao terminar, conferidos pela sessão principal. → Conferir o resultado sempre no arquivo de saída (tabela completa, linha final do pytest com a duração, "Resultado:" do controle de mutação), nunca só pelo retorno. → Notificação "waiting on its own background work"; retorno sem a tabela.
- **L48. Versionar um `.py` muda o alcance dos greps (2026-11-23; `c03a966`).** O `medir_subagentes.py` entrou no git e o grep 3.6 do §5 passou a dar FALHA, um falso positivo em "tokens". A verificação padrão não foi rodada depois daquele commit, e a FALHA só apareceu na verificação do item 6. → Rodar a verificação padrão depois de qualquer commit que versione código, mesmo que seja só docs ou chore. → FALHA nova num grep sem mudança de código no diff.

## 8. Abertura de chat (para o responsável)

Quatro linhas bastam para a sessão principal decidir se vai ao `/plan`, montar os pedidos do §3 sem perguntar o óbvio e parar no limite:

```text
Tarefa <id>: <objetivo em uma linha>. Tipo: leitura | alteração.
Base: branch <b> (HEAD <hash>, se importar).
Restrições e autorização: <texto literal | nenhuma>.
Limite de tempo: <minutos>. Entregável: <chat | docs/entregas/... | commit>.
```
