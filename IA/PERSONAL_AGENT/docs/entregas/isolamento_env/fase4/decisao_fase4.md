# Decisão de segurança: isolamento do .env, fase 4, passo 2 (Achados 1 e 3)

Modelo: Opus 5.5 (claude-opus-5-5), subagente `seguranca`. Branch isolamento-env, HEAD 3ff2b79 (código = b0ce169).
Lido: `docs/plans/isolamento_env_fase4.md` (§1, §4 Passo 2, §5), `docs/PROCESSO.md` (§2, §7), `decisao_fase3.md`, revisão Gemini (Achados 1 e 3, §5), `fase4/passo0_reproducao.md`, blocos `carga-env` de `app.py` e `src/main.py`, `app.py:560-563`, python-dotenv 1.2.4 instalado (`dotenv/main.py`, `dotenv/parser.py`).
Escopo: só leitura e decisão. `.env` não lido. Sem ORACLE_SANDBOX, sem Oracle, sem pytest. Os fatos de Python foram conferidos em script no scratchpad (`passo2_seg/fatos.py`, `python -I`, diretório temporário, sem `.env`). O helper do Passo 1 (`tests/_guarda_env.py`, em edição pelo `mecanico`) só foi lido para levantar riscos de integração; esta decisão não depende dos detalhes dele.

## 0. Fatos verificados agora (L9)

| # | Fato | Onde |
|---|---|---|
| F1 | Blocos `carga-env` idênticos (diff vazio) | `app.py:34-81`, `src/main.py:19-66` |
| F2 | `estado = "ok"` é gravado **antes** do `finally` que descarta ORACLE_SANDBOX | `app.py:70` × `:73-75`; `src/main.py:55` × `:58-60` |
| F3 | A checagem que levanta o RuntimeError lê o estado **fora** do lock | `app.py:76`, `src/main.py:61` |
| F4 | Duas leituras do arquivo por carga (`dotenv_values` e `load_dotenv`) | `app.py:68-69`, `src/main.py:53-54` |
| F5 | `DotEnv._get_stream` usa o caminho quando ele existe, mesmo se houver `stream` | `dotenv/main.py:62-66`; conferido: `dotenv_values(f, stream=StringIO(...))` devolve o conteúdo de `f` |
| F6 | `dotenv_values`/`load_dotenv` só chamam `find_dotenv` se caminho e stream forem ambos `None` | `dotenv/main.py:424-425`, `:462-463` |
| F7 | `load_dotenv` com `override=False` só grava chave ausente de `os.environ` | `dotenv/main.py:104-108` |
| F8 | Linha malformada vira `Binding(error=True)` sem exceção; o texto inteiro é lido de uma vez; BOM removido | `dotenv/parser.py:73`, `:178-185`, `:188-191` |
| F9 | `PYTHON_DOTENV_DISABLED` só é checado em `load_dotenv` | `dotenv/main.py:418-422` |
| F10 | Windows: `open()` num diretório dá `PermissionError`; `os.stat` do diretório dá `S_ISDIR`; `os.path.isfile/isdir` são `nt._path_isfile/_path_isdir` e **não** chamam `os.stat`; `Path.is_file` usa `os.path.isfile` | scratchpad, Python 3.15.2 |
| F11 | `os._Environ.__setitem__` e `__delitem__` chamam os globais `putenv`/`unsetenv` do módulo `os` antes de mexer em `_data`. Um `putenv` que falha não deixa a chave; um `unsetenv` que falha deixa a chave | `inspect.getsource`, Python 3.15.2 |
| F12 | `UnicodeDecodeError` não é `OSError` | scratchpad |
| F13 | Streamlit 1.67.0: `ScriptControlException(BaseException)` só é levantada nos pontos de yield (chamadas `st.*`, cache, coordenador). Não há `SetAsyncExc` | `streamlit/runtime/scriptrunner_utils/exceptions.py:22`, `runtime/scriptrunner/script_runner.py:522-583` |
| F14 | Nenhum código de produção fora dos blocos lê ORACLE_SANDBOX | `git grep ORACLE_SANDBOX -- src/ app.py` |
| F15 | O `_wrapper` do harness troca o caminho pelo fictício (`_original(env_ficticio, ...)`) no HEAD e no working tree | `test_carga_env_entrada.py:43-50` (HEAD) |

## 1. Forma decidida

Invariantes (o implementador pode mudar a forma, desde que mantenha todos):
- **I1. Uma leitura, dentro de função.** `os.stat` e uma `open(caminho, encoding="utf-8")` com `.read()`, sob o lock. O texto e os valores ficam só dentro da função (regra P3a.1 da fase 3: nada do `.env` em variável de módulo nem no estado).
- **I2. Só `os.stat` e `open` tocam o caminho.** Nada de `os.path.*`, `Path.is_file/exists/read_text` (F10).
- **I3. `None` só com OSError e `os.environ` igual ao retrato.** O retrato é tirado dentro da função antes de qualquer escrita, e a comparação é feita **antes** do `finally` do descarte.
- **I4. "ok" e `_CARREGOU_AGORA` só depois do `finally`.** Uma exceção no próprio descarte (F11) deixa "falhou".
- **I5. A decisão de levantar usa estado e falha copiados sob o lock**, não o dicionário lido depois do `with`.
- **I6. Campos por tentativa zerados no começo de cada tentativa:** falha, sombreadas, malformadas, sandbox_descartada.
- **I7. `load_dotenv` continua sendo a única escrita** em `os.environ` (`override=False`, `stream=`).

Esboço de referência (texto idêntico nas duas entradas; acrescentar `import io`, `import stat` e `from dotenv.parser import parse_stream` nos imports de topo, todos de stdlib ou dotenv):

```python
def _carregar_env(caminho):
    """Uma leitura do .env (sob o lock de quem chama). Texto e valores só aqui dentro (P3a).
    Devolve (estado, falha, sombreadas, malformadas); estado None = nada foi escrito e a próxima subida tenta de novo."""
    retrato = dict(os.environ)  # antes de qualquer escrita
    try:
        try:
            modo = os.stat(caminho).st_mode  # só os.stat (no Windows os.path.isfile/isdir não passam por ele)
        except FileNotFoundError:
            texto = ""  # .env ausente: nada a carregar (comportamento de b0ce169; ver PENDENTE P1)
        else:
            if not stat.S_ISREG(modo):
                return "falhou", "NaoEArquivoRegular", (), 0  # Achado 3a: diretório, FIFO, dispositivo
            with open(caminho, encoding="utf-8") as arquivo:  # a única abertura
                texto = arquivo.read()
        sombreadas = tuple(sorted(
            nome for nome, valor in dotenv_values(stream=io.StringIO(texto)).items()
            if valor is not None and nome in os.environ and os.environ[nome] != valor
        ))
        malformadas = sum(1 for linha in parse_stream(io.StringIO(texto)) if linha.error)
        load_dotenv(stream=io.StringIO(texto), override=False)
    except OSError as exc:
        if dict(os.environ) != retrato:
            raise  # escrita parcial: quem chama marca "falhou"
        return None, type(exc).__name__, (), 0
    return "ok", None, sombreadas, malformadas


_ESTADO_ENV = vars(sys).setdefault(
    "_personal_agent_estado_env",
    {"lock": threading.Lock(), "estado": None, "falha": None, "sandbox_descartada": False, "sombreadas": (),
     "malformadas": 0},
)
_CARREGOU_AGORA = False
with _ESTADO_ENV["lock"]:
    if _ESTADO_ENV["estado"] is None:
        _ESTADO_ENV.update(estado="falhou", falha=None, sandbox_descartada=False, sombreadas=(), malformadas=0)
        _sandbox_do_shell = "ORACLE_SANDBOX" in os.environ
        _proximo = "falhou"
        try:
            _proximo, _ESTADO_ENV["falha"], _ESTADO_ENV["sombreadas"], _ESTADO_ENV["malformadas"] = (
                _carregar_env(ROOT_DIR / ".env")
            )
        except Exception as exc:
            _ESTADO_ENV["falha"] = type(exc).__name__
        finally:
            if not _sandbox_do_shell and os.environ.pop("ORACLE_SANDBOX", None) is not None:
                _ESTADO_ENV["sandbox_descartada"] = True
        _ESTADO_ENV["estado"] = _proximo  # só depois do descarte (I4)
        _CARREGOU_AGORA = _proximo == "ok"
    _ESTADO_DESTA_SUBIDA, _FALHA_DESTA_SUBIDA = _ESTADO_ENV["estado"], _ESTADO_ENV["falha"]  # sob o lock (I5)
if _ESTADO_DESTA_SUBIDA is None:
    raise RuntimeError(
        f"Carga do .env falhou nesta subida ({_FALHA_DESTA_SUBIDA}); nada do agente foi carregado e nada do .env "
        "entrou no ambiente. Nova tentativa na próxima subida (Web: recarregue a página; CLI: rode de novo)."
    )
if _ESTADO_DESTA_SUBIDA != "ok":
    raise RuntimeError(
        f"Carga do .env falhou nesta subida ({_FALHA_DESTA_SUBIDA or 'interrompida'}); "
        "nada do agente foi carregado. Corrija o .env e reinicie o processo."
    )
```

As duas mensagens começam com "Carga do .env falhou nesta subida (", que é o texto que `MENSAGEM_FALHA_CARGA` procura. Os testes distinguem os dois casos por "Nova tentativa" ou "reinicie o processo". Os dois `raise` ficam fora de `except`, então não há encadeamento (F12: o `UnicodeDecodeError` carrega bytes do arquivo em `.object` e não pode aparecer). Atualizar também o comentário de cabeçalho do bloco (`app.py:41`, `src/main.py:26`): falha de leitura sem escrita = nova tentativa; o resto continua fail-closed até reiniciar.

## 2. Itens da proposta

**Item 1 (os.stat). DECISÃO: ACEITO.**
- Só `os.stat`, pelo motivo do F10.
- `FileNotFoundError` dá texto vazio. Existe e não é `S_ISREG` dá "falhou", com a falha `NaoEArquivoRegular`. Outro OSError no stat dá `None`, se o retrato não mudou, e nessa hora ele não pode ter mudado.
- Ajuste: FIFO também passa a "falhou" (o python-dotenv aceitava FIFO, `dotenv/main.py:487`). No POSIX, abrir um FIFO bloqueia sob o lock; no Windows isso não se aplica. Fica registrado.
- Sobre a leitura literal de "OSError ⇒ None" para o `.env` ausente: ver PENDENTE P1.
- Prova: testes (c) e (c').

**Item 2 (uma abertura, OSError ⇒ None, mensagem). DECISÃO: ACEITO.**
- Mensagem definida no §1.
- O `None` vale para OSError no `stat`, no `open`, no `read` e no `close`, e também para um `putenv` que falhe já na primeira chave (F11: nada foi escrito).
- `FileNotFoundError` no `open`, depois de o `stat` ter dito "regular" (o arquivo sumiu no meio), dá `None`. A tentativa seguinte decide pelo `stat`.
- Prova: testes (a) e (b).

**Item 3 (stream, parse_stream, load_dotenv). DECISÃO: ACEITO.**
- `stream=` confirmado, então **D3 se aplica** (§4).
- `UnicodeDecodeError` (F12) e `ValueError` (NUL no `putenv`) continuam "falhou".
- Cada chamada recebe um `io.StringIO(texto)` novo, porque o `Reader` consome o stream (`parser.py:73`). Mesmo encoding e o mesmo `newline` padrão do dotenv, então o texto analisado é o mesmo.
- O residual de `PYTHON_DOTENV_DISABLED` continua (F9). Agora sombreadas e malformadas também são calculadas quando a carga está desligada, o que dá um aviso enganoso, mas só com nomes e contagem. Acrescentar isso à linha de residual do plano §7.
- Prova: (b), (d) e os D3.

**Item 4 (retrato e escrita parcial). DECISÃO: ACEITO com ajuste.**
- O retrato fica **dentro** da função (I1/I3). Como variável de módulo, ele seria uma cópia do ambiente inteiro no namespace do script.
- A comparação é feita no `except OSError` da função, antes do `finally` da entrada. Assim, ORACLE_SANDBOX gravada pelo arquivo conta como escrita e leva a "falhou".
- **C2a confirmado:** uma tentativa `None` não promove ORACLE_SANDBOX do arquivo, por duas barreiras independentes:
  1. `None` ⇒ `os.environ` igual ao retrato do início da tentativa. Nenhuma chave do arquivo ficou, e a tentativa seguinte refaz `_sandbox_do_shell` sobre o mesmo ambiente;
  2. o `finally` remove ORACLE_SANDBOX não vinda do shell em qualquer saída.
- Prova: (e) por mutação e (a) para o C2a com nova tentativa.

**Item 5 (zerar campos e momento dos avisos). DECISÃO: ACEITO com ajuste.**
- Zerar `falha`, `sombreadas`, `malformadas` e `sandbox_descartada` no começo de cada tentativa (I6). Isso é inócuo: com `None`, `sandbox_descartada` é sempre False.
- `estado` e `_CARREGOU_AGORA` são gravados só depois do `finally` (I4). `_CARREGOU_AGORA` fica True só na execução cuja tentativa terminou "ok".
- Os avisos (descarte, sombreadas, malformadas) saem **na tentativa que deu certo**:
  - log uma vez por processo; stderr na CLI;
  - `st.warning` em todo rerun depois do "ok" (`app.py:560-563`).
- Ajuste I5: copiar estado e falha sob o lock (§3a).
- Prova: (a) para o aviso uma vez só na tentativa boa, e (g) para o "ok" depois do `finally`.

**Item 6 (texto idêntico, escrito por Opus). DECISÃO: ACEITO.** Na verificação: diff vazio entre os blocos e grep do §5.

**D4. DECISÃO: ACEITO.**
- Constante `_AVISO_MALFORMADAS = "Linhas do .env com erro de sintaxe foram ignoradas. Quantidade: "` mais `str(n)`, só quando `n > 0`. Ela não contém "DESCARTADA", "ORACLE_SANDBOX" nem o prefixo das sombreadas, de que dependem `test_carga_env_entrada.py:251`, `:265` e `:369` (HEAD).
- CLI (`src/main.py`, no bloco `_CARREGOU_AGORA`): `_log_carga.warning(...)` e `print(f"[Sistema]: AVISO: {_AVISO_MALFORMADAS}{n}", file=sys.stderr)`.
- Web: `warning` no bloco `_CARREGOU_AGORA` (`app.py:98-103`) e `st.warning(...)` ao lado de `app.py:560-563`.
- O python-dotenv continua emitindo os avisos próprios, com o **número** da linha e sem o conteúdo (`dotenv/main.py:35-38`), duas vezes por linha, como em b0ce169. Os testes filtram pelo prefixo.

## 3. Perguntas

**(a) Corrida entre abas com `None`.**
- Esta é uma **janela nova** que a proposta crie sem o I5.
- Sequência: a aba A termina a tentativa com `None` e solta o lock. A aba B entra e chega a "ok". A aba A lê o estado fora do lock (F3) e segue.
- Pior caso, se B for preemptada entre "ok" e o `finally` (F2): A importa o projeto com ORACLE_SANDBOX do arquivo ainda em `os.environ`. Hoje isso tem efeito nulo em `src/` (F14), mas fere C1. Antes não existia, porque a tentativa era única e todo leitor só passava pelo lock depois dela.
- Fechada por I4 + I5: todas as transições e a leitura da decisão ficam sob o lock; "ok" e "falhou" são terminais; o `st.warning` (`app.py:560`) só roda depois de um "ok" local.
- Sem teste determinístico (ver P2). Conferência por revisão: o `raise` usa as cópias locais.

**(b) BaseException.** **DECISÃO: continua "falhou"** (o `_proximo` não chega a ser gravado).
- Uma interrupção não diz em que ponto parou, e a regra do retrato só existe no `except OSError`.
- Na CLI, Ctrl+C encerra o processo de qualquer modo. Na Web, o Streamlit não injeta exceção no bloco (F13).
- A exceção do guarda dos testes precisa falhar alto. As fixtures do Passo 1 limpam o estado por teste (Achado 2).
- Prova opcional (h).

**(c) Riscos que a proposta cria ou expõe.**
- R1: a corrida do item (a). Fechada por I4/I5.
- R2: `estado = "ok"` antes do `finally` (F2) já é um caminho fail-open hoje: um `unsetenv` que falha no descarte (F11) deixa "ok" com ORACLE_SANDBOX do arquivo. Fechado por I4; prova (g), com controle direto.
- R3: o harness mascara a mudança. Pelo F5 e pelo F15, o `_wrapper` reabriria o fictício pelo caminho, ignoraria o stream e daria 3 leituras. Exige H1/H2 (§4).
- R4: o guarda `DotEnv` deixa de cobrir a produção, porque `StringIO` não tem `name`. O redirecionamento de `open`/`os.stat` do Passo 1 passa a ser a única barreira (L13).
  - Produção do Passo 2 só depois do commit do Passo 1.
  - Grep na verificação: `git grep -n -E "import main|AppTest|from_file|runpy" -- tests/` só nos três arquivos, todos com o helper e com `ficticio`.
  - Se alguma fixture de `test_fluxo_*` afirmar sobre `aberturas_redirecionadas`, **PARE**: o arquivo está fora do Passo 2.
- R5: o texto do `.env` em variável de módulo violaria P3a. Fechado por I1; conferir na revisão.

## 4. Testes (em `tests/test_carga_env_entrada.py`, subprocesso; injeções só no filho)

Requisitos do harness:
- **H1.** Os wrappers de `load_dotenv` e `dotenv_values`:
  - com `stream`, repassam os argumentos sem mudança e registram `caminho=None` e `stream=True`;
  - sem `stream` (b0ce169), mantêm a troca pelo fictício.
- **H2.** Contar as **leituras efetivas do fictício**: toda abertura cujo alvo final seja `env_ficticio`, redirecionada ou direta. `stat` é contado à parte. Esperado: b0ce169 = 2 por processo; novo = 1.
- **H3.** Injeções configuráveis, uma vez cada:
  - `PermissionError` na 1ª leitura efetiva;
  - `OSError` em `os.putenv` para uma chave;
  - `OSError` em `os.unsetenv("ORACLE_SANDBOX")`;
  - fictício como diretório;
  - fictício ausente.
- **H4.** Primeiro afirmar que a injeção disparou (vale nas duas bases), depois a asserção principal.
- ORACLE_SANDBOX=1 só no fictício, e o filho continua sem credenciais (`_PREFIXOS`, `:21`, HEAD).

| Teste | Cenário | Asserção principal (depois o resto) | Controle contra b0ce169 |
|---|---|---|---|
| (a) `[cli,web]` OSError antes da escrita | fictício `ORACLE_SANDBOX=1` + sentinela; `PermissionError` na 1ª leitura; 2 runs | run 1 com "PermissionError" e "Nova tentativa" (H4); **run 2 sem exceção e sentinela carregada**; ORACLE_SANDBOX ausente após cada run; "DESCARTADA" 1 vez no log (CLI: 1 vez no stderr; Web: `st.warning` no run 2); `load_dotenv` 1 vez; leituras efetivas 2 | **direto**: run 2 mantém o RuntimeError (PermissionError). Mutação "tirar o `pop` do finally" falha no run 2. Com "None sem comparar o retrato" o teste passa por construção (nada foi escrito no run 1): registrar (L14) |
| (b) `[cli,web]` uma leitura | fictício normal; 2 runs | **leituras efetivas == 1**; `load_dotenv` com `stream` e caminho `None` | **direto**: 2 (H2) |
| (c) `[cli,web]` diretório | fictício é diretório; 2 runs | **os dois runs** com "NaoEArquivoRegular" e "reinicie o processo"; `stat` 1 vez (sem nova tentativa); `load_dotenv` 0 vezes | **direto**: b0ce169 sobe "ok" (StringIO vazio) |
| (c') `[cli]` ausente | fictício inexistente | sobe "ok", sem chaves e com 0 leituras | sem controle (comportamento mantido); se P1 = (B), passa a esperar "Nova tentativa" |
| (d) `[cli,web]` malformadas | `SENTINELA=1`, `LINHA MALFORMADA_FICTICIA texto_secreto_ficticio`, e por **último** `CHAVE_ABERTA="segredo_ficticio_aberto` | **ok**, sentinela carregada e **um** aviso com o prefixo e "2"; "secreto"/"segredo" ausentes do log, stderr, stdout e tela; CLI com o prefixo `[Sistema]: AVISO:` no stderr; Web com `st.warning` nos 2 runs | **direto**: sem aviso |
| (e) `[cli,web]` escrita parcial | `SENTINELA_A=1`, `SENTINELA_B=1`; `putenv` falha em `SENTINELA_B`; 2 runs | `SENTINELA_A` presente após o run 1 (H4); **run 2 com "reinicie o processo"**; leituras efetivas 1; `load_dotenv` 1 vez | b0ce169 passa (fail-closed em tudo): registrar. **Mutação** na cópia nova: trocar `if dict(os.environ) != retrato: raise` por nada (todo OSError vira `None`) faz o run 2 recarregar e o teste falhar. A variante com ORACLE_SANDBOX como 1ª chave passa sob a mutação, por causa do `finally` (L14) |
| (g) `[cli,web]` "ok" só depois do descarte | `ORACLE_SANDBOX=1` + sentinela; `unsetenv` falha 1 vez; 2 runs | run 1 com exceção (H4); **run 2 com "reinicie o processo"** | **direto**: em b0ce169 o run 2 sobe, com ORACLE_SANDBOX do arquivo em `os.environ` (F2) |
| (h) opcional `[cli]` BaseException | exceção `BaseException` própria na 1ª leitura; o harness a captura só nesta configuração | run 2 com "interrompida" e "reinicie"; leituras 1 | b0ce169 passa. Mutação "BaseException ⇒ None" falha |

**D3 (aprovado; linhas do HEAD, que vão mudar depois do Passo 1).**
- `test_oracle_sandbox_do_env_descartada`, `:255`: troca de `Path(chamada["caminho"]) == RAIZ/.env` para "a única abertura registrada pelo helper (tipo `open`/`io.open`) é `RAIZ/.env`" e "leituras efetivas == 1".
- `test_b3_nomes_sombreados_sem_valores`, `:381`: a mesma troca para `chamadas_values`.
- **Acrescentado** nos dois: a chamada recebeu `stream` e caminho `None`.
- Nenhuma outra asserção muda. C1, C2a, B4, R-F2-1, A3, B3, C3 e D6.3 continuam como estão (`len(chamadas) == 1` vale).

Greps acrescentados ao §6:
- dentro dos blocos `carga-env`, nenhum `os.path.`, `.is_file(`, `.exists(` nem `read_text`;
- `open(` aparece 1 vez por bloco;
- `load_dotenv(` aparece 2 vezes, ambas com `stream=` e `override=False`.

## 5. Desfechos da entrada (o que é recusado e com que status)

| Situação | estado | Mensagem | Próxima subida |
|---|---|---|---|
| lido e carregado | ok | — (avisos de descarte, sombreadas e malformadas, só com nomes e contagem) | não recarrega |
| ausente no `stat` | ok (sem chaves) | — | não recarrega (P1) |
| não regular | falhou | `(NaoEArquivoRegular)` … reinicie | erro fixo |
| OSError sem escrita | None | `(<Tipo>)` … Nova tentativa | tenta de novo |
| OSError com escrita parcial, UnicodeDecodeError, ValueError (NUL), outra Exception | falhou | `(<Tipo>)` … reinicie | erro fixo |
| BaseException, ou exceção no descarte | falhou | `(interrompida)` … reinicie | erro fixo |

Em nenhum caso fora de "ok" um módulo do projeto é importado.

Registros:
- `auditoria_oracle.log` ganha só o WARNING com a contagem, uma vez por processo.
- JSONL de aprovação, `OPS_KILL_AUDIT` e e-mail: sem mudança.
- Conta KILL: sem mudança, continua só `PKG_OPS_KILL.KILL_SESSION`. Nada em `oracle_dba.py`, `db/` ou `registry/`.
- A3: depois do "ok", nada mais escreve em `os.environ`. Antes do "ok", nada do projeto roda.

## 6. PENDENTE APROVAÇÃO do responsável e residuais

- **P1. `.env` ausente.**
  - Decidido (A): `FileNotFoundError` no `stat` dá "ok" sem chaves. É o comportamento de b0ce169 e o texto do plano aprovado (§4, Passo 2.1).
  - Diverge da leitura literal de "OSError ⇒ None". Risco aceito por (A): numa janela de troca do arquivo (salvar com rename, sincronização do OneDrive), a Web sobe "ok" sem chaves até reiniciar.
  - Efeito de (A): Oracle sem credenciais (ERRO_CONFIG, sem kill). Sem Ollama, o LLM cai no Gemini com a chave "local" (`app.py:173`) e o pedido do chat sai e volta recusado. Isto é inferência.
  - Alternativa (B), em uma linha: tirar o `except FileNotFoundError`. A ausência passa a "Nova tentativa", e o teste (c') inverte. **O responsável escolhe.**
- **P2.** Teste determinístico da corrida (§3a): exige semear `_personal_agent_estado_env` no filho, o que é exceção à regra P1a da fase 3. Sem essa exceção, a corrida fica "fechada por construção e revisão", como o R-F2-1.
- **P3.** Leitura rasgada durante um salvamento concorrente: é anterior a esta mudança, e a leitura única reduz a janela. Mitigação possível, fora do escopo: comparar `st_size`/`st_mtime_ns` antes e depois e tratar a diferença como `None`.
- Residuais a registrar:
  - FIFO passa a "falhou";
  - troca por FIFO entre `stat` e `open` bloqueia sob o lock (só POSIX);
  - `PYTHON_DOTENV_DISABLED` agora também com aviso enganoso;
  - avisos próprios do python-dotenv com o número da linha;
  - R4 (o guarda `DotEnv` não cobre mais a produção).
