# Plano: lista de liberação no R1 e R3 fora de `tests/` (`guarda-r1-r3`)

## 1. Contexto

**Decisões do responsável (2026-11-19)** sobre as pendências do `ajuste-fino-subagentes`:
1. O R1 do guarda passa a ser lista de liberação, como recomendaram a sessão principal e o `seguranca`.
2. O R3 de Write e Edit passa a valer também fora de `tests/`.
3. Ficam aceitos os residuais:
   - subprocesso;
   - glob sem recursão no PowerShell;
   - nome 8.3 e link simbólico;
   - `setenv` com valor inteiro;
   - credenciais herdadas pelo processo filho do controle de mutação.

   A lista de liberação fecha também o alias do git e o `git grep --no-index`.

**Dados levantados (só leitura):**
- **Subcomandos do git que os subagentes usaram nas transcrições.**
  - De leitura: diff 142, status 130, grep 98, rev-parse 49, show 41, log 35, ls-files 29, archive 26, branch 9, config 8, check-ignore 5, ls-tree 3, check-attr 2, hash-object 1, cat-file 1, remote 1. Todos entram na lista.
  - De escrita: commit, add, stash, reset, rm, init e outros. São de antes da regra "não commita" ou de repositório de rascunho, e continuam bloqueados.
- **Grep 3.5 sobre todos os `.py` versionados:** nenhuma linha hoje.

## 2. Base
- Branch `main`, HEAD `69734c4`, árvore rastreada limpa.
- Baseline: 552 passed e 16 skipped (`docs/entregas/ajuste-fino-subagentes/final.md`).
- Modelo da sessão: claude-opus-5-5.
- Não rastreados previstos: `docs/_tmp/` (do responsável), `docs/plans/1.11-item1-B-refeito.md` e `docs/entregas/...`.

## 3. Desenho que este plano pede para aprovar

### D1. Lista de liberação do R1 (`tools/guarda_agentes.py`)

**Liberados sem condição:**
- status, diff, log, show, grep, ls-files, ls-tree;
- rev-parse, rev-list, archive, blame, cat-file, describe, shortlog;
- show-ref, for-each-ref, merge-base, name-rev, check-ignore, check-attr;
- count-objects, version, help, var, whatchanged, range-diff, cherry;
- diff-tree, diff-files, diff-index, show-branch, verify-commit, verify-tag.

**Liberados com condição:**
- `branch`: sem criar nem alterar (regra atual);
- `config`: só leitura (`--get*`, `--list`, `-l`);
- `remote`: sem argumento, ou com `-v`, `show` ou `get-url`;
- `reflog`: sem `expire` nem `delete`;
- `symbolic-ref`: só leitura (1 posicional, sem `-d`);
- `hash-object`: sem `-w`;
- `grep` e `diff`: sem `--no-index`; o `grep` também sem `--no-exclude-standard`, porque essas opções leem arquivo fora do índice, inclusive o `.env`.

**Todo o resto é bloqueado**, inclusive alias, com o motivo "git fora da lista de liberação". As opções globais (`-C`, `-c`, `--git-dir` etc.) continuam sendo puladas como hoje, e subcomando indeterminado continua bloqueado.

### D2. R3 fora de `tests/`
- Write ou Edit em qualquer arquivo do projeto que contenha as formas do grep 3.5 é bloqueado, como hoje em `tests/`.
- Exceção: documentação (`.md` e `.txt`), para que o `seguranca` possa citar no arquivo de conferência o código que confere.
- O `.env` fictício com `ORACLE_SANDBOX=1` continua permitido, porque não está nas formas do grep 3.5.

### D3. Complemento na verificação
- O grep 3.5 do §5 passa a varrer `'*.py'` (hoje é `'tests/*.py'`), no `tools/verificacao_padrao.py` e no `docs/PROCESSO.md`.
- O teste de igualdade com o §5 já cobre a mudança.
- Hoje o grep não acha nada em nenhum `.py`.

## 4. Arquivos

Todos são escritos pela sessão principal (claude-opus-5-5).

| Passo | Arquivo | Ação |
|---|---|---|
| 0 | `docs/plans/guarda-r1-r3.md` e `docs/GOVERNANCA_LOG.md` | cópia deste plano; linha com as decisões e os residuais aceitos |
| 1 | `tools/guarda_agentes.py` e `tests/test_guarda_agentes.py` | R1 por lista de liberação (D1) |
| 2 | os mesmos | R3 fora de `tests/` (D2) |
| 3 | `tools/verificacao_padrao.py`, `tests/test_verificacao_padrao.py` e `docs/PROCESSO.md` (§5) | grep 3.5 em `'*.py'` (D3) |
| 4 | `docs/PROCESSO.md` (§3) e `.claude/agents/*.md` | texto do guarda: lista de liberação; R3 fora de `tests/` |
| 5 | `docs/GOVERNANCA_LOG.md` e `docs/PROCESSO.md` §7 | registro e lições |

Ficam intocados: `src/`, `app.py`, `db/`, `registry/`, `.claude/settings.json` e `CLAUDE.md`.

## 5. Passos

Os passos 1 e 2 são feitos em sequência, um commit cada. Isso evita montar versões intermediárias à mão.

### Passo 0: plano e decisões
Commit 1: `docs: plano do guarda-r1-r3 e decisoes do responsavel`.

### Passo 1: R1 por lista de liberação (D1)
- **Código:** `git_que_grava` vira `git_nao_liberado`, com as listas do D1.
- **Testes:**
  - todos os comandos liberados de hoje continuam liberados;
  - os casos bloqueados de hoje continuam bloqueados;
  - novos bloqueados: alias (`git ci -m x`), `git worktree list`, `git notes list`, `git grep --no-index X`, `git diff --no-index a b`, `git remote add`, `git reflog expire`;
  - novos liberados: `cat-file`, `ls-tree`, `describe`, `merge-base`, `check-ignore`, `check-attr`, `remote show`, `reflog`, `symbolic-ref HEAD`, `hash-object a.py`.
- **Controle** (`controle_mutacao`): uma mutação por regra.
  - `status` fora da lista;
  - subcomando desconhecido passa a ser liberado;
  - `--no-index` no grep e no diff;
  - as condicionais de `remote`, `reflog`, `symbolic-ref` e `hash-object`.

  Todas devem dar DETECTADA.

Commit 2: `fix(tools): guarda com lista de liberacao do git (R1)`.

### Passo 2: R3 fora de `tests/` (D2)
- **Testes:**
  - `src/conftest.py` com a forma `environ[...] = '1'`: bloqueado;
  - `tools/x.py` com a forma `setenv(...)`: bloqueado;
  - `docs/x.md` com o mesmo texto: liberado;
  - `.env` fictício em `tests/`: liberado.
- **Controle:** mutação que volta a restringir a `tests/` e mutação que tira a exceção da documentação.

Commit 3: `fix(tools): guarda aplica o R3 fora de tests/, salvo documentacao`.

### Passo 3: grep 3.5 em `'*.py'` (D3)
- **Mudança:** o pathspec muda no script e na linha do §5.
- **Controle:** mutação do pathspec no script derruba o teste de igualdade.

Commit 4: `fix(tools): grep 3.5 do PROCESSO secao 5 varre todo .py`.

### Conferência (entre os passos 3 e 4)
Antes dos commits 2 a 4, um `seguranca` novo, com effort `high` e já sob o guarda, confere o D1 a D3 lendo o código. Experimento bloqueado pelo guarda vem descrito, e a sessão principal o roda (L33). Saída: `conferencia_r1_r3.md`.

### Passo 4: textos
- **§3 do PROCESSO:**
  - R1 = git fora da lista de liberação;
  - R3 = formas do grep 3.5 em qualquer arquivo de código.
- **Corpos dos 3 agentes:** "git fora da lista de leitura" no lugar de "git que grava".

Commit 5: `docs: guarda com lista de liberacao e R3 fora de tests no PROCESSO e nos agentes`.

### Passo 5: verificação, registro e lições
1. **Verificação pelo `verificador`.** Roda `verificacao_padrao` com o rótulo `final` (esperado: 552 + N passed e 16 skipped) e valida o YAML.
2. **Registro.** Linha no GOVERNANCA_LOG.
3. **Lições.** Lições novas no §7, se houver.

Commit 6: `docs: registra guarda-r1-r3 no GOVERNANCA_LOG`.

## 6. Verificação
- **Testes:** `tests/test_guarda_agentes.py` e `tests/test_verificacao_padrao.py` passam.
- **Controles:** todas as mutações dão DETECTADA, e o m0 passa.
- **Suíte e greps:** `verificacao_padrao` com o rótulo `final` dá código 0. O grep 3.5 sobre `'*.py'` não acha nenhuma linha.
- **Sonda ao vivo:** uma chamada curta do `verificador` com `git cat-file -t HEAD`, que deve passar, e `git ci`, que deve ser bloqueado.

## 7. GOVERNANCA_LOG (linha prevista)
Commits 1 a 5:
- R1 por lista de liberação e R3 fora de `tests/` (salvo documentação);
- grep 3.5 em `'*.py'`;
- N testes novos;
- controles;
- conferência do `seguranca`;
- pytest;
- sonda ao vivo;
- residuais aceitos pelo responsável.

Status: aguardando revisão.

## 8. Fora de escopo
- Hooks na sessão principal (`.claude/settings.json`).
- Os residuais aceitos no item 3 do Contexto.
