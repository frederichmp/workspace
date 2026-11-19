# Plano: revisão dos subagentes v2 (`revisao-subagentes-v2`)

## 1. Contexto

**Pedido do responsável (2026-11-18):** revisar os subagentes para usá-los corretamente e gastar menos tokens. A revisão só de leitura está em `docs/entregas/revisao-subagentes-v2/revisao.md` (propostas P1 a P10), aprovada com "APROVADO".

**Medição.** Fonte: 67 transcrições `agent-*.jsonl`. As horas estão em UTC; o git usa −03:00.
- 7 de 66 chamadas, todas com mais de 60 turnos, somam 63% dos 146 M tokens de entrada dos subagentes.
- A suíte leva cerca de 4,5 min (271 s). Isso levou a pytest em segundo plano com Monitor e `sleep`.
- O 1º turno custa de 34 a 35 mil tokens nos três agentes. É o custo fixo: sistema, definições de ferramentas herdadas, CLAUDE.md, corpo do agente e pedido.
- Houve retornos de até 26 mil caracteres, com limite escrito de 15 a 20 linhas.
- O `src/tools/oracle_dba.py` foi relido 27 vezes em 12 chamadas.
- Os pedidos tinham de 440 a 780 caracteres no formato T/A/R/S. Nas 10 chamadas desde o PROCESSO.md, a mediana é de 2,6 mil e o máximo, 6,9 mil.

**Errata da revisão** (corrigida no passo 1):
- **A2:** dizia cerca de 37 mil tokens por turno; o medido é de 34 a 35 mil no 1º turno.
- **A3:** atribuía ao PROCESSO.md chamadas anteriores a ele, por causa do fuso.
- **A7:** dizia que o PROCESSO.md não era lido; está errado, porque as 10 chamadas citam o arquivo em comandos Bash. A P7 continua pelo custo do §7, que cresce a cada tarefa, e não por descumprimento.

## 2. Base

- Branch `main`, HEAD `3f2db49`. Esse commit foi feito por outra sessão às 23:01, durante esta. A árvore rastreada está limpa.
- Antes de cada commit, conferir o HEAD e o `git status`. Se algo mudou, PARE.
- Baseline: 272 passed e 16 skipped (`docs/entregas/registro_pos_merge/pytest_suite.txt`, em `66a15d7`; depois disso, só estilo e docs).
- Modelo da sessão, conferido na transcrição: `claude-opus-5-5`.
- Os não rastreados de hoje ficam fora dos commits: `docs/entregas/...` e `docs/plans/1.11-item1-B-refeito.md`.

## 3. Decisões do responsável ("APROVADO", 2026-11-18)

1. **Script como §2.** `tools/verificacao_padrao.py` é tratado como código do §2: escrito por Opus e conferido pelo `seguranca` antes do commit.
2. **Teste da lista fechada de ferramentas antes de fechar a tarefa.** Definição nova só vale no próximo chat (§3). Por isso, o teste é o 1º passo do próximo chat e o status fica "aguardando revisão" até lá.
3. **Reconciliação nesta tarefa.** A conciliação entre o PROCESSO §3 e o PROTOCOLO.md entra aqui (P5).
4. **Effort do `seguranca`.** `high` em conferência de diff; `xhigh` (o padrão) em decisão nova.

As decisões 1 e 3 eram perguntas abertas. Do "APROVADO", adotei a opção mais conservadora na 1 e a proposta P5 na 3. Se não era isso, recuse o plano.

**Item novo, que não estava na revisão (P11):** a sessão principal faz direto o passo pequeno, de até 3 edições em 1 ou 2 arquivos e sem rodar a suíte. Motivo: uma chamada de agente custa cerca de 35 mil tokens só para começar. Recuse o plano se não quiser este item.

## 4. Arquivos

Todos são escritos pela sessão principal (claude-opus-5-5).

| Passo | Arquivo | Ação |
|---|---|---|
| 1 | `docs/plans/revisao-subagentes-v2.md` | novo: cópia deste plano |
| 1 | `docs/entregas/revisao-subagentes-v2/revisao.md` e `medir_subagentes.py` | errata e script de medição, ambos não rastreados |
| 2 | `tools/verificacao_padrao.py` | novo (§2) |
| 2 | `tests/test_verificacao_padrao.py` | novo |
| 3 | `.claude/agents/mecanico.md`, `seguranca.md`, `verificador.md` | reescritos |
| 4 | `docs/PROCESSO.md` (cabeçalho, §1, §2, §3 e §5), `docs/PROTOCOLO.md`, `CLAUDE.md` | editados |
| 5 | `docs/GOVERNANCA_LOG.md` e `docs/PROCESSO.md` §7 | 1 linha no log; lições L24 e L25 |

Ficam intocados: `src/`, `app.py`, `db/`, `registry/`, `.claude/settings.json` e a memória local.

## 5. Passos

### Passo 1: plano e errata
- Copiar este plano para `docs/plans/revisao-subagentes-v2.md`.
- Corrigir A2, A3 e A7 no `revisao.md`.
- Salvar o script de medição consolidado, com a opção `--desde` e as horas em UTC.

Commit 1: `docs: plano da revisao-subagentes-v2`.

### Passo 2: `tools/verificacao_padrao.py` (P10)

**Uso:**

```bash
python -I tools/verificacao_padrao.py --tarefa <t> --base <commit> --esperado <P>/<S> \
  [--previsto <padrão> ...] [--rotulo <r>] [--registry-pendente]
```

**Regras gerais:**
- Usa só a biblioteca padrão, e nada roda no import.
- Nunca lê o `.env`, nunca imprime valor de variável e nunca define `ORACLE_SANDBOX`.

**Passo 0 do §5 (perfil do Windows):**
- Roda o comando do §5 por `powershell.exe -NoProfile` e lê só os nomes.
- Filtra em Python, sem diferenciar maiúsculas de minúsculas.
- Nome com prefixo proibido: PARE.

**Passo 1 do §5 (git):**
- Roda `git status --porcelain=v1 -z --untracked-files=all -- .`, tira o prefixo `IA/PERSONAL_AGENT/` e trata renomeação.
- Caminho fora de `--previsto` (fnmatch) e de `docs/entregas/<tarefa>/`: FALHA.
- Caminho fora do previsto em `tests/`, `src/` ou na raiz do projeto: PARE antes do pytest.

**Passo 2 do §5 (pytest):**
- Roda o comando do §5 em subprocesso, com ambiente sem `ORACLE_SANDBOX`, `PYTHONDONTWRITEBYTECODE=1` e timeout de 560 s.
- O resultado só é OK com todas estas condições:
  - código de saída 0;
  - 0 failed e 0 error;
  - passed = P e skipped = S;
  - todo SKIPPED com o motivo do `tests/conftest.py:188`;
  - nenhum "FALHA DE GOVERNANCA" na saída.
- Skipped abaixo de S: PARE com "POSSÍVEL EXECUÇÃO EM SANDBOX".
- Sem linha de contagem, com timeout ou com erro de import do `oracledb`: NÃO VERIFICADO.

**Passo 3 do §5 (greps):**
- Roda os 8 greps do §5, cada um com o seu resultado esperado.
- Código do `git grep`: 1 significa nenhuma linha; 0 significa linhas encontradas; qualquer outro é ERRO, nunca OK.
- `load_dotenv`: exatamente `app.py` e `src/main.py`, ambos com `override=False`.
- Os padrões ficam partidos no código-fonte, para o próprio script não casar com os greps.

**Saídas:**
- Arquivos `docs/entregas/<tarefa>/<rotulo>_{perfil,git_status,pytest,greps}.txt` e `<rotulo>.md`, com a tabela.
- `--tarefa` é validado: sem `..` e só com `[A-Za-z0-9._/-]`.
- O script não sobrescreve saída existente; para rodar de novo, mude o `--rotulo`.
- Código de saída: 0 OK, 1 FALHA, 2 PARE ou NÃO VERIFICADO.

**Teste que prova** (`tests/test_verificacao_padrao.py`):
- Só funções puras: sem git, sem subprocesso e sem pytest aninhado.
- Importa o script pelo caminho (`importlib.util.spec_from_file_location`).
- Casos:
  - saída OK;
  - skipped abaixo do esperado;
  - motivo de skip diferente;
  - "FALHA DE GOVERNANCA" com 0 failed;
  - erro de import do `oracledb`;
  - saída sem linha de contagem;
  - `git grep` com código 0, 1 e 2;
  - `load_dotenv` com as 2 linhas certas, com `override=True` e com 3 linhas;
  - caminho previsto e PARE em `tests/`;
  - leitura do `-z` com renomeação;
  - `--tarefa` com `..`;
  - filtro do perfil.

**Controle negativo, por mutação.** Roda numa cópia `git archive HEAD` mais os 2 arquivos novos, nunca com o `.env`. As mutações:
- **m1:** `git grep` com código 2 aceito como OK;
- **m2:** sem a checagem de skipped abaixo do esperado;
- **m3:** sem a checagem de "FALHA DE GOVERNANCA";
- **m4:** previsto que aceita qualquer caminho.

Em cada mutação:
- medir o fim de linha em bytes e fazer `assert` de exatamente 1 substituição (L3, L16);
- rodar só o arquivo de teste novo, com a saída em `controle_m<n>.txt` (L20);
- ao menos 1 teste deve falhar (L14).

**Ordem:**
1. Escrever o script e o teste; rodar o arquivo de teste.
2. Rodar os controles m1 a m4.
3. Chamar o `seguranca` com effort `high` para conferir o script e o teste (saída `conferencia_script.md`).
4. Corrigir o que vier NÃO CONFORME.
5. Execução real com o rótulo `smoke` (esperado: 272+N passed e 16 skipped).

Commit 2: `feat(tools): verificacao padrao do PROCESSO §5 em script, com testes`.

### Passo 3: agentes (P1 a P4 e P6 a P8)

Frontmatter exato. As descrições ficam entre aspas, e o YAML é validado com PyYAML.

```yaml
name: mecanico
description: "Executa um passo já decidido de plano aprovado (docs/plans/): testes sem conexão, refatoração e documentação, só nos arquivos do pedido. Não decide segurança, não edita código do PROCESSO §2 sem autorização literal do responsável e não commita."
model: sonnet
effort: high
color: blue
tools: Read, Edit, Write, Grep, Glob, Bash, PowerShell
```

```yaml
name: seguranca
description: "Decide e confere segurança do PROCESSO §2: kill, contas Oracle, hash, TTL, auditoria, .env e ORACLE_SANDBOX, registry. Usar antes de alterar arquivo do §2 e para conferir diff dessas áreas; não usar para leitura geral. Decide; não implementa."
model: opus
effort: xhigh
color: red
tools: Read, Grep, Glob, Bash, PowerShell, Write
```

```yaml
name: verificador
description: "Verificação antes de commit ou aceite: roda tools/verificacao_padrao.py (PROCESSO §5) e as checagens do plano contra o baseline. Somente leitura; grava só em docs/entregas/<tarefa>/."
model: haiku
color: green
tools: Bash, PowerShell, Read, Grep, Glob, Write
```

**Corpo dos três agentes.** Os limites e os PAREs atuais ficam. Entra o seguinte:
- **Economia:**
  - o Bash já começa na raiz do projeto, sem `cd`;
  - comandos independentes vão juntos num só;
  - arquivo grande se lê com `Grep -n` e `Read` com `offset`/`limit`, sem reler;
  - pytest em primeiro plano com timeout 600000, nunca em segundo plano, Monitor ou `sleep`;
  - primeiro o teste isolado; a suíte, uma vez no fim.
- **Teto de chamadas de ferramenta:** cerca de 30 no `mecanico`, 40 no `seguranca` e 15 no `verificador`. Ao chegar nele, o agente grava o parcial e devolve PARCIAL.
- **Lições no corpo, uma linha cada:**
  - `mecanico`: L1, L3/L16, L9, L13, L14/L18, L20;
  - `seguranca`: L2, L7, L8, L9, L13, L17, L22/L23;
  - `verificador`: L4, L12, L15, L21.

  Outra lição, só se o pedido citar: `Grep "L<n>\." docs/PROCESSO.md`.
- **Mapa do §2** resumido no `mecanico`, já com o script novo.
- **Retorno:**
  - 1ª linha de status: `OK|PARE|ERRO|PARCIAL`; no `seguranca`, `CONFORME|NÃO CONFORME|PENDENTE|PARCIAL`; no `verificador`, `OK|FALHA|PARE|NÃO VERIFICADO`;
  - no máximo 1.200 caracteres no `mecanico` e 1.500 no `seguranca` e no `verificador`;
  - detalhes em `docs/entregas/<tarefa>/`;
  - o `verificador` devolve só as linhas com FALHA ou PARE e resume as OK em uma linha.
- **No `verificador`:**
  - um comando do script, e as checagens do plano juntas num só comando;
  - script ausente ou com erro: usa a sequência manual do §5 e diz isso no retorno.
- **No `mecanico`:** pedido sem tarefa, arquivos ou critério de aceite: PARE e peça.

Commit 3: `chore(claude): agentes com ferramentas fechadas, teto de chamadas, licoes no corpo e retorno curto`.

### Passo 4: PROCESSO, PROTOCOLO e CLAUDE.md (P5, P9 e P11)
- **Cabeçalho do PROCESSO:** os agentes trazem no corpo o que precisam e leem aqui só o item citado no pedido.
- **§1:** "`mecanico` no resto, salvo passo pequeno (§3)".
- **§2:**
  - linha nova "Verificação padrão: `tools/verificacao_padrao.py`";
  - nota: se o mapa mudar, atualizar também o `mecanico.md`.
- **§3:**
  - effort por chamada: `seguranca` em `high` na conferência de diff e `xhigh` na decisão nova; `mecanico` em `medium` no passo só de documentação;
  - pedido de no máximo 1.000 caracteres, com o resto no plano, citado por seção;
  - retorno com linha de status e teto de tamanho (incorporado do PROTOCOLO.md);
  - uma chamada por passo e por controle;
  - SendMessage só para complemento curto do mesmo passo e com agente abaixo do teto;
  - P11;
  - "Definições novas" passa a pedir também a medição do 1º turno (antes: 34 a 35 mil tokens).
- **§5:**
  - abre com o comando do script e os códigos de saída;
  - os comandos listados ficam como referência: mudou um, muda também o script e o teste.
- **`docs/PROTOCOLO.md`:** vira um ponteiro de 2 linhas para o §3.
- **`CLAUDE.md`:** as 2 linhas sobre o PROTOCOLO viram uma: "Pedido e retorno de subagentes: `docs/PROCESSO.md` §3".

Commit 4: `docs: delegacao enxuta no PROCESSO e PROTOCOLO incorporado ao §3`.

### Passo 5: verificação, registro e lições
1. **Verificação pelo `verificador`.** Usa a definição atual, carregada no início do chat. Roda o script com o rótulo `final`, refaz à mão os 8 greps e compara com o `final_greps.txt`, e valida o YAML dos agentes.
2. **Registro.** Linha no GOVERNANCA_LOG.
3. **Lições novas no §7:**
   - **L24:** custo concentrado em chamadas longas.
   - **L25:** medição de transcrição. As horas estão em UTC e o git em −03:00. Ausência só se afirma depois de conferir Read, Grep e Bash.

Commit 5: `docs: registra revisao-subagentes-v2 no GOVERNANCA_LOG e licoes L24 e L25`.

### Próximo chat (aceite)
1. Conferir em `/agents` que os 3 agentes mostram as ferramentas novas.
2. Fazer uma chamada curta do `verificador` (`git status --short -- .`) e conferir que o retorno chega.
3. Medir o 1º turno com `medir_subagentes.py --desde <hora>`. Esperado: menos de 34 mil tokens.

Só depois disso o status passa a "aceito".

## 6. Verificação
- **YAML estrito** (PyYAML, `python -I`):
  - 1ª linha `---`, sem BOM;
  - só as chaves `name`, `description`, `model`, `effort`, `color` e `tools`;
  - `model` ∈ {sonnet, opus, haiku};
  - `effort` ∈ {low, medium, high, xhigh, max}.
- **Teste do script:** `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider tests/test_verificacao_padrao.py` dá N passed; cada mutação, de m1 a m4, dá ao menos 1 failed.
- **Verificação final** (`verificador`). Esperado: código de saída 0, e os 8 greps feitos à mão iguais aos do `final_greps.txt`.

  ```bash
  python -I tools/verificacao_padrao.py --tarefa revisao-subagentes-v2 --base 3f2db49 \
    --esperado <272+N>/16 --rotulo final \
    --previsto 'docs/entregas/1.11/item1/*' --previsto 'docs/entregas/isolamento_env/fase4/*' \
    --previsto 'docs/entregas/processo-subagentes/*' --previsto 'docs/entregas/registro_pos_merge/*' \
    --previsto 'docs/plans/1.11-item1-B-refeito.md'
  ```
- **Histórico:** `git log -5 --stat` mostra só os arquivos da seção 4.

## 7. GOVERNANCA_LOG (linha prevista)

`2026-11-18 | <hashes 1–4> | claude-opus-5-5 (sessão principal); conferência claude-opus-5-5 (seguranca); verificação claude-haiku-5-5 | .claude/agents/*, tools/verificacao_padrao.py, tests/test_verificacao_padrao.py, docs/PROCESSO.md, docs/PROTOCOLO.md, CLAUDE.md | processo e verificação | <o que mudou; N testes novos, nenhuma asserção removida; controles m1 a m4; pytest 272+N/16; teste do P1 pendente para o próximo chat> | aguardando revisão`

## 8. Fora de escopo
- O `model: sonnet` do `.claude/settings.json`, a memória local e o código de produção.
- Versionar o script de medição: ele fica em `docs/entregas/`.
- Automatizar o isolamento do `.env` (§5, passo 4).
