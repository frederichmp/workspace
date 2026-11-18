# Plano: processo de agentes e delegação (`processo-subagentes`)

## Contexto

Pedido do responsável (2026-11-18): atualizar a documentação do processo para que os próximos chats tenham instruções mais enxutas e os subagentes fiquem mais inteligentes. Levantamento feito só com leitura:

- **Agentes rasos e muito usados.** Os três `.claude/agents/*.md` têm de 3 a 5 linhas de instrução. Nas transcrições do projeto, o `verificador` foi chamado 46 vezes, o `mecanico` 42 e o `seguranca` 25.
- **Delegação repetitiva e incompleta.** Cada pedido repete cerca de 2 a 3 mil caracteres de regras fixas: `.env`, `ORACLE_SANDBOX`, "sem Oracle" e "Leia CLAUDE.md", que já chega ao subagente automaticamente. Nenhum pedido informa o *baseline* de passed/skipped, e só 8 de 21 pedidos ao `mecanico` dizem quando parar.
- **Lições do GOVERNANCA_LOG que nenhuma instrução cobre:**
  - incidente 01:27: o `monkeypatch` vazou `ORACLE_SANDBOX=1`, e a queda de skipped de 16 para 8 foi o que denunciou;
  - `aa9a0a5`: diff de segurança de uma sessão principal em Sonnet, commitado sem origem;
  - mutação de teste que não teve efeito por causa de CRLF;
  - DLL do `oracledb` bloqueada pelo Controle de Aplicativo;
  - `python.envFile` do VS Code;
  - variáveis do perfil do Windows.
- **Divergência de prática.** O `mecanico.md` manda devolver "commit criado", mas desde `86d1eac` o `mecanico` escreve e quem revisa e commita é a sessão principal.
- **Proveniência fora do repositório.** A regra sobre a origem de diffs existe só na memória local do usuário.
- **Fragilidade escondida.** O frontmatter do `mecanico.md` e do `seguranca.md` é YAML inválido num parser estrito (`ScannerError`, por causa do ": " sem aspas na descrição). O Claude Code tolera hoje, mas a documentação diz que YAML que não faz parse descarta o agente sem aviso.
- **Documentação oficial** (code.claude.com/docs/en/sub-agents): existem os campos `effort`, `color`, `disallowedTools` e `memory`. Campo desconhecido é ignorado sem erro. Subagentes, exceto Explore e Plan, recebem o CLAUDE.md.

**Decisões do responsável (2026-11-18):**
1. Lições curadas e versionadas em `docs/PROCESSO.md`, sem o campo `memory`.
2. `effort`: `seguranca` em xhigh, `mecanico` em high, `verificador` no padrão.
3. Tarefa só de leitura dispensa o `/plan`.
4. `.claude/settings.json` continua com `model: sonnet`, e entra uma regra de checagem do modelo antes de mexer em código de segurança.

## Base

- Branch `isolamento-env`, HEAD `11767be`.
- Baseline: 199 passed, 16 skipped.
- Os commits ficam nesta branch, que é onde os próximos chats começam.
- Ficam fora dos commits os arquivos hoje não rastreados: `docs/entregas/1.11/item1/*`, `docs/plans/1.11-item1-B-refeito.md` e `db/ops_kill.sqlbkp`.

## Arquivos

Todos escritos pela sessão principal (Opus).

| Arquivo | Ação |
|---|---|
| `docs/plans/processo-subagentes.md` | novo: cópia deste plano aprovado |
| `.claude/agents/mecanico.md`, `seguranca.md`, `verificador.md` | reescritos |
| `docs/PROCESSO.md` | novo, com cerca de 180 linhas |
| `CLAUDE.md` | acréscimos e 1 regra alterada (seção 2) |
| `docs/GOVERNANCA_LOG.md` | 1 linha nova |

Ficam intocados: código, testes, `db/`, `registry/`, `.claude/settings.json` e a memória local.

## 1. Agentes: frontmatter exato e conteúdo do corpo

As descrições ficam entre aspas, para serem YAML válido.

```yaml
name: mecanico
description: "Executa passo já decidido de plano aprovado (docs/plans/): testes sem conexão, refatoração sem decisão de segurança e documentação, só nos arquivos listados no pedido. Não decide segurança, não edita código de segurança (docs/PROCESSO.md §2) sem autorização literal do responsável e não commita."
model: sonnet
effort: high
color: blue
disallowedTools: Agent
```

Corpo do `mecanico`:
- **Antes de editar:** ler o passo do plano e o PROCESSO §2 e §7. Rodar `git status`; se houver diff que o pedido não explica, PARE. Confirmar os arquivos permitidos.
- **Limites:** PARE em vez de contornar.
- **Como trabalhar:** menor diff possível; seguir os padrões existentes (`tests/fakes_oracle.py`, fixtures do conftest); controle negativo quando o plano pedir; conferir que a mutação foi aplicada (CRLF).
- **Testes:** usar o comando padrão. Skipped abaixo do baseline: PARE e não rode de novo. pytest bloqueado conta como "não verificado".
- **Retorno em até 15 linhas:**
  - ID do modelo;
  - arquivos alterados;
  - classificação das mudanças em testes: expectativa alterada com justificativa, só chamada, asserção acrescentada, ou "nenhuma asserção removida ou enfraquecida";
  - contagens comparadas com o baseline;
  - pendências.
- Não faz commit nem `git add`.

```yaml
name: seguranca
description: "Decide e confere segurança: fluxo de kill, contas e privilégios Oracle, hash de identidade, TTL de aprovação, logs de auditoria, isolamento do .env e de ORACLE_SANDBOX, hashes do registry. Usar proativamente antes de mudar código de segurança (docs/PROCESSO.md §2) e para conferir diff dessas áreas. Decide; não implementa."
model: opus
effort: xhigh
color: red
disallowedTools: Edit, NotebookEdit, Agent
```

Corpo do `seguranca`:
- Só grava `decisao*.md` e `conferencia*.md` em `docs/entregas/<tarefa>/`.
- **Método:**
  1. Rastrear o caminho completo com `arquivo:linha` conferidos agora.
  2. Listar os casos de recusa, o que vai para cada log (JSONL e OPS_KILL_AUDIT) e o que a conta KILL pode executar.
  3. Atacar a proposta: parâmetros vindos do LLM, TOCTOU, vazamento de ambiente, CLI × Web × abas, exceção no meio do fluxo, resultado desconhecido.
  4. Propor a mudança mínima e o teste que a prova, com controle negativo.
  5. Separar fato verificado de inferência e de "esperado pela documentação". Fato de banco só vale com leitura fornecida pelo responsável.
  6. O que cabe ao responsável vira PENDENTE APROVAÇÃO.
- **Retorno:** veredito por ponto (CONFORME / NÃO CONFORME / PENDENTE).

```yaml
name: verificador
description: "Verificação antes de cada aceite: git status, pytest sem conexão, greps de regressão e contagem contra o baseline. Usar proativamente depois de alteração e antes de commit ou aceite. Somente leitura; grava apenas saídas em docs/entregas/<tarefa>/."
model: haiku
color: green
disallowedTools: Edit, NotebookEdit, Agent
```

Corpo do `verificador`:
- Só grava em `docs/entregas/<tarefa>/`. Nada que altere o índice ou a árvore de trabalho.
- Segue a sequência do PROCESSO §5.
- **Para quando:** skipped diferente do esperado (se for menor, o aviso é "POSSÍVEL EXECUÇÃO EM SANDBOX"); aparece algum nome no perfil do Windows; pytest bloqueado (conta como "não verificado").
- **Retorno:** tabela com checagem, esperado, obtido e OK/FALHA, mais o ID do modelo.

## 2. CLAUDE.md

Nenhuma regra é removida. A única alteração é a regra do `/plan`, aprovada na decisão 3.

**Segurança**, acrescentar:
- Teste nunca define `ORACLE_SANDBOX=1` no processo do pytest (nem por `monkeypatch`): só `"0"` ou ausente. `"1"` só em `.env` fictício lido por subprocesso sem credenciais.
- Skipped abaixo do baseline sem `ORACLE_SANDBOX` no shell: parar, não rodar o pytest de novo e avisar (incidente 01:27).

**Operação**, acrescentar:
- Comando padrão (Git Bash): `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider`. Rodar só pelo terminal, nunca pelo executor de testes do VS Code.
- A raiz do git é `Workspace/`: `git add` só com caminhos explícitos, nunca `git add -A` nem `git add .`.
- Antes de commitar: registrar a origem de todo diff que já estava no working tree e o modelo de quem escreveu cada arquivo, no commit (coautoria de todos os modelos) e no GOVERNANCA_LOG.

**Processo de tarefa:**
- **Alterada:** "Toda tarefa **que grava no repositório** começa em `/plan`…". Tarefa só de leitura (revisão, diagnóstico, levantamento) dispensa plano, commit e GOVERNANCA_LOG: saída curta vai no chat, longa em `docs/entregas/<tarefa>/`. Se precisar gravar mais que isso, volta ao `/plan`.
- **Nova:** código de segurança (mapa no PROCESSO §2) só é escrito por Opus. Antes de tocá-lo, a sessão principal confere o próprio modelo e para se não for Opus. O `mecanico` só o edita com autorização literal do responsável citada no pedido.
- **Nova:** a delegação segue o formato do PROCESSO §3, e as regras fixas já ficam nos agentes. Subagente não commita: a sessão principal revisa o diff inteiro, mostra o `git diff` e commita.
- **Nova:** ao fechar a tarefa, a sessão principal acrescenta as lições novas ao PROCESSO §7.
- "Antes de cada aceite…" passa a citar a sequência do PROCESSO §5.

## 3. `docs/PROCESSO.md` (seções)

- **§1 Ciclo da tarefa:** abertura → plano → decisão → execução → revisão → verificação → commit → registro → aceite, com quem faz cada etapa e o caso da tarefa só de leitura.
- **§2 Mapa de código de segurança:**
  - kill e auditoria em `oracle_dba.py`;
  - `db/ops_kill.sql`, com commit PENDENTE APROVAÇÃO;
  - topo de `app.py` e `src/main.py`, e o painel HITL;
  - guard e `CHAVES_ENV_SANDBOX` no `tests/conftest.py`;
  - `executor.py`, `registry.py`, `registry/` e `tools/verificar_registro.py`;
  - `.env.example`.
- **§3 Delegação:** tabela agente × modelo/effort × quando usar ou não × onde grava; modelo de pedido em 6 linhas (tarefa e passo, base e baseline, arquivos permitidos, objetivo e critério, autorização literal, saída); paralelismo; como conferir o retorno.
- **§4 Modelo de plano:** Contexto, Base e baseline, Arquivos por passo e agente, Passos (com o teste que prova e o controle negativo), Decisões do responsável, Verificação com resultado esperado, Linha prevista do GOVERNANCA_LOG, Fora de escopo.
- **§5 Verificação padrão:**
  - perfil do Windows, só nomes;
  - `git status`;
  - pytest com o critério de skipped;
  - greps padrão com resultado esperado, já conferidos hoje em `11767be`;
  - equivalentes em PowerShell;
  - `git archive` para checar isolamento.
- **§6 GOVERNANCA_LOG:** colunas e checklist do campo "Detalhe".
- **§7 Lições aprendidas:** curadas, de 1 a 2 linhas cada, no formato "o que houve → como evitar → como detectar". Itens: 01:27; `aa9a0a5`; CRLF; DLL bloqueada; VS Code; perfil do Windows; fato de banco; rerun do Streamlit; números de linha que envelhecem; raiz do git.
- **§8 Abertura de chat** (para o responsável): modelo de 4 linhas com tarefa e tipo, base, restrições e autorização, limite de tempo e entregável.

## 4. Execução e commits (após aprovação)

Todos os commits usam caminhos explícitos, mostram o `git diff` antes, trazem `Co-Authored-By: Claude Opus 5.5` e não vão para push.

1. Copiar o plano para `docs/plans/`. Commit `docs: plano do processo de agentes e delegacao`.
2. Reescrever os 3 agentes e validar o YAML. Commit `chore(claude): agentes com contexto, limites e retorno padronizado`.
3. Criar `docs/PROCESSO.md` e alterar o `CLAUDE.md`. Commit `docs: processo de tarefa e delegacao e regras novas no CLAUDE.md`.
4. Rodar o `verificador` (Haiku) usando o modelo de pedido novo.
5. Acrescentar a linha no GOVERNANCA_LOG, com os hashes, a autoria (claude-opus-5-5 e claude-haiku-5-5) e as decisões. Commit `docs: registra processo de agentes no GOVERNANCA_LOG`.

## 5. Verificação

- **YAML estrito** (PyYAML 6.0.3, `python -I`), nos 3 agentes:
  - 1ª linha exatamente `---`, sem BOM;
  - `name` presente;
  - só chaves documentadas;
  - `effort` ∈ {low, medium, high, xhigh, max};
  - `model` ∈ {sonnet, opus, haiku}.
- **Caminhos:** os citados em `docs/PROCESSO.md` e no `CLAUDE.md` existem (script de checagem).
- **`verificador`:**
  - `git status` só com o previsto;
  - pytest com 199 passed e 16 skipped;
  - greps padrão no resultado esperado;
  - saída em `docs/entregas/processo-subagentes/`, não rastreada.
- **Histórico:** `git log -5 --stat` só com os arquivos previstos.
- **Próximo chat:** `/agents` mostra os 3 agentes com modelo, effort, cor e ferramentas novos. O chat atual pode continuar usando as definições carregadas no início.

## Fora de escopo

- Achados da revisão de hoje, que viram itens próprios:
  - guard em `tests/conftest.py:187`;
  - `except Exception` em `oracle_dba.py:823`;
  - lista fixa de protegidos;
  - dependências;
  - `db/ops_kill.sqlbkp`.
- Troca do modelo padrão no `settings.json`.
- Memória local do usuário.
