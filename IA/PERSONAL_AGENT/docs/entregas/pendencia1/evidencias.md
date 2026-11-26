# Pendência 1: origem da tag `ref/item1-v1-nao-aceito` e da remoção dos branches

Tarefa somente leitura pedida pelo gerenciador (CLAUDE APP) em 2026-11-18. Executor: Claude Code, sessão principal `21c92eb3`, claude-opus-5-5 (1ª mensagem às 23:10:09). Nada foi alterado no `.git`: sem commit, tag, branch, reset, gc, prune, push ou mudança de ref. Único arquivo gravado no repositório: este (não rastreado; não commitar). O local `docs/_tmp/` segue o pedido; o `CLAUDE.md` prevê `docs/entregas/<tarefa>/` para saída longa de tarefa de leitura.

Horários em -03:00 (fuso do Windows: E. South America Standard Time), todos de 2026-11-18 salvo indicação. Comandos git rodados na raiz do repositório (`Workspace/`).

**Classes.** COMPROVADO: lido diretamente (objeto git, metadado de arquivo, linha de histórico ou de transcrição). FORTE CORRELAÇÃO: inferência em que fontes independentes concordam em tempo e ordem. CONTEXTUAL: fato verdadeiro em torno da questão que não prova autoria. HIPÓTESE: explicação plausível, não verificada.

## 1. Resposta

A tag foi criada às **23:06:14.82**, e os branches foram removidos entre **23:06:14.9 e 23:07:18.5**. Os comandos foram colados num **console PowerShell interativo** da conta Windows `<usuario>` e estão no histórico do PSReadLine, linhas 327 a 345. Isso aconteceu cerca de 5 minutos depois do commit do P2 (`3f2db49`, 23:01:31). Não foi sessão do Claude Code nem o Codex. Os mesmos comandos também removeram `docs/protocolo` e `´` e descartaram o stash. Nada se perdeu.

| # | Conclusão | Classe | Base |
|---|---|---|---|
| C1 | `ref/item1-v1-nao-aceito` é tag **lightweight**: o ref aponta direto para o commit `8fd66781…` (`cat-file -t` = `commit`), sem objeto tag. Não há tagger nem data de tag. O `creatordate` (00:03:44) é a data do commit do stash, não da tag. | COMPROVADO | §3.1, §3.2 |
| C2 | Criada às **23:06:14.82**: CreationTime = LastWriteTime do ref solto `.git/refs/tags/ref/item1-v1-nao-aceito`. Não existe `.git/packed-refs`, então esse arquivo é a única cópia do ref. | COMPROVADO (metadado NTFS) | §3.5 |
| C3 | Os comandos de criação da tag e de remoção dos branches estão literais no histórico do **PowerShell interativo** (PSReadLine, `ConsoleHost_history.txt`) da conta `<usuario>`. Aparecem em dois blocos multilinha idênticos (L327–333 e L339–345) e em três comandos avulsos entre eles (L334, L335, L337). | COMPROVADO | §4.1 |
| C4 | Quem executou: o **responsável, à mão**, colando blocos no console. Só entrada interativa (teclado ou colagem) vai para o PSReadLine. O mesmo usuário escrevia na sessão `6a0fdc5e` às 23:05:03 e 23:05:48. Não há rastro de automação de tela na janela. O histórico prova a conta e o console, não a pessoa. | FORTE CORRELAÇÃO | §4.1, §4.3, §4.4 |
| C5 | **Nenhuma sessão do Claude Code** executou esses comandos. Nenhuma transcrição do projeto tem `git tag`, `branch -d/-D` ou `stash drop` executados na janela. A `442f9f24` terminou às 23:02:18. A `6a0fdc5e` só leu arquivos e rodou scripts de análise e `git log`. Esta sessão só recebeu a 1ª mensagem às 23:10:09. As ferramentas do Claude Code não gravam no PSReadLine (controle em §4.5). | FORTE CORRELAÇÃO | §4.3, §4.5 |
| C6 | **O Codex não participou.** Sua última escrita em `refs/codex` foi às 10:44:15.99, 12 h 22 min antes da tag. As 3 `refs/codex` são idênticas nos bundles das 20:26 e das 23:08. Nenhum arquivo do `~/.codex` foi gravado entre 23:05:30 e 23:08:30, e o último log de sessão do Codex é das 10:38:49. | FORTE CORRELAÇÃO | §2, §4.2, §4.4 |
| C7 | O app do Codex foi aberto por volta das 22:00 (estado global às 22:01:45, `config.toml` às 22:10:14), sem sessão nem ref neste repositório depois disso. Gemini: nada gravado na janela. | CONTEXTUAL | §4.4 |
| C8 | Os 5 branches (`revert/aa9a0a5`, `isolamento-env`, `item1/reaplicado`, `docs/protocolo`, `´`) e o `refs/stash` existiam às 20:26:28 e não existiam às 23:08:22. A tag já existia às 23:08:22. | COMPROVADO | §4.2 |
| C9 | Os 3 branches da pendência foram removidos entre 23:06:14.9 e 23:07:18.5. A remoção de `isolamento-env` fica mascarada pela de `´` às 23:07:18.48. Depois vieram `docs/protocolo` (23:07:14–16), `´` (23:07:18.48) e o `stash drop` (23:07:18.54). O pager do git, que só abre com TTY, encerrou às 23:07:18.71. | FORTE CORRELAÇÃO | §2, §3.5 |
| C10 | A ordem no disco é a do bloco colado (tag → rev-parse → `branch -d` ×3 → `branch -D docs/protocolo` → `branch -d '´'` → `stash drop` → listagem). O plano punha o `stash drop` logo depois da tag (`registro_pos_merge.md:94-96`). Tag e início do `branch -d` distam 0,1 s, rápido demais para digitar, então saíram do mesmo bloco multilinha, provavelmente o 1º. | FORTE CORRELAÇÃO | §2, §4.1 |
| C11 | Ficam sem explicação comprovada: a repetição do bloco, os intervalos de segundos dentro da remoção de um mesmo branch (ex.: `revert`, reflog às 23:06:14.9 e ref às 23:06:58.7) e qual entrada fez o quê. Candidatos: (a) o Git for Windows não conseguiu apagar os diretórios vazios, que continuam lá, e, com TTY, perguntou "Should I try again? (y/n)"; (b) latência de E/S do `.git` dentro do OneDrive. A cauda (`docs/protocolo`, `´`, stash) é compatível com o 2º bloco, se o 1º parou antes dela. | HIPÓTESE | §3.4, §5 |
| C12 | O bloco usa aspas do PowerShell (`"stash@{0}"`) e acrescenta o `rev-parse` dos dois `ref/*` e a listagem final; o plano está em sintaxe Bash. Foi adaptado antes da colagem, provavelmente pelo gerenciador ou pelo responsável. | HIPÓTESE | §4.1 |
| C13 | Nada se perdeu. As pontas removidas estão em `main` (`a89791a`, `673ceb1`, `8810b6e`, `54f813c`) ou têm tag (`27d135d` → `ref/docs-protocolo-27d135d`; `8fd6678` → `ref/item1-v1-nao-aceito`). `git fsck --unreachable` não acusa commit inalcançável, logo nenhuma outra entrada de stash foi descartada. | COMPROVADO | §4.6 |
| C14 | A limpeza não moveu HEAD: entre o P2 (23:01:31) e a coleta (23:12) o reflog de HEAD não tem entrada. A seguinte é um commit de outra tarefa às 23:26:20 (`486dd9b`, alheio à pendência). No intervalo do lote (P0 às 22:17:43, P2 às 23:01:31) só há commits, nenhum checkout ou reset. O último checkout foi às 20:10:36. | COMPROVADO | §3.3 |
| C15 | Autorização: o plano previa a limpeza "depois do aceite deste plano executado, com autorização explícita" (`registro_pos_merge.md:93`). A revisão 4, commitada no P2, ainda diz "Fora de commit: pendente". A execução veio cerca de 5 min depois. O GOVERNANCA_LOG não a registra; só a lista como pendente (`GOVERNANCA_LOG.md:141`, status "aguardando aceite"). | CONTEXTUAL | §5 |
| C16 | O mesmo console fez backups antes e depois: `personal_agent_8810b6e.bundle` (L315, 20:26:28) e `personal_agent_3f2db49.bundle` (L348, 23:08:22), em `Downloads`, além de `git fsck --no-dangling` (L346). | COMPROVADO | §4.1, §4.2 |

## 2. Linha do tempo e correlação com `refs/codex/*`

| Horário | Evento | Fonte | Classe |
|---|---|---|---|
| 2026-11-15 22:21:16.53 | checkpoint Codex `f0a4b001…/1794792076526` (restante) | epoch em ms no nome; mtime do ref 48 ms depois | COMPROVADO |
| 2026-11-16 01:55:20.57 | checkpoint Codex `b0920ad9…/1794804920574` (restante) | idem, 55 ms | COMPROVADO |
| 00:03:44 | stash `8fd6678` criado ("On main: item1 v1 sobre aa9a0a5 (nao aceito; referencia)") | commit | COMPROVADO |
| 00:03:53 | `revert/aa9a0a5` criado a partir de `19f19f2` | reflog de HEAD; CreationTime de `refs/heads/revert/` | COMPROVADO |
| 00:04:44 | `item1/reaplicado` criado em `a89791a` | idem, `refs/heads/item1/` | COMPROVADO |
| 00:54:25 | `docs/protocolo` (`27d135d`) | CreationTime de `refs/heads/docs/`; commit | COMPROVADO |
| 10:38:49 | última sessão do Codex (rollout) | `~/.codex/sessions/2026/11/18/` | COMPROVADO |
| 10:43:10.37 | checkpoint Codex `740cdb7d…/1795009390373` (último restante) | nome; mtime 51 ms depois | COMPROVADO |
| 10:44:15.99 | última mudança em `.git/refs/codex/` | mtime de diretório | COMPROVADO |
| 11:37:16 | `isolamento-env` criado em `673ceb1` | reflog | COMPROVADO |
| 20:10:36–37 | tag `pre-merge-isolamento`, `switch main`, FF | reflog; ref da tag | COMPROVADO |
| 20:26:28 | bundle `8810b6e` com os 5 branches e o stash | bundle; PSReadLine L315 | COMPROVADO |
| ~22:00–22:10 | app do Codex aberto | `~/.codex` (estado, config) | CONTEXTUAL |
| 22:17:43 | P0 e tag `ref/docs-protocolo-27d135d` | reflog; ref da tag | COMPROVADO |
| 23:01:31 | commit do P2 `3f2db49` (plano rev. 4: "Fora de commit: pendente") | reflog | COMPROVADO |
| 23:02:18 | último evento da sessão `442f9f24` | transcrição | COMPROVADO |
| 23:05:03–23:05:48 | usuário escreve na sessão `6a0fdc5e` | transcrição | COMPROVADO |
| 23:06:04.71 | processo desta sessão (`21c92eb3`, pid 4084) inicia, ocioso até 23:10:09 | `~/.claude/sessions/4084.json` | COMPROVADO |
| **23:06:14.82** | **tag `ref/item1-v1-nao-aceito` criada** | CreationTime = LastWriteTime do ref solto | COMPROVADO |
| 23:06:14.92 | reflog de `revert/aa9a0a5` apagado (+0,1 s) | LastWriteTime de `logs/refs/heads/revert/` (vazio) | FORTE CORRELAÇÃO |
| 23:06:22.24 | reflog de `item1/reaplicado` apagado | `logs/refs/heads/item1/` (vazio) | FORTE CORRELAÇÃO |
| 23:06:58.72 | ref `revert/aa9a0a5` (ou seu `.lock`) apagado | `refs/heads/revert/` (vazio) | FORTE CORRELAÇÃO |
| 23:06:59.73 | ref `item1/reaplicado` (ou seu `.lock`) apagado | `refs/heads/item1/` (vazio) | FORTE CORRELAÇÃO |
| 23:07:03.64 | `.git/config` recriado | CreationTime de `config`; causa (seção `[branch]` removida pelo `branch -d`): HIPÓTESE | COMPROVADO |
| 23:07:14.40 / 23:07:16.80 | reflog / ref de `docs/protocolo` apagados | `logs/refs/heads/docs/`, `refs/heads/docs/` (vazios) | FORTE CORRELAÇÃO |
| 23:07:18.4755 | `´` apagado (ref e reflog no mesmo instante) | LastWriteTime de `refs/heads/` = de `logs/refs/heads/` | FORTE CORRELAÇÃO |
| 23:07:18.4775 | `.git/config` gravado (+2 ms) | LastWriteTime de `config` | FORTE CORRELAÇÃO |
| 23:07:18.545 | `stash drop`: `refs/stash` e seu reflog removidos | `.git/refs/` e `.git/logs/refs/`, onde só o stash fica solto | FORTE CORRELAÇÃO |
| 23:07:18.709 | `less` (pager do git, só com TTY) encerra: `git branch --list; git stash list` | CreationTime de `~/.lesshst` | FORTE CORRELAÇÃO |
| 23:08:21.520 | último comando aceito no PowerShell (L346–349: fsck, for-each-ref, bundle) | LastWriteTime do histórico PSReadLine | COMPROVADO |
| 23:08:22.295 | bundle `3f2db49`: só `main` e as 3 tags | bundle | COMPROVADO |
| 23:10:09 | 1ª mensagem desta sessão (pedido da pendência 1) | transcrição | COMPROVADO |
| 23:26:20 | commit `486dd9b` (`docs: plano da revisao-subagentes-v2`), de outra tarefa, alheio à pendência | reflog; transcrição da `6a0fdc5e` | COMPROVADO (commit); autoria: FORTE CORRELAÇÃO |

**Correlação com `refs/codex/*`: nenhuma** (FORTE CORRELAÇÃO para "Codex não participou"). As 3 refs restantes têm no nome o epoch em ms da criação, com 48 a 55 ms de diferença para o mtime do arquivo. São refs de checkpoint (`turn-diffs/checkpoints`) que apontam para objetos tree. A mais recente é das 10:43:10; a última mudança na árvore `refs/codex` é das 10:44:15.99, 12 h 22 min antes da tag. Os diretórios vazios de checkpoints já apagados vão de 2026-10-13 19:06 a 2026-11-18 10:40. Nada em `refs/codex` mudou entre os bundles das 20:26 e das 23:08.

## 3. Coleta pedida

### 3.1 Item 1: tipo da tag

`git cat-file -t ref/item1-v1-nao-aceito` → `commit`; o ref e o ref descascado (`^{}`) dão `8fd66781f66bf1e2913b4f64233f43219c53a5f1`. Logo é **lightweight**: sem objeto tag, sem tagger, sem data de tag (COMPROVADO). O alvo é o antigo `stash@{0}`: commit `8fd6678`, "On main: item1 v1 sobre aa9a0a5 (nao aceito; referencia)", autor e committer `frederichmp` às 00:03:44. Tem 3 pais: `19f19f2` (HEAD), `6d5418f` (índice) e `e4f8d4b` (não rastreados). Confere com o F7 do plano.

### 3.2 Item 2: `for-each-ref`

Saída literal no Anexo A.2. As 3 tags (`pre-merge-isolamento`, `ref/docs-protocolo-27d135d`, `ref/item1-v1-nao-aceito`) têm `taggername` e `taggerdate` vazios, ou seja, as 3 são lightweight. As 3 `refs/codex/turn-diffs/checkpoints/…` são do tipo `tree`. Na rodada ampliada, o `creatordate` das tags é a data do commit-alvo (00:03:44 para `8fd6678`), não a data de criação da tag.

### 3.3 Item 3: reflog de HEAD

As 80 linhas estão no Anexo A.3.

- **Intervalo do lote** (P0 às 22:17:43 → P2 às 23:01:31): 7 entradas, todas `commit` ou `commit (cherry-pick)`. Nenhum checkout ou reset (COMPROVADO).
- **Depois de 23:01:31:** nenhuma entrada até a coleta (23:12). Tag, `branch -d/-D` e `stash drop` não gravam no reflog de HEAD, e HEAD não se moveu na limpeza (COMPROVADO). A recaptura do Anexo A.3 tem uma entrada a mais no topo: `486dd9b` às 23:26:20, commit de outra tarefa feito durante esta, alheio à pendência (§5).
- **Último checkout:** 20:10:36 (`isolamento-env` → `main`), seguido do FF às 20:10:37.

| Branch | Criação | Ponta na remoção (bundle 20:26) | Contido em `main` |
|---|---|---|---|
| `revert/aa9a0a5` | 00:03:53, `checkout: moving from main to revert/aa9a0a5` | `a89791a` | sim |
| `item1/reaplicado` | 00:04:44, `moving from revert/aa9a0a5 to item1/reaplicado` | `673ceb1` | sim |
| `isolamento-env` | 11:37:16, `moving from item1/reaplicado to isolamento-env` | `8810b6e` | sim |
| `docs/protocolo` | sem entrada no reflog de HEAD; diretório `refs/heads/docs/` criado às 00:54:25.39 | `27d135d` | não; preservado pela tag `ref/docs-protocolo-27d135d` |
| `´` | 2026-10-07 | `54f813c` | sim |

### 3.4 Item 4: `.git/logs/refs/heads` e `.git/logs/refs/tags`

`.git/logs/refs/heads` contém `docs`, `item1`, `main` e `revert`. `.git/logs/refs/tags` não existe (`ls` sai com código 2).

- **Sem reflog de tag** (COMPROVADO): com `core.logAllRefUpdates=true` o git só mantém reflog de `refs/heads`, `refs/remotes`, `refs/notes` e HEAD. A criação da tag não deixa rastro em reflog.
- **Diretórios vazios** (COMPROVADO): `docs/`, `item1/` e `revert/` estão vazios em `.git/refs/heads/` e em `.git/logs/refs/heads/`. Ref e reflog foram apagados, e os diretórios ficaram. O horário da última mudança de cada um marca a remoção (§3.5).
- **Padrão do ambiente** (CONTEXTUAL): `.git/refs/codex/` também tem vários diretórios vazios de checkpoints apagados pelo Codex. O padrão vem do ambiente (Git for Windows com `.git` dentro do OneDrive), não da ferramenta.

### 3.5 Item 5: horários de arquivo (NTFS)

C = CreationTime; W = LastWriteTime. O LastAccess não é usado, porque o NTFS só o atualiza se o valor anterior tiver mais de 1 h. A saída bruta está no Anexo A.5.

| Caminho | C | W | Leitura |
|---|---|---|---|
| `.git/refs/tags/ref/item1-v1-nao-aceito` | 23:06:14.8216990 | 23:06:14.8216990 | ref solto da tag (41 bytes): momento da criação |
| `.git/refs/tags/ref/` | 22:17:43.8794097 | 23:06:14.8257282 | criado com `ref/docs-protocolo-27d135d`; última mudança = rename do `.lock` da tag nova |
| `.git/packed-refs` | — | — | **não existe**: nenhum ref empacotado e nenhuma reescrita na remoção |
| `.git/config` | 23:07:03.6415910 | 23:07:18.4775391 | `branch -d/-D` reescreve o config (seção `[branch "<nome>"]`); W 2 ms depois da remoção de `´` |
| `.git/logs/refs/heads/revert/` (vazio) | 00:03:53.0803445 | 23:06:14.9174496 | reflog de `revert/aa9a0a5` apagado |
| `.git/logs/refs/heads/item1/` (vazio) | 00:04:44.4065246 | 23:06:22.2401828 | reflog de `item1/reaplicado` apagado |
| `.git/refs/heads/revert/` (vazio) | 00:03:53.0803445 | 23:06:58.7191401 | ref (ou `.lock`) de `revert/aa9a0a5` apagado |
| `.git/refs/heads/item1/` (vazio) | 00:04:44.4065246 | 23:06:59.7339765 | ref (ou `.lock`) de `item1/reaplicado` apagado |
| `.git/logs/refs/heads/docs/` (vazio) | 00:54:25.3971820 | 23:07:14.4032012 | reflog de `docs/protocolo` apagado |
| `.git/refs/heads/docs/` (vazio) | 00:54:25.3898337 | 23:07:16.8007158 | ref de `docs/protocolo` apagado |
| `.git/refs/heads/` e `.git/logs/refs/heads/` | 2026-10-07 | 23:07:18.4755278 (os dois, na 1ª coleta) | última mudança de nível 1: `´` (`isolamento-env` fica mascarado). Na recaptura, `refs/heads/` mostra 23:26:20.54, efeito do `main.lock` do commit `486dd9b` |
| `.git/logs/refs/` | 2026-10-07 | 23:07:18.5449186 | `logs/refs/stash` removido |
| `.git/refs/` | 2026-10-07 | 23:07:18.5459151 | `refs/stash` removido |
| `.git/refs/codex/…` (mais recente) | — | 10:44:15.9859983 | última atividade do Codex no repositório |
| `~/.lesshst` | 23:07:18.7092834 | 23:07:18.7102922 | `less` encerrou (42 bytes, só histórico do `less`) |
| `PSReadLine\ConsoleHost_history.txt` | 2026-10-07 12:29:16 | 23:08:21.520 | último comando aceito = L346–349 |
| `Downloads\personal_agent_8810b6e.bundle` | 20:26:28.600 | 20:26:29.890 | L315 |
| `Downloads\personal_agent_3f2db49.bundle` | 23:08:22.295 | 23:08:23.358 | L348 |

## 4. Coleta complementar (fora da lista; só leitura)

### 4.1 Histórico do PowerShell (PSReadLine)

Arquivo `%APPDATA%\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt`: 349 linhas, última gravação às 23:08:21.520. O PSReadLine grava um item por comando aceito no console interativo. Um item multilinha sai como várias linhas terminadas em crase, a marca de continuação; uma crase digitada no texto sairia dobrada, e nenhuma linha tem crase dobrada. O histórico não guarda horário por item. As horas vêm do último item (mtime do arquivo) e dos efeitos no `.git` (§2). O texto exato das linhas 314–349 está no Anexo A.6, só com as linhas de git; as demais foram omitidas.

| Item | Linhas | Conteúdo |
|---|---|---|
| a | 315 | `git -C "…\Workspace\" bundle create '…\Downloads\personal_agent_8810b6e.bundle' --all` (arquivo das 20:26:28) |
| b | 316 | `git bundle verify` do mesmo arquivo |
| c | 317–322 | consultas: `log -1` de `54f813c`; `merge-base --is-ancestor` de `54f813c`, `docs/protocolo` e `revert/aa9a0a5`; `stash list`; `stash show` |
| d | 323–326 | `stash show --name-only "stash@{0}"`; `log --oneline main..docs/protocolo`; `diff --stat main...docs/protocolo`; `ls-tree -r --name-only main \| Select-String PROTOCOLO` |
| **e: bloco 1** | **327–333** | `git tag ref/item1-v1-nao-aceito "stash@{0}"` → `git rev-parse ref/item1-v1-nao-aceito ref/docs-protocolo-27d135d` → `git branch -d revert/aa9a0a5 isolamento-env item1/reaplicado` → `git branch -D docs/protocolo` → `git branch -d '´'` → `git stash drop "stash@{0}"` → `git branch --list; git stash list` |
| f | 334 | `git tag ref/item1-v1-nao-aceito "stash@{0}"` |
| g | 335–336 | `git rev-parse ref/item1-v1-nao-aceito ref/docs-protocolo-27d135d` e uma linha vazia |
| h | 337–338 | `git branch -d revert/aa9a0a5 isolamento-env item1/reaplicado` e uma linha vazia |
| **i: bloco 2** | **339–345** | idêntico ao bloco 1 |
| j | 346–349 | `git fsck --no-dangling` → `git for-each-ref --format="%(refname) %(objectname:short)"` → `git bundle create '…\Downloads\personal_agent_3f2db49.bundle' --all` → `git bundle verify` |

Pontos de leitura:

- Só entrada interativa vai para esse arquivo. O `pwsh` não interativo usado pelas ferramentas do Claude Code não carrega o PSReadLine (controle em §4.5).
- O bloco difere do plano em três pontos: aspas do PowerShell em `"stash@{0}"`; `stash drop` no fim e não logo após a tag; `branch -D docs/protocolo` antes de `branch -d '´'`. Os efeitos no disco seguem o bloco (C10).
- O comando dos 3 branches da pendência aparece 3 vezes (L329, L337, L341). Uma vez removidos, as repetições falham sem efeito; qual delas removeu o quê é HIPÓTESE (C11).

### 4.2 Bundles de backup (`git bundle list-heads`)

| Ref | `8810b6e.bundle` (20:26:28) | `3f2db49.bundle` (23:08:22) |
|---|---|---|
| `refs/heads/main` | `8810b6e` | `3f2db49` |
| `refs/heads/revert/aa9a0a5` | `a89791a` | — |
| `refs/heads/isolamento-env` | `8810b6e` | — |
| `refs/heads/item1/reaplicado` | `673ceb1` | — |
| `refs/heads/docs/protocolo` | `27d135d` | — |
| `refs/heads/´` | `54f813c` | — |
| `refs/stash` | `8fd6678` | — |
| `refs/tags/pre-merge-isolamento` | `19f19f2` | `19f19f2` |
| `refs/tags/ref/docs-protocolo-27d135d` | — (criada às 22:17) | `27d135d` |
| `refs/tags/ref/item1-v1-nao-aceito` | — | `8fd6678` |
| `refs/codex/turn-diffs/checkpoints/…` (3) | `4124d96`, `aac0d00`, `154f07d` | iguais |
| `refs/remotes/origin/HEAD`, `main` | `ffd9cbc` | `ffd9cbc` |

Saída bruta no Anexo A.7.

### 4.3 Transcrições do Claude Code

O diretório `~/.claude/projects/…-Workspace-IA-PERSONAL-AGENT/` foi varrido em busca de `item1-v1-nao-aceito`, `git tag`, `branch -d/-D`, `stash drop` e `update-ref -d`, e de todos os eventos entre 23:04:30 e 23:09:00. O script ficou no scratchpad, fora do repositório. Todas as sessões são `entrypoint: claude-vscode`.

| Sessão | Processo iniciado | Eventos | Na janela 23:06:14–23:07:19 |
|---|---|---|---|
| `442f9f24` (pid 7732) | 21:43:49 | 21:43:57 → 23:02:18 | encerrada antes; nenhuma execução dos comandos, só menções no plano e no log e consultas `git tag -l` |
| `6a0fdc5e` (pid 15976) | 22:57:23 | 23:01:26 → 23:15:17 | ativa: Glob, Read, Write no próprio scratchpad, PowerShell com `Get-ChildItem`, `python -I` de análise de transcrições e `git log`; nenhum `git tag`, `branch` ou `stash` |
| `21c92eb3` (esta, pid 4084) | 23:06:04.71 | a partir de 23:10:09 | processo aberto, sem eventos |

O último arquivo de subagente gravado é das 22:27:11 (`442f9f24/subagents/agent-aadb4291…`).

### 4.4 Codex, Gemini e app do Claude na janela 23:05:30–23:08:30

A varredura listou nome e horário dos arquivos gravados na janela, sem ler conteúdo.

- **`~/.codex`:** nenhum arquivo. A última sessão (rollout) é das 10:38:49. A última atividade fora da janela foi entre 22:00 e 22:10 (`.codex-global-state.json` às 22:01:45, `config.toml` às 22:10:14).
- **`~/.gemini`:** nenhum arquivo.
- **App do Claude (`%LOCALAPPDATA%\Claude-Data\…`):**
  - Local Storage às 23:05:32.
  - 4 `SKILL.md` do skills-plugin entre 23:06:06.94 e 23:06:06.96, na sincronização que acompanha o início do processo do Claude Code às 23:06:04.
  - `DIPS` (base interna do Chromium) às 23:07:11 e 23:08:12.
  - Nenhum log de agente local nem de computer use.
- **`~/.claude`:**
  - `sessions/4084.*.key` às 23:06:04.5 (esta sessão).
  - Arquivos de plugins às 23:06:04.9 e 23:06:12.4.
  - `file-history/6a0fdc5e…` às 23:07:08 e 23:07:39 (os Write da `6a0fdc5e` no scratchpad dela).
- **`~` (nível 1):**
  - `.claude.json` às 23:06:04.8, início desta sessão.
  - `.lesshst` às 23:07:18.71.
  - `Downloads` às 23:08:23, bundle novo.

### 4.5 Controles negativos

Às 23:26:38, depois de dezenas de chamadas PowerShell e Bash desta sessão (com git), `ConsoleHost_history.txt` continuava com W=23:08:21.520 e `~/.lesshst` com W=23:07:18.710. As ferramentas do Claude Code não gravam no histórico do PSReadLine e não abrem pager, porque rodam sem TTY (COMPROVADO).

### 4.6 Integridade

- `git fsck --unreachable` saiu com código 0: **0 commits inalcançáveis**; há 15 blobs e 27 trees soltos, de origem não investigada e fora do escopo. Um stash descartado viraria commit inalcançável, então o único descartado foi `8fd6678`, hoje sob a tag (COMPROVADO).
- `merge-base --is-ancestor`: `a89791a`, `673ceb1`, `8810b6e` e `54f813c` estão em `main`. `27d135d` não está e é mantido pela tag `ref/docs-protocolo-27d135d` (COMPROVADO).
- `git stash list` está vazio (COMPROVADO).

## 5. Limites e próximos passos (nada disso foi executado)

- **O que não é recuperável daqui:** a saída do console (erros, perguntas "Should I try again? (y/n)", mensagens "Deleted branch") não fica gravada. Só o scrollback do terminal, se ainda estiver aberto, ou o relato do responsável confirmam a C11.
- **Identidade:** o histórico do PSReadLine prova a conta Windows e o console interativo, não a pessoa (C4).
- **Registro:** a execução não consta do GOVERNANCA_LOG; só aparece como pendente em `:141`, status "aguardando aceite". Registrar é gravação no repositório e exige tarefa com `/plan`. A decisão sobre a "autorização explícita" (C15) é do responsável.
- **Fora do escopo, vistos de passagem:**
  - `docs/protocolo` (`27d135d`, 00:54:25) foi criado sem entrada no reflog de HEAD desta worktree.
  - `FETCH_HEAD` foi regravado às 23:12:07 por um fetch sem mudança em `origin/main`, provavelmente o autofetch do VS Code (HIPÓTESE).
  - Os diretórios vazios em `.git/refs/heads/` e `.git/logs/refs/heads/` são inofensivos; removê-los seria alterar o `.git`.
- **Sessão concorrente** (autoria: FORTE CORRELAÇÃO, porque a transcrição da `6a0fdc5e` cita esses arquivos e os mtimes caem dentro da atividade dela). Durante esta tarefa, a sessão `6a0fdc5e` (revisão dos subagentes):
  - commitou `486dd9b` às 23:26:20;
  - entre 23:30 e 23:34, deixou modificados e não commitados `CLAUDE.md`, `docs/PROCESSO.md`, `docs/PROTOCOLO.md` e `.claude/agents/{mecanico,seguranca,verificador}.md`;
  - criou `tools/verificacao_padrao.py` e `tests/test_verificacao_padrao.py`.

  Esta tarefa gravou só `docs/_tmp/`.

## Anexo A. Saídas brutas

Recapturadas em 2026-11-18 23:34:50 -0300 com os mesmos comandos da coleta (raiz do git, `Workspace/`). Tags, `refs/codex` e o stash não mudaram desde a 1ª coleta (23:12). Já `main` avançou para `486dd9b` às 23:26:20 (`docs: plano da revisao-subagentes-v2`), commit de outra tarefa, alheio à pendência (§5). Por isso o A.3 tem uma entrada a mais no topo e, no A.5, `.git/refs/heads/` mostra 23:26:20. O corpo (§1 a §4) descreve a 1ª coleta.

### A.1 Item 1

```text
$ git cat-file -t ref/item1-v1-nao-aceito
commit
$ git rev-parse refs/tags/ref/item1-v1-nao-aceito "refs/tags/ref/item1-v1-nao-aceito^{}"
8fd66781f66bf1e2913b4f64233f43219c53a5f1
8fd66781f66bf1e2913b4f64233f43219c53a5f1
```

### A.2 Item 2

```text
$ git for-each-ref refs/tags refs/codex --format="%(refname) %(objecttype) %(taggername) %(taggerdate:iso) %(objectname:short)"
refs/codex/turn-diffs/checkpoints/740cdb7d8257ff07b1c6a0c407cd2e12/cfa80edf7cbe6d33fee360a0eb0b4b77/1795009390373/d5b5f4e2-a508-4aa2-b24c-251a1973795e tree   4124d96
refs/codex/turn-diffs/checkpoints/b0920ad9c28efeb4a565d887c154b502/d48b5e492154612d20b691e02222066b/1794804920574/5b1adbfa-74be-4111-8aa5-69aabae89057 tree   aac0d00
refs/codex/turn-diffs/checkpoints/f0a4b001261377557af06403686b9490/6cfa1da3bcbf475c6a9e511076647616/1794792076526/4ad7c644-96e1-4adb-9906-75c4dcdd03c5 tree   154f07d
refs/tags/pre-merge-isolamento commit   19f19f2
refs/tags/ref/docs-protocolo-27d135d commit   27d135d
refs/tags/ref/item1-v1-nao-aceito commit   8fd6678
```

### A.3 Item 3

```text
$ git reflog show HEAD --date=iso | head -80
486dd9b HEAD@{2026-11-18 23:26:20 -0300}: commit: docs: plano da revisao-subagentes-v2
3f2db49 HEAD@{2026-11-18 23:01:31 -0300}: commit: docs: registro pos-merge, aceite da fase 4 e licoes L21 a L23 (P2)
3ca8f98 HEAD@{2026-11-18 22:48:44 -0300}: commit: style: 2 linhas em branco antes do decorador do T2 (PEP 8) (S1)
66a15d7 HEAD@{2026-11-18 22:21:37 -0300}: commit: test: .env ausente preserva ORACLE_SANDBOX do shell, CLI e Web (T2)
e692788 HEAD@{2026-11-18 22:20:14 -0300}: commit: test: igualdade do bloco carga-env entre app.py e src/main.py (T1)
fa9e390 HEAD@{2026-11-18 22:18:45 -0300}: commit: chore: ignora *.sqlbkp no projeto (P3)
8cc3773 HEAD@{2026-11-18 22:18:30 -0300}: commit: docs: precedencia do PROCESSO.md (secao 3) sobre o PROTOCOLO.md e registro pos-merge (P1)
a3362f2 HEAD@{2026-11-18 22:17:43 -0300}: commit (cherry-pick): docs: protocolo curto de instrucao e resposta de subagentes
8810b6e HEAD@{2026-11-18 20:10:37 -0300}: merge isolamento-env: Fast-forward
19f19f2 HEAD@{2026-11-18 20:10:36 -0300}: checkout: moving from isolamento-env to main
8810b6e HEAD@{2026-11-18 19:16:42 -0300}: commit: docs: isolamento do .env, fase 4 (GOVERNANCA_LOG, licoes, decisao e verificacoes)
b293706 HEAD@{2026-11-18 19:14:36 -0300}: commit: test: D6.2 exercita executor e RAG; D6.4 confere autouse e escopo da guarda (isolamento .env fase 4, passo 4)
ede678a HEAD@{2026-11-18 19:05:32 -0300}: commit: fix: Chroma do rag_search sem leitura de cwd/.env (isolamento .env fase 4, passo 3, Achado 4)
f5692f0 HEAD@{2026-11-18 18:59:05 -0300}: commit: fix: carga unica do .env com nova tentativa so sem escrita (isolamento .env fase 4, passo 2, Achados 1 e 3)
216a6fd HEAD@{2026-11-18 16:02:15 -0300}: commit: test: protege leituras do .env nos testes antes da carga unica (isolamento .env fase 4, passo 1, Achados 2 e 5)
3ff2b79 HEAD@{2026-11-18 14:45:18 -0300}: commit: docs: material de revisao adversarial da fase 3 do isolamento do .env
b0ce169 HEAD@{2026-11-18 14:32:30 -0300}: commit: docs: isolamento do .env, fase 3 (GOVERNANCA_LOG, licoes e verificacoes)
cfd7890 HEAD@{2026-11-18 14:32:04 -0300}: commit: test: cobertura D6 e D3 da revisao Gemini (isolamento .env fase 3, passo 4)
427adfc HEAD@{2026-11-18 14:15:22 -0300}: commit: fix: avisos visiveis da carga do .env, so com nomes (isolamento .env fase 3, passo 3, B3/C3)
3cb6e03 HEAD@{2026-11-18 14:06:33 -0300}: commit: fix: destino do log de aprovacao resolvido em tempo de chamada (isolamento .env fase 3, passo 2, A3)
4aef0b4 HEAD@{2026-11-18 14:01:10 -0300}: commit: fix: carga do .env uma vez por processo com try/finally (isolamento .env fase 3, passo 1)
c97a90f HEAD@{2026-11-18 13:38:43 -0300}: commit: docs: plano da fase 3 do isolamento do .env, revisao Gemini e reproducao
ba598f0 HEAD@{2026-11-18 12:54:17 -0300}: commit: docs: registra processo de agentes no GOVERNANCA_LOG
3cc241b HEAD@{2026-11-18 12:53:55 -0300}: commit: docs: licao L12 e verificador trata caminho fora do previsto como falha
49ad795 HEAD@{2026-11-18 12:50:34 -0300}: commit: docs: processo de tarefa e delegacao e regras novas no CLAUDE.md
124e12c HEAD@{2026-11-18 12:47:41 -0300}: commit: chore(claude): agentes com contexto, limites e retorno padronizado
04f261f HEAD@{2026-11-18 12:46:44 -0300}: commit: docs: plano do processo de agentes e delegacao
11767be HEAD@{2026-11-18 12:18:22 -0300}: commit: docs: mensagem de abertura da revisao adversarial para o Gemini
6a53bbc HEAD@{2026-11-18 12:13:53 -0300}: commit: docs: registra rebase do plano 1.11-V2, material de revisao e teste do guard
350aee4 HEAD@{2026-11-18 12:13:36 -0300}: commit: test: caracteriza o guard de sessao de ORACLE_SANDBOX do conftest
a329324 HEAD@{2026-11-18 12:11:59 -0300}: commit: docs: material de revisao adversarial do isolamento do .env (fases 1 e 2)
2acba24 HEAD@{2026-11-18 12:11:03 -0300}: commit: docs: rebaseia o plano 1.11-V2 sobre d05577e
d05577e HEAD@{2026-11-18 12:05:04 -0300}: commit: docs: isolamento do .env, fase 2 (aceites, conferencia e residuais)
560a339 HEAD@{2026-11-18 12:03:34 -0300}: commit: fix: carga unica do .env nos pontos de entrada, sem ORACLE_SANDBOX do arquivo (isolamento .env, D1/D2)
bbe0e9b HEAD@{2026-11-18 11:48:08 -0300}: commit: docs: isolamento do .env, fase 1 (plano, decisao, verificacao, README)
0313e3b HEAD@{2026-11-18 11:44:51 -0300}: commit: fix: remove load_dotenv(override=True) em tempo de chamada (isolamento .env, D4)
c2b6a1d HEAD@{2026-11-18 11:41:57 -0300}: commit: refactor: remove load_dotenv de modulo em src/tools e src/config (isolamento .env, D3)
86d1eac HEAD@{2026-11-18 11:39:20 -0300}: commit: test: credenciais de sandbox so pelo conftest, com lista de permissao (isolamento .env, D5)
673ceb1 HEAD@{2026-11-18 11:37:16 -0300}: checkout: moving from item1/reaplicado to isolamento-env
673ceb1 HEAD@{2026-11-18 11:01:08 -0300}: commit: test: isola ambiente dos testes (B refeito, incidente 01:27)
bf394bc HEAD@{2026-11-18 10:15:10 -0300}: commit: docs: incidente de sandbox indevido (01:27 de 2026-11-18)
20bdc82 HEAD@{2026-11-18 10:14:30 -0300}: commit: revert: test de isolamento de env (incidente 01:26)
264000f HEAD@{2026-11-18 01:27:40 -0300}: commit: test: isola AGENTDBA_LOG_DIR do load_dotenv com override (B)
79806ba HEAD@{2026-11-18 01:04:14 -0300}: commit: docs: distingue O1 nos registros de falha
14917ea HEAD@{2026-11-18 00:59:25 -0300}: commit: test: env limpo em subprocessos (O2 do item 1)
ec647cf HEAD@{2026-11-18 00:58:42 -0300}: commit: fix(kill): retira O1 do item 1 (fica como item proprio)
c22a928 HEAD@{2026-11-18 00:35:35 -0300}: commit: feat(kill): item 1 - INTENCAO duravel antes do kill (fail-closed)
a89791a HEAD@{2026-11-18 00:04:44 -0300}: checkout: moving from revert/aa9a0a5 to item1/reaplicado
a89791a HEAD@{2026-11-18 00:04:28 -0300}: commit: docs: excecao do auditoria_oracle.log e limite do T8 (item 1)
4609954 HEAD@{2026-11-18 00:04:13 -0300}: commit: revert: aa9a0a5 Python v2 do item 6 (so codigo e testes)
19f19f2 HEAD@{2026-11-18 00:03:53 -0300}: checkout: moving from main to revert/aa9a0a5
19f19f2 HEAD@{2026-11-17 23:24:35 -0300}: commit: docs: decisao de seguranca do item 1 (INTENCAO antes do kill)
a1e8d30 HEAD@{2026-11-17 23:13:54 -0300}: commit: docs: regra de logon_time aceita pelo responsavel (item 6)
5b8066e HEAD@{2026-11-17 23:12:40 -0300}: commit: docs: origem e autoria do diff v2 do item 6 (aa9a0a5 nao aceito)
aa9a0a5 HEAD@{2026-11-17 22:57:24 -0300}: commit: feat(kill): Python v2 do item 6 - identidade no PKG (PENDENTE APROVAÇÃO)
67c01e8 HEAD@{2026-11-17 20:08:55 -0300}: commit: docs: parte 2 do item 6 bloqueada ate o Python v2
a371c41 HEAD@{2026-11-17 20:05:29 -0300}: commit: docs: parte 1 do item 6 concluida (estado final)
257304f HEAD@{2026-11-17 20:03:23 -0300}: commit: docs: registra execucao da parte 1 do item 6 (MODELO)
b89ff64 HEAD@{2026-11-17 19:59:37 -0300}: commit: docs: condicoes 2 e 4 do ensaio do item 6 atendidas
e2a7066 HEAD@{2026-11-17 19:59:11 -0300}: commit: docs(entregas): backup do PKG_OPS_KILL instalado (evidencia do item 6)
235ebcc HEAD@{2026-11-17 19:57:01 -0300}: commit: docs: autorizacao do ensaio do item 6 (condicionada ao backup)
d03f9b3 HEAD@{2026-11-17 19:54:11 -0300}: commit: docs: pre-requisitos do ensaio do item 6
15a0d38 HEAD@{2026-11-17 19:50:37 -0300}: commit: docs: decisao 4 aceita com risco (MODELO) no item 6
b2c20d4 HEAD@{2026-11-17 19:43:39 -0300}: commit: docs: decisao 4 reaberta na secao 6 do item 6
e3f69c6 HEAD@{2026-11-17 19:42:29 -0300}: commit: docs: condicao a do ensaio (tabelas do schema STARTUPADMIN)
15580e2 HEAD@{2026-11-17 19:41:18 -0300}: commit: docs: decisao 4 reaberta na 7.6 do item 6
818dc05 HEAD@{2026-11-17 19:39:22 -0300}: commit: docs: contas do executor e achado da conta MUT DBA no item 6
c0689b0 HEAD@{2026-11-17 19:33:13 -0300}: commit: docs: leitura de gv$session na 0.4 do item 6
e1ad467 HEAD@{2026-11-17 19:31:29 -0300}: commit: docs: redacao da leitura 0.4 com ressalva de origem
4a32c8a HEAD@{2026-11-17 19:29:57 -0300}: commit: docs: registra leitura 0.4 (gv$sql) do item 6
b58bf07 HEAD@{2026-11-17 19:23:08 -0300}: commit: docs: registra leitura 0.3 (jobs) do item 6
a165f60 HEAD@{2026-11-17 19:21:57 -0300}: commit: docs: registra leitura 0.1 (DBA_DEPENDENCIES) do item 6
d785fc6 HEAD@{2026-11-17 18:38:11 -0300}: commit: docs: 0.3 na situacao das leituras e hashes reais no registro de governanca
cd346f2 HEAD@{2026-11-17 18:37:22 -0300}: commit: docs: situacao das leituras 0.1 e 0.4 do item 6
e9a3b83 HEAD@{2026-11-17 18:36:41 -0300}: commit: docs: registra leitura 0.1 da parte 1
edea03a HEAD@{2026-11-17 18:35:33 -0300}: commit: docs(governanca): referencia da 7.3 aponta para 14f88e5
14f88e5 HEAD@{2026-11-17 18:33:23 -0300}: commit: docs(entregas): ordem das consultas opcionais do HS_ADMIN_SELECT_ROLE
aae2141 HEAD@{2026-11-17 18:31:54 -0300}: commit: docs(entregas): escopo do HS_ADMIN_SELECT_ROLE como expectativa documental
1229912 HEAD@{2026-11-17 18:30:58 -0300}: commit: docs(entregas): consultas usadas nas leituras da 7.3
f68aac5 HEAD@{2026-11-17 18:30:12 -0300}: commit: docs(entregas): encerra 7.3 do item 6
```

### A.4 Item 4

```text
$ ls .git/logs/refs/heads .git/logs/refs/tags
ls: cannot access '.git/logs/refs/tags': No such file or directory
.git/logs/refs/heads:
docs
item1
main
revert
(exit 2)
$ find .git/refs/heads .git/logs/refs/heads -mindepth 1 (conteúdo completo)
d .git/logs/refs/heads/docs
d .git/logs/refs/heads/item1
f .git/logs/refs/heads/main
d .git/logs/refs/heads/revert
d .git/refs/heads/docs
d .git/refs/heads/item1
f .git/refs/heads/main
d .git/refs/heads/revert
```

### A.5 Item 5 (PowerShell, Get-Item: CreationTime / LastWriteTime, hora local -03:00)

```text
.git/refs/tags/ref/item1-v1-nao-aceito                         C=2026-11-18 23:06:14.8216990  W=2026-11-18 23:06:14.8216990  (41 bytes)
.git/refs/tags/ref/                                            C=2026-11-18 22:17:43.8794097  W=2026-11-18 23:06:14.8257282  (dir, 2 entradas)
.git/packed-refs                                               AUSENTE
.git/config                                                    C=2026-11-18 23:07:03.6415910  W=2026-11-18 23:07:18.4775391  (336 bytes)
.git/refs/                                                     C=2026-10-07 12:37:15.9637091  W=2026-11-18 23:07:18.5459151  (dir, 4 entradas)
.git/refs/heads/                                               C=2026-10-07 12:37:15.9637091  W=2026-11-18 23:26:20.5443671  (dir, 4 entradas)
.git/refs/heads/revert/                                        C=2026-11-18 00:03:53.0803445  W=2026-11-18 23:06:58.7191401  (dir, 0 entradas)
.git/refs/heads/item1/                                         C=2026-11-18 00:04:44.4065246  W=2026-11-18 23:06:59.7339765  (dir, 0 entradas)
.git/refs/heads/docs/                                          C=2026-11-18 00:54:25.3898337  W=2026-11-18 23:07:16.8007158  (dir, 0 entradas)
.git/logs/refs/                                                C=2026-10-07 12:39:49.9525786  W=2026-11-18 23:07:18.5449186  (dir, 2 entradas)
.git/logs/refs/heads/                                          C=2026-10-07 12:39:49.9525786  W=2026-11-18 23:07:18.4755278  (dir, 4 entradas)
.git/logs/refs/heads/revert/                                   C=2026-11-18 00:03:53.0803445  W=2026-11-18 23:06:14.9174496  (dir, 0 entradas)
.git/logs/refs/heads/item1/                                    C=2026-11-18 00:04:44.4065246  W=2026-11-18 23:06:22.2401828  (dir, 0 entradas)
.git/logs/refs/heads/docs/                                     C=2026-11-18 00:54:25.3971820  W=2026-11-18 23:07:14.4032012  (dir, 0 entradas)
.git/refs/stash                                                AUSENTE
.git/logs/refs/stash                                           AUSENTE
.git/refs/codex/…/740cdb7d…/cfa80edf…/1795009390373/           C=2026-11-18 10:43:10.4244118  W=2026-11-18 10:44:15.9859983  (dir, 1 entradas)
~/.lesshst                                                     C=2026-11-18 23:07:18.7092834  W=2026-11-18 23:07:18.7102922  (42 bytes)
PSReadLine/ConsoleHost_history.txt                             C=2026-10-07 12:29:16.4636175  W=2026-11-18 23:08:21.5209099  (17008 bytes)
Downloads/personal_agent_8810b6e.bundle                        C=2026-11-18 20:26:28.6008586  W=2026-11-18 20:26:29.8900382  (7367893 bytes)
Downloads/personal_agent_3f2db49.bundle                        C=2026-11-18 23:08:22.2956985  W=2026-11-18 23:08:23.3584117  (7368359 bytes)
```

### A.6 PSReadLine, linhas 314 a 349

Só as linhas de git; as demais aparecem como `<omitida>`. A crase final é a marca de continuação do PSReadLine: a linha seguinte pertence ao mesmo item.

```text
 314: <omitida: não-git, 5 caracteres>
 315: git -C "C:\Users\<usuario>\OneDrive - <organizacao>\Workspace\"  bundle create 'C:\Users\<usuario>\Downloads\personal_agent_8810b6e.bundle' --all
 316: git bundle verify "C:\Users\<usuario>\Downloads\personal_agent_8810b6e.bundle"
 317: git log -1 --format="%h %ad %an %s" --date=iso 54f813c`
 318: git merge-base --is-ancestor 54f813c main; echo "ancestral_main=$LASTEXITCODE"`
 319: git stash list`
 320: git stash show --name-only stash@{0}`
 321: git merge-base --is-ancestor docs/protocolo main; echo "protocolo_em_main=$LASTEXITCODE"`
 322: git merge-base --is-ancestor revert/aa9a0a5 main; echo "revert_em_main=$LASTEXITCODE"
 323: git stash show --name-only "stash@{0}"`
 324: git log --oneline main..docs/protocolo`
 325: git diff --stat main...docs/protocolo`
 326: git ls-tree -r --name-only main | Select-String PROTOCOLO
 327: git tag ref/item1-v1-nao-aceito "stash@{0}"`
 328: git rev-parse ref/item1-v1-nao-aceito ref/docs-protocolo-27d135d`
 329: git branch -d revert/aa9a0a5 isolamento-env item1/reaplicado`
 330: git branch -D docs/protocolo`
 331: git branch -d '´'`
 332: git stash drop "stash@{0}"`
 333: git branch --list; git stash list
 334: git tag ref/item1-v1-nao-aceito "stash@{0}"
 335: git rev-parse ref/item1-v1-nao-aceito ref/docs-protocolo-27d135d`
 336: (vazia)
 337: git branch -d revert/aa9a0a5 isolamento-env item1/reaplicado`
 338: (vazia)
 339: git tag ref/item1-v1-nao-aceito "stash@{0}"`
 340: git rev-parse ref/item1-v1-nao-aceito ref/docs-protocolo-27d135d`
 341: git branch -d revert/aa9a0a5 isolamento-env item1/reaplicado`
 342: git branch -D docs/protocolo`
 343: git branch -d '´'`
 344: git stash drop "stash@{0}"`
 345: git branch --list; git stash list
 346: git fsck --no-dangling`
 347: git for-each-ref --format="%(refname) %(objectname:short)"`
 348: git bundle create 'C:\Users\<usuario>\Downloads\personal_agent_3f2db49.bundle' --all`
 349: git bundle verify 'C:\Users\<usuario>\Downloads\personal_agent_3f2db49.bundle'
```

### A.7 Bundles (`git bundle list-heads`, hash abreviado)

```text
$ git bundle list-heads ~/Downloads/personal_agent_8810b6e.bundle
4124d96 refs/codex/turn-diffs/checkpoints/740cdb7d8257ff07b1c6a0c407cd2e12/cfa80edf7cbe6d33fee360a0eb0b4b77/1795009390373/d5b5f4e2-a508-4aa2-b24c-251a1973795e
aac0d00 refs/codex/turn-diffs/checkpoints/b0920ad9c28efeb4a565d887c154b502/d48b5e492154612d20b691e02222066b/1794804920574/5b1adbfa-74be-4111-8aa5-69aabae89057
154f07d refs/codex/turn-diffs/checkpoints/f0a4b001261377557af06403686b9490/6cfa1da3bcbf475c6a9e511076647616/1794792076526/4ad7c644-96e1-4adb-9906-75c4dcdd03c5
27d135d refs/heads/docs/protocolo
8810b6e refs/heads/isolamento-env
673ceb1 refs/heads/item1/reaplicado
8810b6e refs/heads/main
a89791a refs/heads/revert/aa9a0a5
54f813c refs/heads/´
ffd9cbc refs/remotes/origin/HEAD
ffd9cbc refs/remotes/origin/main
8fd6678 refs/stash
19f19f2 refs/tags/pre-merge-isolamento
8810b6e HEAD
$ git bundle list-heads ~/Downloads/personal_agent_3f2db49.bundle
4124d96 refs/codex/turn-diffs/checkpoints/740cdb7d8257ff07b1c6a0c407cd2e12/cfa80edf7cbe6d33fee360a0eb0b4b77/1795009390373/d5b5f4e2-a508-4aa2-b24c-251a1973795e
aac0d00 refs/codex/turn-diffs/checkpoints/b0920ad9c28efeb4a565d887c154b502/d48b5e492154612d20b691e02222066b/1794804920574/5b1adbfa-74be-4111-8aa5-69aabae89057
154f07d refs/codex/turn-diffs/checkpoints/f0a4b001261377557af06403686b9490/6cfa1da3bcbf475c6a9e511076647616/1794792076526/4ad7c644-96e1-4adb-9906-75c4dcdd03c5
3f2db49 refs/heads/main
ffd9cbc refs/remotes/origin/HEAD
ffd9cbc refs/remotes/origin/main
19f19f2 refs/tags/pre-merge-isolamento
27d135d refs/tags/ref/docs-protocolo-27d135d
8fd6678 refs/tags/ref/item1-v1-nao-aceito
3f2db49 HEAD
```

### A.8 Integridade

```text
$ git fsck --unreachable --no-progress | cut -d" " -f2 | sort | uniq -c
     15 blob
     27 tree
(exit do fsck: 0; nenhuma linha "commit" = 0 commits inalcançáveis)
$ git stash list
(vazio)
$ git merge-base --is-ancestor <ponta> main
a89791a: em main
673ceb1: em main
8810b6e: em main
54f813c: em main
27d135d: fora de main
```
