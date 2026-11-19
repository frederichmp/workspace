# Plano: ajuste fino dos subagentes (`ajuste-fino-subagentes`)

## 1. Contexto

**Pedido do responsável (2026-11-18):** "mete bronca, vamos deixá-los com um fine tuning perfeito", depois da `revisao-subagentes-v2`.

**Decisões do responsável sobre a v2 (2026-11-18):**
- `docs/_tmp/` é de outro chat do responsável.
- Riscos aceitos:
  - arquivo não rastreado fica fora do `git grep` e do 3.7;
  - `--previsto 'docs/*'` continua aceito.

**Evidência:**
- **A v2 já rende.** O 1º turno do `verificador` caiu de 34 a 35 mil tokens para 14,1 mil. O `seguranca` lançado antes da reescrita ainda custou 35,0 mil.
- **As regras críticas ainda são só texto:** git que grava, `.env`, `ORACLE_SANDBOX=1`, onde cada agente grava e o teto de chamadas. Nada impede o agente de descumpri-las.
- **A documentação traz as travas.** Fonte: `claude-code-guide` (resumo de WebFetch, a conferir nos links code.claude.com/docs/en/sub-agents e /hooks). Versão instalada: 2.1.327.
  - `maxTurns`: teto rígido; o agente devolve a saída marcada como parcial.
  - `hooks` no frontmatter: rodam só enquanto o agente está ativo; exit 2 bloqueia a chamada, com o motivo no stderr.
  - `onFailure: "block"` (2.1.295+): falha, timeout ou JSON inválido do hook também bloqueiam.
- **O controle de mutação é o maior custo.** As 7 chamadas mais longas (63% dos tokens) eram passos com controles de mutação feitos à mão (L3, L14, L16, L18, L20).
- **Critério ambíguo no plano anterior.** O `verificador` leu "`effort` ∈ {...}" como campo obrigatório.

## 2. Base
- Branch `main`, HEAD `0e3fd62`, árvore rastreada limpa.
- Baseline: 352 passed e 16 skipped (`docs/entregas/revisao-subagentes-v2/final.md`).
- Não rastreados previstos: `docs/_tmp/pendencia1_evidencias.md` (do responsável), `docs/plans/1.11-item1-B-refeito.md` e `docs/entregas/...`.
- `.env` ignorado pelo git (conferido).
- Modelo da sessão: claude-opus-5-5.

## 3. Decisões que este plano pede

1. **Dois scripts novos como §2.** `tools/controle_mutacao.py` e `tools/guarda_agentes.py` são tratados como código do §2, como o `verificacao_padrao`: escritos por Opus e conferidos pelo `seguranca` com effort `high` antes do commit.
2. **Hooks só nos 3 agentes**, no frontmatter. A sessão principal (`.claude/settings.json`) fica de fora.
3. **`maxTurns`:** 45 no `mecanico`, 60 no `seguranca` e 30 no `verificador`. É 1,5 a 2 vezes o teto escrito, para o agente conseguir gravar o parcial antes do corte.

## 4. Arquivos

Todos são escritos pela sessão principal (claude-opus-5-5).

| Passo | Arquivo | Ação |
|---|---|---|
| 0 | `docs/plans/ajuste-fino-subagentes.md` | novo: cópia deste plano |
| 0 | `docs/GOVERNANCA_LOG.md` | linha com as decisões do responsável sobre a v2 |
| 1 | `tools/controle_mutacao.py` e `tests/test_controle_mutacao.py` | novos (§2) |
| 2 | `tools/guarda_agentes.py` e `tests/test_guarda_agentes.py` | novos (§2) |
| 3 | `.claude/agents/mecanico.md`, `seguranca.md` e `verificador.md` | `maxTurns`, `hooks` e corpo |
| 4 | `docs/PROCESSO.md` (§2, §3, §4 e §5) | editado |
| 5 | `docs/GOVERNANCA_LOG.md` e `docs/PROCESSO.md` §7 | registro e lições |

Ficam intocados: `src/`, `app.py`, `db/`, `registry/`, `.claude/settings.json`, `CLAUDE.md` e a memória local.

## 5. Passos

### Passo 0: plano e decisões da v2
- Commit 1: `docs: plano do ajuste-fino-subagentes`.
- Commit 2: `docs: decisoes do responsavel sobre a revisao-subagentes-v2`. A linha nova no log registra a origem do `docs/_tmp/` e os riscos aceitos.

### Passo 1: `tools/controle_mutacao.py`

Faz numa chamada o controle de mutação que hoje o agente monta à mão.

```bash
python -I tools/controle_mutacao.py --tarefa <t> --rotulo <r> --alvo <arquivo> --teste <caminho ou nodeid> [--teste ...] \
  --mutacao <nome> <de> <para> [--mutacao ...] [--incluir <arquivo do working tree> ...]
```

**Cópia:**
- Faz `git archive HEAD` do projeto, extraído com `tarfile` (filtro `data`) num diretório temporário fora do repositório.
- Copia também os arquivos de `--incluir` do working tree (arquivos novos, ainda não commitados).
- Falha se a cópia tiver `.env`. Apaga o diretório temporário no fim.

**m0 (sem mutação):** roda primeiro e precisa passar. Se não passar, o controle é inválido.

**Cada mutação:**
- `de` precisa ter exatamente 1 ocorrência, em bytes UTF-8 (L3, L16).
- O fim de linha é medido e registrado.
- Roda só os `--teste` na cópia, com ambiente sem `ORACLE_SANDBOX` e `PYTHONDONTWRITEBYTECODE=1`.
- A saída vai para `docs/entregas/<t>/<r>_<nome>.txt` (L20). O arquivo é aberto com `open("x")` e nunca sobrescrito.

**Classificação do resultado:**
- **DETECTADA:** pytest com código 1 e ao menos 1 failed ou error.
- **PASSOU:** código 0 (L14, L18).
- **INVÁLIDA:** qualquer outro código, por exemplo uma mutação que quebra a coleta.

**Saída:** a tabela vai para o stdout e para `<r>.md`. Código de saída: 0 quando todas as mutações foram detectadas; 1 quando alguma passou; 2 quando o controle é inválido ou houve erro.

**Validações** (as mesmas do `verificacao_padrao`):
- `--tarefa` e `--rotulo` validados;
- `--alvo`, `--teste` e `--incluir` relativos ao projeto, sem `..`, sem `.env`;
- erro inesperado sai com 2.

**Testes** (`tests/test_controle_mutacao.py`): funções puras (troca com contagem e fim de linha, classificação, validações) e o `main` com fakes. Sem subprocesso real.

**Controle:** o próprio script, aplicado a uma cópia dele mesmo. Cada guarda ganha uma mutação, e todas devem dar DETECTADA.

### Passo 2: `tools/guarda_agentes.py` (hook PreToolUse)

**Como roda:** `python -I "$CLAUDE_PROJECT_DIR/tools/guarda_agentes.py" --perfil <mecanico|seguranca|verificador>`. O script lê do stdin o JSON do hook (`tool_name`, `tool_input`). Exit 0 libera; exit 2 bloqueia, com motivo e regra no stderr e o pedido "devolva PARE, não contorne". Erro interno também sai com 2.

**Regras:**
- **R1. git que grava** (todos os perfis), também quando vem depois de opções globais (`-C caminho`, `-c k=v`, `--no-pager`):
  - bloqueados: `add`, `commit`, `push`, `pull`, `fetch`, `clone`, `init`, `stash`, `reset`, `checkout`, `switch`, `restore`, `rebase`, `merge`, `cherry-pick`, `revert`, `clean`, `rm`, `mv`, `tag`, `am`, `apply`, `worktree`, `submodule`, `update-ref`, `gc`, `prune`, `notes`, `replace` e `filter-branch`;
  - `branch` só é bloqueado com opção de alteração (`-d`, `-D`, `-m`, `-M`, `-c`, `-C`, `--delete`, `--move`, `--copy`, `--force`);
  - `config` só é bloqueado sem `--get`, `--list` ou `-l`;
  - liberados: `status`, `diff`, `log`, `show`, `grep`, `ls-files`, `rev-parse`, `archive` e `blame`.
- **R2. Conteúdo do `.env`** (todos os perfis):
  - Read, Grep, Write e Edit com caminho de nome `.env` ou `.env.*`, salvo `.env.example`, sem diferenciar maiúsculas;
  - Bash e PowerShell com `.env` como palavra; ficam fora o `.env.example` e o `\.env$` de regex;
  - `grep`, `findstr` ou `Select-String` recursivo sobre `.`.
- **R3. `ORACLE_SANDBOX=1`** (todos os perfis):
  - em comando: `ORACLE_SANDBOX=1`, `$env:ORACLE_SANDBOX = '1'` ou `setx ORACLE_SANDBOX 1`;
  - em Write ou Edit de arquivo em `tests/` que contenha o padrão do grep 3.5.
- **R4. Onde grava:**
  - `verificador`: Write e Edit só em `docs/entregas/`;
  - `seguranca`: só `docs/entregas/**/decisao*.md` e `conferencia*.md`.

**Testes** (`tests/test_guarda_agentes.py`):
- função pura `decidir(perfil, ferramenta, entrada, raiz)`, com casos bloqueados e liberados, incluindo os comandos reais dos agentes: pytest padrão, `verificacao_padrao`, `git grep '(^|/)\.env$'`, `git -C "$R" archive` e `git status`;
- o `main` com stdin: 0, 2, JSON inválido e perfil inválido.

**Controle:** `controle_mutacao.py` com uma mutação por regra.

**Ordem dos passos 1 e 2:**
1. Escrever os scripts e os testes.
2. Rodar os controles.
3. Chamar o `seguranca` (effort `high`) para conferir os dois scripts, antes dos hooks, para que um defeito do guarda não o bloqueie.
4. Corrigir o que vier NÃO CONFORME.
5. Commit 3: `feat(tools): controle de mutacao em script, com testes`. Commit 4: `feat(tools): guarda dos subagentes (hook PreToolUse), com testes`.

### Passo 3: agentes

Frontmatter novo, igual nos três (muda só o número e o perfil):

```yaml
maxTurns: 45
hooks:
  PreToolUse:
    - matcher: "Bash|PowerShell|Read|Grep|Glob|Write|Edit"
      hooks:
        - type: command
          command: 'python -I "$CLAUDE_PROJECT_DIR/tools/guarda_agentes.py" --perfil mecanico'
          onFailure: block
```

**Corpo:**
- **Todos:** "bloqueio do guarda é PARE: não contorne". O teto escrito fica, e o `maxTurns` é o corte rígido.
- **`mecanico`:** controle de mutação pelo `tools/controle_mutacao.py`. Essa ferramenta substitui as linhas de L3, L16 e L20 do corpo.
- **`verificador`:** antes de dar FALHA por um critério do plano, conferir se outro trecho do plano o contradiz. Se contradizer, informar "critério ambíguo" com os dois `arquivo:linha`.

**Teste ao vivo** (a definição vale na próxima delegação). Uma chamada curta do `verificador` com 4 sondas:
- `git stash list`: deve ser bloqueado (R1);
- Read de um `.env` fictício no scratchpad, com conteúdo sentinela: deve ser bloqueado (R2);
- Write em `docs/_sonda.md`: deve ser bloqueado (R4);
- `git status --short -- .`: deve passar.

Se o mecanismo falhar (shell, `$CLAUDE_PROJECT_DIR`), corrigir antes do commit. Medir também o 1º turno.

Commit 5: `chore(claude): agentes com maxTurns, guarda por hook e controle de mutacao por script`.

### Passo 4: `docs/PROCESSO.md`
- **§2:** entram `tools/controle_mutacao.py` e `tools/guarda_agentes.py`.
- **§3:** `maxTurns`, guarda (o que bloqueia; bloqueio é PARE) e PARCIAL do `maxTurns`, que vira chamada nova com o que falta.
- **§4:** critério de campo opcional diz "quando presente", e o pedido ao `verificador` traz o valor esperado exato.
- **§5:** comando do controle de mutação.

Commit 6: `docs: guarda, maxTurns e controle de mutacao no PROCESSO`.

### Passo 5: verificação, registro e lições
1. **Verificação pelo `verificador`**, já com a definição nova e o guarda. Roda `verificacao_padrao` com o rótulo `final` (esperado: 352 + N1 + N2 passed e 16 skipped) e valida o YAML.
2. **Registro.** Linha no GOVERNANCA_LOG.
3. **Lições novas no §7.**

Commit 7: `docs: registra ajuste-fino-subagentes no GOVERNANCA_LOG e licoes`.

## 6. Verificação
- **Testes novos:** os arquivos novos passam, e todas as mutações dão DETECTADA (m0 passa).
- **Sondas ao vivo:** os 3 bloqueios acontecem e o `git status` passa.
- **YAML estrito:** só as chaves `name`, `description`, `model`, `effort` (quando presente), `color`, `tools`, `maxTurns` e `hooks`; `maxTurns` inteiro; `hooks.PreToolUse[0].hooks[0].onFailure == "block"`.
- **Verificação final:**

  ```bash
  python -I tools/verificacao_padrao.py --tarefa ajuste-fino-subagentes --base 0e3fd62 \
    --esperado <352+N1+N2>/16 --rotulo final \
    --previsto 'docs/entregas/1.11/item1/*' --previsto 'docs/entregas/isolamento_env/fase4/*' \
    --previsto 'docs/entregas/processo-subagentes/*' --previsto 'docs/entregas/registro_pos_merge/*' \
    --previsto 'docs/entregas/revisao-subagentes-v2/*' --previsto docs/plans/1.11-item1-B-refeito.md \
    --previsto docs/_tmp/pendencia1_evidencias.md
  ```

  Esperado: código de saída 0.

## 7. GOVERNANCA_LOG (linha prevista)

Commits 1 a 6:
- dois scripts novos com N1 + N2 testes;
- agentes com `maxTurns` e guarda;
- sondas ao vivo;
- controles;
- conferência do `seguranca`;
- pytest;
- autoria claude-opus-5-5.

Status: aguardando revisão.

## 8. Fora de escopo
- Hooks na sessão principal (`.claude/settings.json`).
- `omitClaudeMd`, `isolation: worktree`, `permissionMode`, `skills` e `memory`.
- Enxugar o `CLAUDE.md`, que entra em todo turno dos agentes.
- O guarda é contra acidente, não um sandbox: um subprocesso Python ainda consegue contornar as regras.
