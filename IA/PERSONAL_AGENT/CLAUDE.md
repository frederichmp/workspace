# Regras do projeto PERSONAL_AGENT

Como cumprir estas regras (ciclo, delegação, verificação e lições): `docs/PROCESSO.md`, leitura obrigatória antes de planejar ou delegar.

## Segurança (inegociável)
- Nunca ler, editar ou imprimir o conteúdo de `.env`.
- Nunca conectar ao Oracle em testes sem `ORACLE_SANDBOX=1`, definida só na sessão de execução autorizada.
- Teste nunca define `ORACLE_SANDBOX=1` no processo do pytest (nem por `monkeypatch`): só `"0"` ou ausente. `"1"` só em `.env` fictício lido por subprocesso sem credenciais.
- Skipped abaixo do baseline sem `ORACLE_SANDBOX` no shell: parar, não rodar o pytest de novo e avisar (incidente 01:27).
- Nunca usar `ORACLE_USER` (legado). Diagnóstico usa `ORACLE_USER_DIAG`; kill usa `ORACLE_USER_KILL` e chama `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION`.
- Nunca escrever `ALTER SYSTEM` ou SQL de sessão no Python.
- Nunca alterar hash em `registry/` sem commit marcado "PENDENTE APROVAÇÃO".
- Nunca colar, imprimir ou commitar credenciais, mesmo em saídas de teste.

## Operação
- Testes sem conexão: `pytest -v -rs` (sem `ORACLE_SANDBOX`).
- Comando padrão (Git Bash): `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider`. Só pelo terminal, nunca pelo executor de testes do VS Code.
- A raiz do git é `Workspace/`: `git add` só com caminhos explícitos, nunca `git add -A` nem `git add .`.
- Antes de commitar: origem de todo diff que já estava no working tree e modelo de quem escreveu cada arquivo, registrados no commit (coautoria de todos os modelos) e no `docs/GOVERNANCA_LOG.md`.
- Toda alteração termina com `git diff` mostrado e commit com mensagem convencional.
- Não fazer `git push` sem autorização explícita.
- Ao concluir uma tarefa, atualizar `docs/GOVERNANCA_LOG.md` com o que mudou e o status.

## Governança
- Não alterar expectativas de teste para fazer código passar; reportar a falha.
- Não enfraquecer asserções sem justificativa na lista de alterações.

## Processo de tarefa
- Toda tarefa que grava no repositório começa em `/plan`. O plano vai para `docs/plans/<tarefa>.md` e só é executado após aprovação.
- Tarefa só de leitura (revisão, diagnóstico, levantamento) dispensa plano, commit e GOVERNANCA_LOG: saída curta no chat, longa em `docs/entregas/<tarefa>/`. Se precisar gravar mais que isso, volta ao `/plan`.
- Um commit por correção. Nunca `git push`.
- Subagentes: Sonnet para mecânico, Haiku para execução de testes, Opus só para decisão de segurança.
- Código de segurança (mapa em `docs/PROCESSO.md` §2) só é escrito por Opus. Antes de tocá-lo, a sessão principal confere o próprio modelo e para se não for Opus. O `mecanico` só o edita com autorização literal do responsável citada no pedido.
- Delegação no formato de `docs/PROCESSO.md` §3; as regras fixas já estão nos agentes. Subagente não commita: a sessão principal revisa o diff inteiro, mostra o `git diff` e commita.
- Pedido e retorno de subagentes: `docs/PROCESSO.md` §3 (o PROTOCOLO.md foi incorporado nele).
- Paralelizar apenas com conjuntos de arquivos disjuntos. Nunca dois agentes em `oracle_dba.py`, `main.py` ou `app.py`.
- Saídas grandes vão para `docs/entregas/`; o chat recebe caminho e resumo.
- Antes de cada aceite: `git status`, `pytest -q`, greps de regressão (sequência em `docs/PROCESSO.md` §5).
- Ao fechar a tarefa, a sessão principal acrescenta as lições novas a `docs/PROCESSO.md` §7.