# isolamento-env fase 4, passo 0: reprodução dos achados 1, 2 e 4 (só leitura)

Base: branch isolamento-env, HEAD 3ff2b79. Código reproduzido em b0ce169 (3ff2b79 só acrescenta docs).
Baseline da suíte: 226 passed, 16 skipped.
Modelo: claude-haiku-5-5

## Tabela

| Achado | Veredito | Evidência |
|---|---|---|
| 1. OSError transitório na 1ª leitura do `.env` trava as subidas seguintes no mesmo processo | REPRODUZIU | Run 1 e run 2 lançam `RuntimeError: Carga do .env falhou nesta subida (PermissionError)`. Aberturas do `.env` por run: `{"1": 1, "2": 0}`. `estado_final: falhou`. Sentinela ausente do `os.environ`. A 2ª subida não relê o `.env`. |
| 2. Stub do `load_dotenv` e `dotenv_values` em `tests/test_fluxo_web.py` esconde a dependência do estado do CLI | REPRODUZIU | Controle sem mutação: 12 passed (execuções 2 e 3); na execução 1 houve 12 passed + 1 error (ver nota). Mutante (2 linhas removidas, `git diff --no-index` com 2 deleções): c (CLI + web) = 23 passed, 0 failed. d (web isolado) = 12 failed + 1 error. Todas as falhas depois do primeiro teste têm `Carga do .env falhou nesta subida (AssertionError)`. |
| 4. Chroma (`rag_search._obter_vectorstore`) lê `cwd/.env` fora da carga-env | REPRODUZIU | Execução a partir de diretório temporário com `.env` sentinela: `import_rag_search: 0`, `obter_vectorstore: 8`, `caminhos_distintos: [".env"]` (relativo ao cwd, fora da carga-env). |

## Detalhes do achado 2

- Passo c (CLI + web, mutante): 23 passed, nenhuma falha. Confere com a hipótese de herança do estado "ok" do CLI.
- Passo d (web isolado, mutante): o primeiro teste (`test_web_painel_fecha_apos_aprovar`) falha com `assert ['...\.env'] == []`, porque a leitura do `.env` ocorre sem o stub. Os testes seguintes falham com a mensagem `Carga do .env falhou nesta subida (AssertionError)`. O enunciado do Gemini ("depois do primeiro") confere para essas falhas; o primeiro teste tem outra mensagem.
- Três primeiras mensagens de falha, em d (só a linha da mensagem):
  1. `E AssertionError: assert ['C:\\Users\\...\\PERSONAL_AGENT\\.env'] == []`
  2. `RuntimeError: Carga do .env falhou nesta subida (AssertionError)`
  3. `RuntimeError: Carga do .env falhou nesta subida (AssertionError)`

## Nota sobre instabilidade do controle (achado 2)

- Execução 1 do controle sem mutação: `ERROR at teardown of test_web_painel_fecha_apos_aprovar` (AssertionError), resultado 12 passed + 1 error.
- Execuções 2 e 3 do mesmo controle: 12 passed, sem erro.
- Causa não identificada nesta reprodução. Não foi investigada, por escopo. Registrar como instabilidade observada; a fase 4 precisa considerá-la antes de usar esse teste como controle.

## Procedimento e confirmações

- Passo 0 (perfil do Windows, só nomes): sem linhas. OK.
- Passo 1: cópia de b0ce169 em `scratchpad/passo0/copia` (app.py e src/main.py presentes; sem `.env` antes do passo 2). Commit confirmado: `b0ce16947da999d1762ea976ec0f4423a88d19e1`.
- Passo 2: `.env` fictício com `SENTINELA_FASE4_A1=1` na cópia.
- Passo 3: `repro_achado1.py` lido antes de rodar. Recusa a raiz real por `samefile` e exige `ORACLE_SANDBOX` ausente.
- Passo 4: `repro_achado4.py` lido antes de rodar. Diretório `scratchpad/passo0/a4` com `.env` sentinela `SENTINELA_FASE4_A4=1`.
- Passo 5: segunda cópia em `scratchpad/passo0/copia_a2`, com `.env` sentinela `SENTINELA_FASE4_A2=1`. Mutação feita em Python por bytes (CRLF preservado), 1 ocorrência por linha removida. `test_fluxo_cli.py` não foi tocado.
- Passo 6: este arquivo.
- Confirmação: o `.env` real não foi aberto. Todas as leituras de `.env` foram nas cópias ou em diretórios temporários com sentinela.
- Confirmação: `ORACLE_SANDBOX` ausente em todos os comandos (`env -u ORACLE_SANDBOX` em pytest e python). Os scripts também conferem a ausência.
- Nenhum commit, `git add`, stash, checkout, reset ou push. Nenhuma alteração no repositório além deste arquivo não rastreado.
- Não houve Oracle.
- `git status` do §5 passo 1 não foi rodado nesta retomada.

## Saídas (scratchpad, fora do repositório)

- `scratchpad/passo0/a2_controle.txt`, `a2_controle_run3.txt`: controle sem mutação.
- `scratchpad/passo0/a2_c_cli_web.txt`: passo c.
- `scratchpad/passo0/a2_d_web_isolado.txt`, `a2_d_limpo.txt`: passo d.
- `scratchpad/passo0/test_fluxo_web.orig.py`: original antes da mutação.
