# Plano: baixa das pendências 1 e 3 e versionamento do `medir_subagentes.py` (`baixa-pendencias-1-3`)

## 1. Contexto

**Pedido do responsável (2026-11-23).** O levantamento só de leitura de 23/11 sobre as pendências 1 e 3 foi aceito com correções. Este plano registra no GOVERNANCA_LOG os dois fatos que estão sem registro e versiona o script que o PROCESSO §3 manda rodar.

**Pendência 1.** O que aconteceu em 2026-11-18, entre 23:06:14 e 23:07:18:
- foi criada a tag `ref/item1-v1-nao-aceito`;
- foram removidas 5 branches;
- o stash foi descartado.

O log trata isso como pendente (linha 141), e a evidência (`docs/_tmp/pendencia1_evidencias.md`) não está versionada.

**Pendência 3.** A reconciliação PROCESSO × PROTOCOLO foi feita em `1a79587`, mas as linhas 124 e 126 continuam "pendente".

**Script.** O `docs/entregas/revisao-subagentes-v2/medir_subagentes.py` é exigido pelo PROCESSO §3 e não está versionado.

**Árvore.** Nenhuma outra sessão escreve nela (verificado em 2026-11-23):
- as 7 sessões do projeto estão ociosas, iniciadas há 4 ou 5 dias;
- não há `index.lock`;
- a árvore rastreada está limpa;
- HEAD `113bb11`, 0/0 contra `origin/main`.

## 2. Pré-condição (só leitura, feita antes do `add`)

**Busca dirigida** em `docs/_tmp/pendencia1_evidencias.md` e em `docs/entregas/revisao-subagentes-v2/medir_subagentes.py`. Padrões, sem diferenciar maiúsculas:
- `IDENTIFIED BY`, `password`, `passwd`, `pwd`, `senha`;
- `user/pass@host`, como regex `[A-Za-z0-9_.-]+/[^[:space:]/@]+@[A-Za-z0-9_.-]+`;
- `@//`, `DSN`, `ghp_`, `AKIA`, `sk-`, `PRIVATE KEY`.

**Resultado: nenhuma ocorrência** nos dois arquivos para os 12 padrões. Só se reportaria arquivo, linha e padrão, nunca o valor. Antes do `add` do commit 1, a busca roda de novo; se houver ocorrência, a execução para.

**Texto literal das linhas citadas do `docs/GOVERNANCA_LOG.md`** (HEAD `113bb11`):

- **Linha 124:**
  `| 2026-11-18 (decisão do responsável) | ver commit "docs: precedencia do PROCESSO.md (secao 3) sobre o PROTOCOLO.md e registro pos-merge (P1)" | frederichmp | ` + "`CLAUDE.md` (1 linha), `docs/PROTOCOLO.md`, `docs/PROCESSO.md` §3 | Divergência registrada (protocolo de subagentes) | `docs/PROTOCOLO.md` (cherry-pick de `27d135d` → `a3362f2`) usa instrução `T:/A:/R:/S:`, resposta em uma linha (`OK`/`ERRO`) e \"Subagente novo por tarefa. Não reutilizar com SendMessage para outra tarefa.\"; o `docs/PROCESSO.md` §3 usa o bloco em prosa (Tarefa, Base, Arquivos, Objetivo, Autorização, Saída) e não proíbe reutilização. Regra de precedência acrescentada ao `CLAUDE.md`: \"Em divergência, PROCESSO.md §3 prevalece sobre PROTOCOLO.md até a tarefa de reconciliação.\" Mapa: `27d135d` (branch `docs/protocolo`) → `a3362f2` (`main`); a tag `ref/docs-protocolo-27d135d` → `27d135d` mantém resolvível a linha original (\"branch `docs/protocolo`\"). Autoria: sessão principal, claude-opus-5-5 | divergência registrada; reconciliação pendente |"
- **Linha 126:**
  "| 2026-11-18 (decisão do responsável) | sem commit (pendência) | frederichmp | `docs/PROTOCOLO.md` × `docs/PROCESSO.md` §3 | Tarefa pendente | Reconciliação em tarefa própria: formato de instrução e de resposta dos subagentes e reutilização com SendMessage. Até lá vale a regra de precedência do `CLAUDE.md` | **pendente** |"
- **Linha 141:**
  "| 2026-11-18 | ver commit \"docs: registro pos-merge, aceite da fase 4 e licoes L21 a L23 (P2)\" | frederichmp | `docs/GOVERNANCA_LOG.md`, `docs/PROCESSO.md` §7 (L21 a L23), `docs/plans/registro_pos_merge.md` | Registro (registro_pos_merge, P2) | Linhas acima: aceite, desvio, decisões, T1, T2, S1, controles, suíte, I3 e risco aberto. Lições L21 a L23. Plano na revisão 4, sincronizado com `~/.claude/plans/robust-giggling-grove.md` (sha256 `48ce84f2…` nos dois). Pendentes: fora de commit (tag do stash, `stash drop`, remoção de branches), reconciliação PROTOCOLO × PROCESSO §3 e cobertura do risco aberto. Autoria: sessão principal, claude-opus-5-5 | aguardando aceite |"
- **Linha 142**, trecho pertinente; a linha inteira está no log:
  "… PROTOCOLO.md incorporado ao §3 (fecha a pendência do P2) … (2) Sem diff rastreado pré-existente (HEAD `3f2db49`, árvore limpa); `docs/_tmp/pendencia1_evidencias.md` (não rastreado, 23:35) é de origem desconhecida (não foi esta sessão nem o `seguranca`), ficou fora dos commits e foi passado como previsto na verificação final. … | aguardando revisão |"
- **Linha 143:**
  "| 2026-11-19 | ver commit \"docs: decisoes do responsavel sobre a revisao-subagentes-v2\" | frederichmp | `docs/GOVERNANCA_LOG.md` (linha da revisao-subagentes-v2) | Decisões do responsável (revisao-subagentes-v2) | Recebidas em 2026-11-18. (1) `docs/_tmp/pendencia1_evidencias.md` é de outro chat do responsável (não desta sessão nem do `seguranca`); continua fora dos commits. (2) Riscos aceitos pelo responsável (\"pode aceitar ok\"): arquivo não rastreado fica fora do `git grep` e do 3.7, e `--previsto 'docs/*'` continua aceito. (3) Em vez do aceite, o responsável pediu o ajuste fino (`ajuste-fino-subagentes`, plano aprovado em 2026-11-19); o `/agents` continua para o próximo chat. Autoria: sessão principal, claude-opus-5-5 | riscos aceitos |"

**Confirmado agora:** o `1a79587` (2026-11-18 23:46:28) tirou do `CLAUDE.md` as linhas "Mensagens a subagentes e respostas seguem docs/PROTOCOLO.md." e "Em divergência, PROCESSO.md §3 prevalece sobre PROTOCOLO.md até a tarefa de reconciliação." No lugar entrou a atual `CLAUDE.md:35`: "Pedido e retorno de subagentes: `docs/PROCESSO.md` §3 (o PROTOCOLO.md foi incorporado nele)." O `docs/PROTOCOLO.md` tem 3 linhas e é ponteiro.

## 3. Commits

Regras para os três:
- só a sessão principal (claude-opus-5-5) executa;
- `git add` só com caminhos explícitos `:/IA/PERSONAL_AGENT/...`, nunca `-A` nem `.`;
- linha nova no log por append, preservando o CRLF do arquivo, sem editar linhas antigas;
- antes de cada commit, **pausa**: mostrar `git diff --cached --stat` e `git diff --cached -- ':/IA/PERSONAL_AGENT/docs/GOVERNANCA_LOG.md'` e aguardar a aprovação do responsável;
- sem push.

### Commit 1: pendência 1
1. Rodar de novo a busca dirigida do §2; se houver ocorrência, PARE.
2. `mkdir docs/entregas/pendencia1` e `mv docs/_tmp/pendencia1_evidencias.md docs/entregas/pendencia1/evidencias.md`. O arquivo não é rastreado, então é movido pelo sistema de arquivos. A `docs/_tmp/` fica vazia e some do `git status`.
3. Copiar este plano para `docs/plans/baixa-pendencias-1-3.md`.
4. Linha nova no log:

   `| 2026-11-23 | ver commit "docs(log): registra desvio da pendencia 1 e versiona evidencia" | frederichmp | refs do git (tag `ref/item1-v1-nao-aceito`; branches `revert/aa9a0a5`, `isolamento-env`, `item1/reaplicado`, `docs/protocolo`, `´`; `refs/stash`); `docs/entregas/pendencia1/evidencias.md`; `docs/plans/baixa-pendencias-1-3.md` | Desvio registrado (pendência 1) | 18/11 23:06:14–23:07:18: criada a tag `ref/item1-v1-nao-aceito` (→ `8fd6678`), removidas 5 branches (`revert/aa9a0a5`, `isolamento-env`, `item1/reaplicado`, `docs/protocolo`, `´`) e descartado o stash (COMPROVADO: refs atuais + evidência, C1, C2, C8, C9). Autoria: FORTE CORRELAÇÃO com console PowerShell da conta Frederich; responsável não recorda. Executado antes da autorização prevista (C15); sem perda (C13). Ratificado a posteriori pelo responsável em 2026-11-23. Baixa da linha 141 (item "fora de commit"; a reconciliação tem baixa no commit seguinte, e a "cobertura do risco aberto" continua com a linha 141). Evidência: `docs/entregas/pendencia1/evidencias.md` (origem: linhas 142–143), movida de `docs/_tmp/`; busca dirigida de credenciais sem ocorrência. Autoria do registro: sessão principal, claude-opus-5-5 | ratificado |`
5. `git add -- ':/IA/PERSONAL_AGENT/docs/entregas/pendencia1/evidencias.md' ':/IA/PERSONAL_AGENT/docs/plans/baixa-pendencias-1-3.md' ':/IA/PERSONAL_AGENT/docs/GOVERNANCA_LOG.md'` e pausa.
6. Commit: `docs(log): registra desvio da pendencia 1 e versiona evidencia`, com a autoria e a coautoria do modelo.

### Commit 2: pendência 3
1. Linha nova no log:

   `| 2026-11-23 | ver commit "docs(log): baixa da reconciliacao PROCESSO x PROTOCOLO (pendencia 3)" | frederichmp | `docs/PROTOCOLO.md` × `docs/PROCESSO.md` §3 | Baixa de pendência (pendência 3) | Reconciliação PROCESSO §3 × PROTOCOLO concluída em `1a79587` (2026-11-18, tarefa revisao-subagentes-v2, linha 142); `docs/PROTOCOLO.md` mantido como ponteiro (3 linhas); `CLAUDE.md:35` já reflete ("Pedido e retorno de subagentes: `docs/PROCESSO.md` §3"), e a regra de precedência saiu do `CLAUDE.md` no mesmo commit. Baixa das linhas 124 e 126 (e do item de reconciliação da linha 141). Autoria: sessão principal, claude-opus-5-5 | concluído |`
2. `git add -- ':/IA/PERSONAL_AGENT/docs/GOVERNANCA_LOG.md'` e pausa.
3. Commit: `docs(log): baixa da reconciliacao PROCESSO x PROTOCOLO (pendencia 3)`.

### Commit 3: script
1. `git add -- ':/IA/PERSONAL_AGENT/docs/entregas/revisao-subagentes-v2/medir_subagentes.py'` e pausa. O GOVERNANCA_LOG não muda neste commit, e a pausa mostra `--stat`.
2. Commit: `chore: versiona medir_subagentes.py`.
3. **Proposta minha, que só entra se você aprovar o plano com ela:** o `CLAUDE.md` pede o registro de toda alteração no GOVERNANCA_LOG. Para cumprir isso, a linha do commit 2 ganha a frase "O `medir_subagentes.py` (exigido pelo PROCESSO §3) é versionado no commit seguinte, `chore: versiona medir_subagentes.py`." Se você preferir sem essa frase, o commit 3 fica sem registro no log.

## 4. Fora de escopo
- As demais entregas não rastreadas, os `.txt` e os `.diff`.
- `docs/plans/1.11-item1-B-refeito.md`.
- `CLAUDE.md` e `docs/PROTOCOLO.md`: nenhuma mudança.
- A "cobertura do risco aberto" da linha 141.
- Push.

## 5. Verificação
Sem mudança de código, então o pytest não é exigido.

**A cada commit:**
- `git status -s -- .` antes e depois;
- `git show --stat HEAD`, com os arquivos exatos do commit;
- `git diff HEAD~1 -- docs/GOVERNANCA_LOG.md` com exatamente 1 linha acrescentada e 0 removidas.

**No fim:**
- `git log --oneline -4`;
- 3 commits à frente do `origin`, sem push;
- `docs/_tmp/` ausente do `git status`;
- `git ls-files docs/entregas/pendencia1 docs/entregas/revisao-subagentes-v2/medir_subagentes.py` lista os 2 arquivos.
