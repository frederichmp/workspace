# Verificação do Passo 1 de docs/plans/isolamento_env_fase4.md

Working tree com o Passo 1 aplicado, sem commit. HEAD 3ff2b79. Modelo: claude-haiku-5-5.

## Resultados

| Item | Checagem | Esperado | Obtido | OK/FALHA |
|---|---|---|---|---|
| 1.0 | Perfil do Windows, só nomes | nenhuma linha | nenhuma linha | OK |
| 1.1 | `git status --short -- .` | só os 5 arquivos previstos + não rastreados da abertura | M tests/test_carga_env_entrada.py, M tests/test_fluxo_cli.py, M tests/test_fluxo_web.py, ?? tests/_guarda_env.py, ?? tests/test_guarda_env.py, mais os não rastreados da abertura, docs/plans/isolamento_env_fase4.md e docs/entregas/isolamento_env/fase4/ | OK |
| 1.2 | pytest sem conexão (1 execução) | 0 failed; passed 252; skipped 16 | 252 passed, 16 skipped, 0 failed, 0 error, 13 warnings | OK |
| 1.2 | Skip | motivo do sandbox | `SKIPPED [16] tests\conftest.py:188: requer ambiente de sandbox autorizado (ORACLE_SANDBOX=1)` | OK |
| 1.3 | G1 ORACLE_USER legado | nenhuma linha | nenhuma linha | OK |
| 1.3 | G2 SQL de sessão no Python | nenhuma linha | nenhuma linha | OK |
| 1.3 | G3 `override=True` | nenhuma linha | nenhuma linha | OK |
| 1.3 | G4 `load_dotenv(` | 2 linhas, override=False | app.py:69 e src/main.py:54, ambas override=False | OK |
| 1.3 | G5 teste que liga o sandbox | nenhuma linha | nenhuma linha | OK |
| 1.3 | G6 credencial em print ou log | nenhuma linha | nenhuma linha | OK |
| 1.3 | G7 `git diff --stat b0ce169 -- registry/ db/` | vazio | vazio | OK |
| 1.3 | G8 `.env` versionado | nenhuma linha | nenhuma linha | OK |
| 2 | `pytest -q -rs -p no:cacheprovider tests/test_fluxo_web.py` isolado | 12 passed | 12 passed, 0 failed | OK |
| 3 | Controle por mutação do Achado 2 (cópia fora do repositório) | falhas "a carga do .env não rodou neste teste Web" | 23 passed, 0 failed; nenhuma das mensagens esperadas | FALHA (ver L14) |

## Controle por mutação (item 3)

- Base: `git archive` de 3ff2b79, com os 5 arquivos do working tree copiados por cima. `.env` fictício só com `SENTINELA_PASSO1_CTRL=1`.
- Ocorrências de `vars(sys).pop(_ATRIBUTO_ESTADO_ENV, None)`: duas por arquivo. A do pedido foi lida como a que limpa o estado antes da carga:
  - `tests/test_fluxo_cli.py`, linha 139, dentro de `main_cli` (fixture de escopo de módulo), antes de `import main`.
  - `tests/test_fluxo_web.py`, linha 233, dentro de `_fabrica` (em `montar_web`), antes de `_montar`.
  - As outras ocorrências (linhas 154 do CLI e 242 do Web) são o restauro do teardown e não foram removidas.
- Remoção por bytes, com 1 linha removida em cada arquivo. Fim de linha medido em bytes: CRLF em todas as linhas, LF puro 0 (antes e depois). `git diff --no-index` contra o working tree: 1 deleção por arquivo.
- Comando: `pytest -q -p no:cacheprovider tests/test_fluxo_cli.py tests/test_fluxo_web.py`. Resultado: 23 passed, 0 failed.
- Nenhuma das mensagens esperadas ("a carga do .env não rodou neste teste Web") apareceu.

## L14: variante que passa por construção

- Com a ordem CLI antes de Web, a remoção não produz a falha prevista. Motivo: `main_cli` tem escopo de módulo. Seu `finally` (linha 154 do CLI) restaura o estado para ausente ao fim do módulo CLI. Quando o módulo Web começa, `sys` não tem o estado "ok", então a carga roda de novo dentro do teste Web.
- Logo, a fixture Web continua provando a carga mesmo sem a limpeza da linha 233, nessa ordem. O controle não discrimina o Achado 2 como foi montado.
- Não investigado por escopo: se a falha aparece com outra ordem ou com a remoção também da linha de restauro (154). Registrar como ponto aberto para a fase 4.

## Confirmações

- Nenhum commit, `git add`, stash, checkout, reset ou push. Nada gravado no repositório além deste arquivo não rastreado.
- `ORACLE_SANDBOX` ausente em todos os comandos (`env -u ORACLE_SANDBOX`).
- O `.env` real não foi aberto. O `.env` da cópia é fictício, só com sentinela.
- Sem Oracle.
- Greps da seção "Verificação" do plano (§6) não foram rodados nesta rodada; só os do §5.

## Saídas (scratchpad)

- `C:/Users/FREDER~1/AppData/Local/Temp/claude/db29872ef7336ab6/4a6117d2-8d87-4921-86bd-6291f042baa6/scratchpad/passo0/pytest_passo1.txt`: pytest completo.
- `.../scratchpad/passo0/web_isolado_passo1.txt`: item 2.
- `.../scratchpad/passo1_ctrl/controle_mutante_limpo.txt`: item 3.
- `.../scratchpad/passo1_ctrl/mutar_passo1.py`: script de mutação.

## Item 3 refeito pela sessão principal (claude-opus-5-5)

A mutação do item 3 (remover só o `pop` de antes da carga) passa por construção: os teardowns das duas fixtures já devolvem o estado a "ausente", então a Web começa limpa depois do CLI. Desenho do controle corrigido: remover TODO o reset nas duas fixtures, ou seja, as 2 ocorrências de `vars(sys).pop(_ATRIBUTO_ESTADO_ENV, None)` em cada arquivo (antes da carga e no teardown) trocadas por `pass`. Isso equivale às fixtures de `b0ce169`, que não tinham reset.

- Cópia: `git archive HEAD` + os 5 arquivos do working tree, `.env` só de sentinela, em scratchpad `passo1_ctrl2/`. Substituições conferidas: 2 em `test_fluxo_cli.py` e 2 em `test_fluxo_web.py`.
- `pytest -q -p no:cacheprovider tests/test_fluxo_cli.py tests/test_fluxo_web.py`: **1 failed, 22 passed, 12 errors**. Os 12 errors são no teardown da Web, com `AssertionError: a carga do .env não rodou neste teste Web`. O 1 failed (`test_web_aprovador_vazio`) é `RuntimeError` do AppTest, efeito do mesmo estado herdado.
- Sem a mutação (item 2 e item 1.2): 23 passed. **Controle válido: a asserção `len(cargas) >= 1` detecta a falta de reset.**
- Variante que passa por construção (L14): a remoção só do `pop` de antes da carga, registrada acima.

Controle da correção em `tests/_guarda_env.py` (`mesmo_arquivo` com erro de stat): ao restaurar a regra antiga ("erro de stat → não é o mesmo"), `test_mesmo_arquivo_erro_de_stat_compara_por_caminho` falha (1 failed, 25 passed). Com a correção: 26 passed.
