# Regras do projeto PERSONAL_AGENT

## Segurança (inegociável)
- Nunca ler, editar ou imprimir o conteúdo de `.env`.
- Nunca conectar ao Oracle em testes sem `ORACLE_SANDBOX=1`, definida só na sessão de execução autorizada.
- Nunca usar `ORACLE_USER` (legado). Diagnóstico usa `ORACLE_USER_DIAG`; kill usa `ORACLE_USER_KILL` e chama `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION`.
- Nunca escrever `ALTER SYSTEM` ou SQL de sessão no Python.
- Nunca alterar hash em `registry/` sem commit marcado "PENDENTE APROVAÇÃO".
- Nunca colar, imprimir ou commitar credenciais, mesmo em saídas de teste.

## Operação
- Testes sem conexão: `pytest -v -rs` (sem `ORACLE_SANDBOX`).
- Toda alteração termina com `git diff` mostrado e commit com mensagem convencional.
- Não fazer `git push` sem autorização explícita.
- Ao concluir uma tarefa, atualizar `docs/GOVERNANCA_LOG.md` com o que mudou e o status.

## Governança
- Não alterar expectativas de teste para fazer código passar; reportar a falha.
- Não enfraquecer asserções sem justificativa na lista de alterações.

## Processo de tarefa
- Toda tarefa começa em `/plan`. O plano vai para `docs/plans/<tarefa>.md` e só é executado após aprovação.
- Um commit por correção. Nunca `git push`.
- Subagentes: Sonnet para mecânico, Haiku para execução de testes, Opus só para decisão de segurança.
- Paralelizar apenas com conjuntos de arquivos disjuntos. Nunca dois agentes em `oracle_dba.py`, `main.py` ou `app.py`.
- Saídas grandes vão para `docs/entregas/`; o chat recebe caminho e resumo.
- Antes de cada aceite: `git status`, `pytest -q`, greps de regressão.