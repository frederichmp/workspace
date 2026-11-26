# Plano: integrar `item6/v2` e `r1-ampliada` na `main` (`merge-r1-main`): **APROVADO pelo responsável em 2026-11-26** ("Pode seguir sua sugestão": M1 branch de integração, M2 manter; M3 push da `main` autorizado depois)

- **Pedido:** do responsável, em 2026-11-26 ("pode realizar também o MERGE").
- **Autor:** sessão principal (claude-opus-5-5). Esta seção é só plano; os fatos abaixo vieram de leitura e de `git merge-tree`, que não toca o working tree nem as branches.

## 1. Fatos (2026-11-26)

| Branch | Local = remoto | Acima da base `37b3cc1` |
|---|---|---|
| `main` | `ffb7bad` | 1 commit: `ffb7bad` (lições L46 a L48 e uma linha no log) |
| `item6/v2` | `bc5c608` | 26 commits (item 6 v2, aceito) |
| `r1-ampliada` | `2de8f46` | 46 commits: contém a `item6/v2` até `cdc8f6d` e a R1 ampliada inteira, aceita. Não contém o `bc5c608` (aceite do item 6) |

- **Conflitos previstos (`git merge-tree`):** só em documento.
  - `docs/GOVERNANCA_LOG.md`: linhas acrescentadas dos dois lados.
  - `docs/PROCESSO.md` §7: a `main` tem L46 a L48 e as branches têm L49 a L68.
  - O código mescla limpo.
- **Escopo:** tudo dentro de `IA/PERSONAL_AGENT/` (290 arquivos); nada fora.
- **Histórico:** a `main` é linear até aqui.

## 2. Passos

1. **Branch de integração:** `integra/r1-main`, criada da `main` (`ffb7bad`).
2. **Merge 1:** `git merge --no-ff item6/v2`, com os conflitos de documento resolvidos por união.
3. **Merge 2:** `git merge --no-ff r1-ampliada`, também com resolução por união.
4. **Regra da união:**
   - **Log:** todas as linhas dos dois lados, em ordem de data, sem perder nenhuma.
   - **Lições:** L45, L46 a L48 da `main` e L49 a L68 das branches, em ordem numérica.
   - **Conferência:** por script, todo o conteúdo dos dois lados tem de estar no resultado e o arquivo não pode ter marcador `<<<<<<<`.
   - **Fim de linha:** CRLF preservado.
5. **Verificação do resultado:**
   - suíte completa: o esperado é 1755 passed e 16 skipped, porque a `main` não acrescenta teste;
   - `verificacao_padrao.py --base ffb7bad`;
   - greps 3.x;
   - nenhuma regressão de mutantes, porque o código vem igual ao da `r1-ampliada`, que já tem 235/235 com o controle novo. A conferência é por diff: árvore de `integra/r1-main` contra `r1-ampliada`, fora os dois documentos, com diferença vazia.
6. **Pausa:** `diff --cached` em cada merge.
7. **`main`:** avança por fast-forward até `integra/r1-main`, sem reescrever o histórico.
8. **Push da `main`:** só com autorização explícita, depois de varredura dirigida em chamada separada e sem force. A autorização do merge não inclui o push da `main`.

## 3. Decisões do responsável

- **M1:** fast-forward da `main` até o merge de integração (recomendado), ou merge direto na `main`. O resultado é o mesmo; a branch de integração permite verificar antes de mexer na `main`.
- **M2:** apagar ou manter `item6/v2` e `r1-ampliada` depois. A recomendação é manter, porque o histórico já está na `main`, e apagar fica para quando você pedir.
- **M3:** autorizar o push da `main` (passo 8).

## 4. Paradas

- Conflito em arquivo que não seja documento.
- Suíte diferente de 1755/16, ou skipped abaixo de 16.
- Árvore de código diferente da `r1-ampliada`.
- Conteúdo perdido na união.

## 5. Execução (2026-11-26)

- `integra/r1-main` criada da `main` (`ffb7bad`).
- **Merge 1** (`item6/v2`) em `71ab8ed`: conflitos só no log e no PROCESSO §7, resolvidos por união, com 0 linhas perdidas; saiu a nota provisória da numeração.
- **Merge 2** (`r1-ampliada`) em `293e577`: conflito só no log, por união; a árvore ficou igual à `r1-ampliada`, fora os 2 documentos.
- **Verificação do resultado:** 1755 passed, 16 skipped; `registry/` e `db/` sem mudança.
- **Fast-forward** da `main` até `293e577`.
- **Varredura antes do push:** achou o usuário do Windows em 45 evidências do item 6, publicadas antes nas duas branches. Por decisão do responsável ("Redija e suba"):
  - `bd7117e` redigiu `<usuario>` e `<organizacao>` em 67 arquivos da árvore da `main`;
  - `976195a` redigiu o e-mail restante numa evidência do 1.10.
- **Push da `main`:** `ffb7bad..976195a`, sem force, com varredura limpa.
- **Limpeza:** a branch local `integra/r1-main`, já incorporada, foi apagada.
- **Limite:** o histórico já publicado mantém o dado (sem reescrita).
