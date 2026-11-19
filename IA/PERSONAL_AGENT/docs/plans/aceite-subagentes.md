# Plano: aceite dos subagentes sem o `/agents` (`aceite-subagentes`)

## 1. Contexto

**O que aconteceu.** O responsável rodou `/agents` num chat novo (2026-11-19). A resposta foi "The /agents wizard has been removed", na versão 2.1.327. O aceite das tarefas `ajuste-fino-subagentes` e `guarda-r1-r3` dependia dessa conferência: modelo, effort, cor, ferramentas e travas de cada agente. O `docs/PROCESSO.md` §3 ainda manda conferir "com `/agents`".

**Evidência já colhida nesta sessão** (transcrições e `docs/entregas/ajuste-fino-subagentes/`):

| Agente | Modelo (transcrição) | Ferramentas fechadas | Guarda | `maxTurns` |
|---|---|---|---|---|
| `verificador` | claude-haiku-5-5 | 1º turno 14,5 mil (antes 34,5 mil) | R1, R2 e R4 bloquearam; `git ci` bloqueado (`sondas.md`, `verificacao_r1r3.md`) | não atingido |
| `seguranca` | claude-opus-5-5 | 1º turno 15,1 mil (antes 35,0 mil) | R2 bloqueou o script de ataque dele | não atingido (máximo de 45 turnos, contra 60) |
| `mecanico` | não rodou com a definição nova | não medido | não medido | não medido |

O hook que falha bloqueia com cada mecanismo sozinho (`sondas_h1.md`), e o YAML dos 3 agentes foi validado.

**Faltam:** o `mecanico` com a definição nova e o corte do `maxTurns`.

## 2. Base
- Branch `main`, HEAD `e10fef2`, árvore rastreada limpa.
- Baseline: 614 passed e 16 skipped.
- Modelo da sessão: claude-opus-5-5.

## 3. Passos

### Passo 1: sonda do `mecanico` (definição real, só leitura)
Uma chamada curta, sem pytest.
- Bash `git status --short -- .`: deve rodar.
- Bash `git add --dry-run -- docs/PROCESSO.md`: deve ser bloqueado pelo guarda (R1, perfil `mecanico`).
- Bash `cat .env.local`: deve ser bloqueado (R2). O arquivo não existe; se o guarda falhar, só sai erro de arquivo inexistente.

**Conferir na transcrição:**
- o modelo `claude-sonnet-5-5`;
- o 1º turno abaixo de 34 mil tokens;
- só ferramentas da lista usadas.

**Saída:** `docs/entregas/aceite-subagentes/sonda_mecanico.md`.

### Passo 2: sonda do `maxTurns`
- **Agente temporário:** `.claude/agents/sonda-maxturns.md`, com haiku, só Bash e `maxTurns: 2`.
- **Antes de chamar:** esperar o aviso de tipo novo (L34).
- **Pedido:** 4 comandos `echo`, um por chamada.
- **Esperado:** corte depois de 2 turnos, com a saída marcada como parcial. O que vale é o que a transcrição registrar.
- **Depois:** o arquivo do agente é apagado, sem commit.

**Saída:** `docs/entregas/aceite-subagentes/sonda_maxturns.md`.

### Passo 3: PROCESSO §3
O item "Definições novas" deixa de citar o `/agents`. A confirmação passa a ser por evidência:
1. YAML validado;
2. modelo e 1º turno na transcrição, com `medir_subagentes.py --desde <hora UTC>`;
3. sonda do guarda: 1 comando liberado e 1 bloqueado, em chamadas separadas (L37).

O texto registra que o `/agents` foi removido na 2.1.327.

Commit 1: `docs: aceite de subagente por evidencia, sem o /agents (PROCESSO secao 3)`, junto com a cópia deste plano em `docs/plans/aceite-subagentes.md`.

### Passo 4: registro
Linha no GOVERNANCA_LOG com a tabela de evidência completa: os 3 agentes, o hook que falha e o `maxTurns`. O status fica "evidência completa; aceite do responsável pendente". O aceite é do responsável (PROCESSO §1, etapa 8).

Commit 2: `docs: evidencia de aceite dos subagentes no GOVERNANCA_LOG`.

## 4. Verificação
- **Transcrições:** as das duas sondas, lidas por script (`tool_use`, `tool_result`, `model` e `usage` do 1º turno).
- **Repositório:** `git status` no fim só com os não rastreados conhecidos, e o agente temporário apagado.
- **Suíte:** não precisa rodar de novo, porque nada no código muda. A última foi 614/16 em `3e4674b`; de lá para cá, só documentação.

## 5. Fora de escopo
- Mudar os agentes ou o guarda.
- O teste do `effort` e da `color`, que não aparecem na transcrição. São aceitos pelo YAML validado e pela documentação.
