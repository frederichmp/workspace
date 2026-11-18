# Decisão de segurança: isolamento do .env, fase 3 (passo 1-D)

Modelo: Opus 5.5 (claude-opus-5-5), subagente `seguranca`. Branch isolamento-env, HEAD c97a90f (código igual a d05577e; os commits seguintes só mexem em docs e em `tests/test_guard_sessao_sandbox.py`).
Base lida: `docs/plans/isolamento_env_fase3.md`, `docs/entregas/revisao_fases_1_2/revisao_adversarial_gemini.md`, `docs/entregas/isolamento_env/reproducao_fase3.md`, `CLAUDE.md` e `docs/PROCESSO.md` (versão de 49ad795).
Escopo: só leitura. Nenhum código editado. `.env` não lido. Sem ORACLE_SANDBOX, sem Oracle, sem pytest. Todas as linhas citadas foram reconferidas em c97a90f (L9). Versões instaladas: streamlit 1.67.0, python-dotenv 1.2.4, Python 3.15 com GIL.
Autorizações aplicadas (responsável, 2026-11-18 13:37): A3 (passo 2, expectativas listadas, nenhuma asserção enfraquecida); B3 (bloquear `dotenv_values` nas fixtures de fluxo; valores só em memória; log, tela e e-mail recebem só nomes); R-F2-1 elevado a média e fechado pelo passo 1; C2b fica como item futuro; C4 = "descartar + aviso visível".

## 0. Caminho de decisão do kill: o que muda

- Recusas, sem mudança: PARAM_INVALIDO, ERRO_CONFIG, HostInacessivelVPN, ALVO_NAO_ENCONTRADO, NAO_USUARIO, USUARIO_PROTEGIDO (`oracle_dba.py:651`), ALVO_ALTERADO (:957), APROVACAO_EXPIRADA (:992, :1411), FALHA_LOG_APROVACAO (:1520, :1534), ERRO_INTERNO e ERRO_ORACLE.
- A conta KILL continua executando só `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION` (:772), com credenciais lidas na chamada.
- Log: o passo 2 muda só **quando** o destino do `kill_approval.log` é resolvido (no import → na chamada). O ponto de resolução continua único: `_caminho_log_efetivo` (:1005-1007). Usam esse ponto:
  - `registrar_log_aprovacao_kill` (:1171);
  - `reconciliar_intencoes_orfas` (:1194);
  - `registrar_decisao_kill`, que resolve **uma vez** em :1397 e passa `destino_log` às gravações de INTENCAO e de RESULTADO (:1427, :1503, :1594, :1628). As duas fases de uma decisão vão sempre para o mesmo arquivo.
- Passo 1: depois da carga, nada mais escreve em os.environ. Isso torna estável a leitura de AGENTDBA_LOG_DIR em tempo de chamada. **O passo 1 tem de entrar antes do passo 2.**

---

## P1. Passo 1: carga única por processo com try/finally (B4, C1, R-F2-1, C2a)

### P1a. Onde fica a sentinela: CONFORME com a proposta, atributo em `sys`

- **Decisão:** um dicionário de estado em `vars(sys)`, criado com `vars(sys).setdefault("_personal_agent_estado_env", {...})`. Ele guarda o lock, o estado da carga e os avisos.
- **Por que `sys`:**
  - O Streamlit reexecuta `app.py` num namespace novo a cada rerun. Variável global do script não sobrevive ao rerun, e essa é a causa do B4.
  - `sys` é um só por processo. Os reruns, as abas (threads) e as instâncias de AppTest compartilham o mesmo `sys`.
  - O watcher de fontes do Streamlit não mexe em `sys`.
  - `st.cache_resource` não serve: o menu "Clear cache" o apaga, e isso reabriria o B4 por uma ação da interface. Além disso, ele não existe na CLI.
- **Por que não um módulo do projeto:** importar módulo do projeto antes da carga viola o I1. Um módulo do projeto também pode ser carregado duas vezes, como `tools.x` e como `src.x`, o que daria dois estados, o mesmo problema do A3.
- **Por que não variável de ambiente:**
  1. Herdada: subprocessos Python que rodassem uma entrada pulariam a própria carga e o próprio retrato de ORACLE_SANDBOX.
  2. Forjável fora do processo: o perfil do Windows vence o .env (L6). Uma variável no perfil desligaria a carga e o descarte em todos os processos.
  3. Polui justamente o que se protege: entraria nas contagens de os.environ (`test_isolamento_env.py:57-60`).
- **Lock:** `threading.Lock()` dentro do mesmo dicionário. Na criação concorrente, o `setdefault` é atômico. Com GIL, o `dict.setdefault` com chave `str` não executa código Python. No build sem GIL, as operações de dict usam seção crítica por objeto. Quem perde a corrida descarta o próprio Lock e usa o que ficou gravado. **Não usar `getattr`/`setattr`**: verificar e depois gravar não é atômico, e duas threads poderiam criar dois locks.
- Chave única e compartilhada pelas duas entradas, porque o significado é "o .env já foi carregado neste processo". Na produção, `app.py` e `main.py` nunca rodam no mesmo processo. Nos testes em processo, a segunda entrada pula a carga, e os carregadores já estão neutralizados.
- **Regra para testes:** nenhum teste lê ou grava `_personal_agent_estado_env`. Os testes de carga e de falha rodam **só em subprocesso**. Um estado "falhou" deixado no processo do pytest derrubaria as entradas de todos os testes seguintes.

### P1b. Retrato tirado uma vez e try/finally: CONFORME

- O retrato de "ORACLE_SANDBOX veio do shell?" é tirado uma única vez por processo, sob o lock e só no ramo da primeira carga.
- O estado é marcado como "falhou" **antes** do `try`, de forma pessimista: só passa a "ok" se a carga terminar.
- O `finally` remove ORACLE_SANDBOX se ela não veio do shell, também quando a carga levanta exceção (C1) ou quando chega uma `BaseException`.
- Nos reruns não há novo retrato, e por isso o resíduo de uma exceção não pode ser promovido a "do shell" (C2a).
- Janela residual, aceita: entre o momento em que `load_dotenv` grava ORACLE_SANDBOX e o `pop`, só corre o restante do laço do próprio python-dotenv (`dotenv/main.py:97-110`), sob o lock. O processo não cria subprocessos, e o Streamlit não injeta exceção assíncrona (grep de `SetAsyncExc` no streamlit 1.67: nada).
- "Filtrar ORACLE_SANDBOX antes de gravar" exigiria trocar o `load_dotenv` por um laço próprio. Isso muda a interpolação, que o `dotenv_values` faz com `override=True` (`dotenv/main.py:470`), e foge do plano aprovado. Fica como item futuro, se um dia for necessário.

### P1c. Exceção durante a carga: DECISÃO, abortar (fail-closed) e não tentar de novo

- **Na CLI**, a exceção se propaga e o processo termina. **Na Web**, todo rerun levanta o mesmo erro antes de qualquer import do projeto, até o processo ser reiniciado. Nenhuma ferramenta, conexão ou painel HITL chega a rodar.
- **A sentinela é marcada mesmo quando a carga falha**, com o estado "falhou". **O rerun seguinte não recarrega**:
  - recarregar reabriria o B4 enquanto o arquivo estiver quebrado, porque chaves acrescentadas depois entrariam;
  - também refaria o retrato de ORACLE_SANDBOX.

  A regra é a mesma da fase 1: alterar o `.env` exige reiniciar o processo.
- **Mensagem fixa**, só com o nome do tipo da exceção, nunca com valores: `RuntimeError("Carga do .env falhou nesta subida (<Tipo>); nada do agente foi carregado. Corrija o .env e reinicie o processo.")`. Ela é levantada **fora** do bloco `except`, então não há encadeamento implícito e a exceção original (ex.: `UnicodeDecodeError`, que mostra um byte) não aparece. No caso de `BaseException` (Ctrl+C), o tipo vem como "interrompida".
- **Sem rollback das outras chaves já gravadas antes da falha:** como nada passa da entrada, elas ficam inertes. A CLI morre de qualquer modo. O servidor Web não executa nada do agente. Isso evita mais código no §2.
- **Nada de logging no caminho da falha:** chamar logging antes do `basicConfig` configuraria o log de forma implícita (D2 da fase 1). O erro aparece no stderr (CLI) ou na interface e no console do Streamlit (Web).

### P1d. Estado que sobrevive aos reruns: DECISÃO, o mesmo dicionário em `sys`

Chaves do dicionário:
- `lock`;
- `estado`: `None`, `"ok"` ou `"falhou"`;
- `falha`: nome do tipo da exceção;
- `sandbox_descartada`: bool;
- `sombreadas`: tupla ordenada **só de nomes** (passo 3).

Nenhum valor do `.env` é guardado no estado.

A variável global do script `_CARREGOU_AGORA` (True só na execução que fez a carga) controla o que é emitido uma vez por processo, depois do `basicConfig`: os WARNINGs do log e o aviso no stderr da CLI. O `st.warning` da Web lê o dicionário em todo rerun.

### P1e. Nada do projeto antes da carga: CONFORME

- Antes do bloco só ficam a stdlib, mais `import threading` (acrescentar em `app.py:9-15` e em `src/main.py:2-7`), `pandas`, `streamlit`, `dotenv` e `openai`.
- O primeiro import do projeto continua depois do bloco (`app.py:66`, `src/main.py:53`).
- `from dotenv import ...` continua no import das entradas (`app.py:19`, `src/main.py:8`). É assim que o stub de `test_fluxo_cli.py:82` e de `test_fluxo_web.py:129` entra em efeito: a entrada é executada depois do stub. No passo 3 a linha passa a ser `from dotenv import dotenv_values, load_dotenv`.
- **O bloco não vai para um módulo do projeto**, pelos motivos do P1a. O texto é idêntico nas duas entradas e fica entre os marcadores `# >>> carga-env` e `# <<< carga-env`. O verificador compara as duas cópias e espera diff vazio.

### Forma final do bloco (passo 1, com as linhas do passo 3 marcadas)

Substitui `app.py:33-43` e `src/main.py:18-28`:

```python
# >>> carga-env (texto idêntico em app.py e src/main.py; isolamento do .env, fase 3)
_AVISO_SANDBOX_DESCARTADA = (
    "ORACLE_SANDBOX encontrada no .env foi DESCARTADA: só vale quando definida pelo operador no shell. "
    "Remova a chave do .env."
)
_AVISO_SOMBREADAS = "Variáveis do .env ignoradas porque o ambiente já as define com outro valor: "  # passo 3


def _nomes_sombreados(caminho):  # passo 3 (B3): só nomes; os valores não saem desta função
    return tuple(sorted(
        nome for nome, valor in dotenv_values(caminho).items()
        if valor is not None and nome in os.environ and os.environ[nome] != valor
    ))


_ESTADO_ENV = vars(sys).setdefault(
    "_personal_agent_estado_env",
    {"lock": threading.Lock(), "estado": None, "falha": None, "sandbox_descartada": False, "sombreadas": ()},
)
_CARREGOU_AGORA = False
with _ESTADO_ENV["lock"]:
    if _ESTADO_ENV["estado"] is None:
        _CARREGOU_AGORA = True
        _ESTADO_ENV["estado"] = "falhou"
        _sandbox_do_shell = "ORACLE_SANDBOX" in os.environ
        try:
            _ESTADO_ENV["sombreadas"] = _nomes_sombreados(ROOT_DIR / ".env")  # passo 3, antes da carga
            load_dotenv(ROOT_DIR / ".env", override=False)
            _ESTADO_ENV["estado"] = "ok"
        except Exception as exc:
            _ESTADO_ENV["falha"] = type(exc).__name__
        finally:
            if not _sandbox_do_shell and os.environ.pop("ORACLE_SANDBOX", None) is not None:
                _ESTADO_ENV["sandbox_descartada"] = True
if _ESTADO_ENV["estado"] != "ok":
    raise RuntimeError(
        f"Carga do .env falhou nesta subida ({_ESTADO_ENV['falha'] or 'interrompida'}); "
        "nada do agente foi carregado. Corrija o .env e reinicie o processo."
    )
# <<< carga-env
```

Depois do `basicConfig` e do silenciamento de loggers, substituindo `app.py:60-63` e `src/main.py:47-50`:

```python
if _CARREGOU_AGORA:
    _log_carga = logging.getLogger(__name__)
    if _ESTADO_ENV["sandbox_descartada"]:
        _log_carga.warning(_AVISO_SANDBOX_DESCARTADA)
        # src/main.py, passo 3 (C3): print(f"[Sistema]: AVISO: {_AVISO_SANDBOX_DESCARTADA}", file=sys.stderr)
    if _ESTADO_ENV["sombreadas"]:  # passo 3
        _log_carga.warning(_AVISO_SOMBREADAS + ", ".join(_ESTADO_ENV["sombreadas"]))
        # src/main.py, passo 3: print(f"[Sistema]: AVISO: {_AVISO_SOMBREADAS}{', '.join(_ESTADO_ENV['sombreadas'])}", file=sys.stderr)
```

No passo 1 entram o bloco sem as linhas "passo 3" e o WARNING de descarte. O passo 3 acrescenta `_nomes_sombreados`, `sombreadas`, os avisos no stderr da CLI e o `st.warning` da Web (P3c).

---

## P2. Passo 2: A3, destino do log resolvido em tempo de chamada

### Mudança em `src/tools/oracle_dba.py`

- `:30-37`: remover `DIRETORIO_LOG_APROVACAO` (:34). `CAMINHO_LOG_APROVACAO_PADRAO` (:37) passa a ser **gancho de teste** com padrão `None`: `CAMINHO_LOG_APROVACAO_PADRAO: Optional[Path] = None`. O comentário diz: "None = destino resolvido em tempo de chamada; um Path aqui (monkeypatch) fixa o destino". `DIRETORIO_LOG_PADRAO` (:33) não muda. `Path` (:13) e `Optional` (:19) já estão importados.
- `:1005-1007`: mudança pedida.

```python
def _diretorio_log_aprovacao() -> Path:
    """AGENTDBA_LOG_DIR (ou o padrão) lido no momento da chamada (A3). Não cria nada."""
    return Path(os.getenv("AGENTDBA_LOG_DIR") or DIRETORIO_LOG_PADRAO)


def _caminho_log_efetivo(caminho_log: Optional[Path]) -> Path:
    """Destino do JSONL: o caminho dado, o gancho do módulo (testes) ou o padrão resolvido agora."""
    if caminho_log is not None:
        return Path(caminho_log)
    if CAMINHO_LOG_APROVACAO_PADRAO is not None:
        return Path(CAMINHO_LOG_APROVACAO_PADRAO)
    return _diretorio_log_aprovacao() / "kill_approval.log"
```

- Não há outro uso no código: `git grep` de `DIRETORIO_LOG_APROVACAO|CAMINHO_LOG_APROVACAO_PADRAO` mostra só :34, :37 e :1007 em produção. `app.py` e `src/main.py` não usam essas constantes. `reconciliar_intencoes_orfas` (:1175, resolve em :1194) passa a ser resolvido na chamada sem nenhuma outra mudança.
- **Ganchos preservados sem alteração:** `conftest.py:140-148` (`setattr` de um atributo que continua existindo e é restaurado para `None`), `test_fluxo_cli.py:119-124` (a comparação `!=` com `None` funciona) e `test_fluxo_web.py:150-152`.
- Risco novo: AGENTDBA_LOG_DIR passa a ser lido em cada chamada. Depois do passo 1, os.environ não muda mais depois da carga. Dentro de uma decisão, o destino é um só (:1397). Um AGENTDBA_LOG_DIR relativo passa a ser resolvido contra o diretório corrente da chamada, e não mais contra o do import, que na prática é o mesmo. Aceito.
- O passo não corrige o `GEMINI_API_KEY` divergente entre as duas cópias (`gemini_router.py:18-24`, congelado no import): isso fica como item próprio no GOVERNANCA_LOG (decisão 2 do responsável).

### Expectativas de teste: lista completa

| Teste:linha | Hoje | Depois | Classificação e justificativa |
|---|---|---|---|
| `test_item1_intencao.py:1001` | `print(str(od.DIRETORIO_LOG_APROVACAO))` | `print(str(od._diretorio_log_aprovacao()))` | **Só a chamada muda.** A constante deixou de existir (A3). O valor esperado em :1031 e :1038 não muda |
| `test_item1_intencao.py:1002` | `print(str(od.CAMINHO_LOG_APROVACAO_PADRAO))` | `print(str(od._caminho_log_efetivo(None)))` | **Só a chamada muda.** O atributo agora é o gancho (`None`). O valor esperado em :1031 e :1040 não muda |
| `test_item1_intencao.py:1003` | `print(od.DIRETORIO_LOG_PADRAO)` | sem mudança | — |
| depois de `:1003` (no filho) | — | `assert os.path.exists(esperado_dir) == antes, "resolver o destino não pode criar a pasta"` | **Asserção acrescentada**: a resolução na chamada também não cria a pasta |
| `test_item1_intencao.py:1044` (docstring) | "já valia quando o módulo de produção foi importado" | "é o diretório que o módulo resolve" | Texto |
| `test_item1_intencao.py:1046` | `assert oracle_dba.DIRETORIO_LOG_APROVACAO == destino` | `assert oracle_dba._diretorio_log_aprovacao() == destino` | **Mesmo valor esperado, só o acesso muda.** A parte implícita, "definida antes do import", deixou de ser propriedade do código, porque nada mais é congelado no import. Isso não enfraquece nada: o que a asserção protegia (log de teste em tmp, fora do OneDrive e fora de `C:\AgentDBA`) continua coberto por :1047-1048, por `isolar_log_aprovacao` e pelos snapshots de `pytest_sessionfinish` (`conftest.py:151`). `conftest.py:21` continua definindo AGENTDBA_LOG_DIR antes de qualquer import, como defesa em profundidade |
| depois de `:1046` | — | para cada nome em `("src.tools.oracle_dba", "tools.oracle_dba")` presente em `sys.modules`: `assert mod._diretorio_log_aprovacao() == destino` | **Asserção acrescentada** (A3 dentro do processo) |
| `test_oracle_kill.py:657` | `assert oracle_dba.CAMINHO_LOG_APROVACAO_PADRAO == isolar_log_aprovacao` | sem mudança (o atributo continua existindo e recebe o patch) | — |
| depois de `test_oracle_kill.py:657` | — | `assert oracle_dba._caminho_log_efetivo(None) == isolar_log_aprovacao` | **Asserção acrescentada**: o gancho tem precedência sobre a resolução |
| `test_item1_intencao.py:1031, 1038-1040, 1052-1054`; `test_fluxo_cli.py:122-124`; `test_fluxo_web.py:152`; `conftest.py:147` | — | sem mudança | — |

Resultado: **nenhuma asserção removida nem enfraquecida.** Três asserções são acrescentadas, e uma tem o acesso trocado, com o mesmo valor esperado.

### Teste novo que prova A3a resolvido

Em `tests/test_carga_env_entrada.py`, parametrizado com `cli` e `web`:
- O subprocesso recebe o ambiente **sem** AGENTDBA_LOG_DIR. O `.env` fictício tem `AGENTDBA_LOG_DIR=<tmp>/dir_env`.
- O filho importa `src.tools.oracle_dba` **antes** da entrada e registra, dentro do wrapper do `load_dotenv`, que `"src.tools.oracle_dba" in sys.modules`. Isso prova que o cenário é o do A3a.
- **Asserção principal:** `src.tools.oracle_dba._caminho_log_efetivo(None) == tools.oracle_dba._caminho_log_efetivo(None) == <tmp>/dir_env/kill_approval.log`.
- Asserções seguintes: `<tmp>/dir_env` não foi criada, e a existência de `C:\AgentDBA` é a mesma antes e depois.
- **Usar `_caminho_log_efetivo(None)`**, que já existe em d05577e, e **não** `_diretorio_log_aprovacao`. Assim o controle negativo falha pela asserção e não por `AttributeError`.
- **Nunca gravar o log neste teste.** Em d05577e, a cópia `src` aponta para `C:\AgentDBA\logs`, e uma gravação criaria a pasta real.

---

## P3. Passo 3: B3 e C3

### P3a. Como funciona o B3: CONFORME, com a ordem fixada

1. Dentro do lock e do `try` do P1, **antes** do `load_dotenv`, `_nomes_sombreados(ROOT_DIR / ".env")` chama `dotenv_values` e devolve só os nomes. Uma chave entra na lista quando o arquivo tem valor (≠ `None`), o nome já existe em `os.environ` e o valor do ambiente é diferente do valor do arquivo.
   - É calculado antes da carga para que `os.environ` ainda esteja no estado anterior a ela.
   - O teste usa `os.environ` e não uma cópia em `dict`, porque no Windows `os.environ` não diferencia maiúsculas de minúsculas.
   - Os valores existem só dentro da função: nenhum é atribuído a variável de módulo nem ao estado.
2. Em seguida vem o `load_dotenv(..., override=False)`, e depois o `finally` do P1.
3. O WARNING com os nomes sai depois do `basicConfig`, uma vez por processo (`_CARREGOU_AGORA`).
4. **Tela:** os nomes também aparecem no stderr da CLI e num `st.warning` da Web, com o mesmo mecanismo do C3. A decisão do responsável cita "tela" entre os destinos permitidos, e o problema do C3 (log suprimido) vale também para o B3. E-mail: nada.
5. Uma falha no `dotenv_values` (ex.: UTF-8 inválido) cai no fail-closed do P1c. O comportamento atual já era esse, porque o `load_dotenv` falharia na mesma leitura.
6. **Restrição de texto:** a mensagem do B3 **não pode conter "DESCARTADA"**. Com shell "0" e arquivo "1", ORACLE_SANDBOX entra na lista de sombreadas, e `test_carga_env_entrada.py:105` exige que não haja aviso com "DESCARTADA".
7. Limitações aceitas: o arquivo é lido duas vezes, e uma alteração entre as duas leituras afeta só o aviso. Uma chave com `${VAR}` é comparada pelo valor que o dotenv interpola, e o aviso é só informativo.

### P3b. Interpretação do bloqueio: CONFORME com a leitura do coordenador, com um ajuste

- **Ajuste:** o guarda fica no **construtor do leitor** e não na função.
  - A fixture troca `dotenv.dotenv_values` por um stub que não lê nada e devolve `{}` (o `load_dotenv` já é um no-op).
  - Um guarda separado substitui `dotenv.main.DotEnv.__init__`: se `dotenv_path` resolve para `RAIZ/.env`, o guarda **registra numa lista e levanta `AssertionError` antes de qualquer `open`**.
  - O teardown da fixture faz `assert leituras_env_reais == []`, e isso **falha o teste**.
- Todo caminho de leitura passa por `DotEnv(dotenv_path=...)`: `load_dotenv`, `dotenv_values`, o `find_dotenv` implícito e uma função original ligada antes do stub. Por isso "chamado com o .env real" vale para qualquer leitor.
- Na Web, a exceção dentro do AppTest é capturada pelo Streamlit. É a lista que faz o teste falhar.
- Por que não "o stub falha quando é chamado com o caminho real": a entrada **sempre** chama `dotenv_values(ROOT_DIR/".env")`, ou seja, com o caminho real. Um stub assim derrubaria a primeira execução da entrada no processo do pytest, a menos que os testes marcassem a sentinela privada como já carregada. Isso acoplaria os testes ao estado do §2 e é vedado no P1a.
- Na nossa leitura, o texto do responsável se cumpre assim: nenhum leitor chega ao `.env` real, e se chegar, o teste falha. Registrar essa leitura no GOVERNANCA_LOG.

**Todos os testes que importam `main` ou rodam `app.py`** (`git grep "import main|AppTest|from_file|runpy" -- tests/`: só estes três):

| Arquivo:linha | Execução | O que fazer |
|---|---|---|
| `tests/test_fluxo_cli.py:78-112` (`main_cli`; `import main` em :105) | no processo do pytest | stub de `dotenv_values` e guarda `DotEnv`, ao lado de :81-82. Asserção da lista vazia logo depois do import e no teardown (:107-112) |
| `tests/test_fluxo_web.py:115-187` (`_montar`; AppTest em :182-184) | no processo do pytest | stub e guarda ao lado de :127-129. A lista vai em `amb`, e `montar_web` (:191-203) faz `assert amb.leituras_env_reais == []` junto do `destinos_inesperados` (:203) |
| `tests/test_carga_env_entrada.py:19-66` (`_SCRIPT`; `import main` em :55, AppTest em :57-58) | subprocesso | **Hoje só redireciona `load_dotenv` (:25-37).** Sem redirecionar também `dotenv_values`, depois do passo 3 o filho **leria o `.env` real**: os valores ficariam na memória, e o WARNING do B3 imprimiria os nomes reais nas saídas capturadas. Fazer um wrapper de `dotenv_values` para o fictício, que registra o caminho e a contagem; o guarda `DotEnv` para o caminho real; `leituras_reais` no JSON, com asserção `== []` em todos os testes. **Isso entra no passo 1** (o arquivo está na lista do passo 1 e a mudança é inócua antes do passo 3) |

Fora da lista, sem mudança:
- `test_item1_intencao.py:991-1004` importa só `src.tools.oracle_dba`. O módulo `dotenv` falso não tem `dotenv_values`, então se um dia a entrada for importada ali, o import falha e o teste quebra de forma visível.
- `test_isolamento_env.py:24` importa só módulos de teste.
- `test_env_em_execucao.py:7-8` importa só `src.tools`. O D6.2 do passo 4 traz os guardas próprios dele e pode reaproveitar o mesmo guarda `DotEnv`.

**Ordem obrigatória no passo 3:** as fixtures (`test_fluxo_cli` e `test_fluxo_web`) recebem o stub e o guarda **antes** da edição de produção. Nunca rodar pytest com a produção já chamando `dotenv_values` e as fixtures ainda sem proteção, porque a primeira execução da entrada dentro do pytest leria o `.env` real.

Item futuro, no §2: um guarda `DotEnv` para a sessão inteira, no conftest, instalado depois da carga sandbox de `conftest.py:62-66`. Ele protegeria também os testes futuros que importarem uma entrada sem fixture.

### P3c. C3, onde aparecem os avisos: DECISÃO

- **CLI:** `print(f"[Sistema]: AVISO: {_AVISO_SANDBOX_DESCARTADA}", file=sys.stderr)`, uma vez, no bloco `_CARREGOU_AGORA` depois do `basicConfig` (`src/main.py:44-46`). Não depende do logging, então sobrevive a um logger raiz configurado em ERROR. O aviso do B3 vai do mesmo modo.
- **Web:** `st.warning(_AVISO_SANDBOX_DESCARTADA)` e, se houver nomes sombreados, `st.warning(_AVISO_SOMBREADAS + ", ".join(...))`, **logo depois de `st.set_page_config(...)` (`app.py:512-517`) e antes da inicialização do `session_state` (`app.py:519`)**.
  - Os avisos aparecem em **todo rerun**, enquanto `_ESTADO_ENV["sandbox_descartada"]` for verdadeiro, ou seja, até reiniciar o processo.
  - O streamlit 1.67.0 aceita `set_page_config` em qualquer posição e mais de uma vez (`streamlit/commands/page_config.py:129`). Mesmo assim, o aviso vem depois dele para manter a configuração da página primeiro.
  - O log do mesmo aviso sai uma vez por processo.
- Texto fixo, sem valor: a constante `_AVISO_SANDBOX_DESCARTADA` do P1. Ela continua contendo "ORACLE_SANDBOX" e "DESCARTADA", que `test_carga_env_entrada.py:92` usa. O sufixo "Remova a chave do .env." atende o C4.

---

## P4. Testes novos e controle negativo contra d05577e

**Como fazer o controle:**
1. Gerar a cópia com `git archive d05577e IA/PERSONAL_AGENT` em %TEMP% e extrair com `tar --force-local` (§5.4). Na cópia não há `.env` real.
2. Sobrescrever `tests/test_carga_env_entrada.py` da cópia com a versão do working tree. Conferir que o `diff` entre as duas não está vazio (L3).
3. Rodar `env -u ORACLE_SANDBOX PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -rs -p no:cacheprovider tests/test_carga_env_entrada.py -k <ids>`.
4. **Resultado válido:** FAILED com `AssertionError` na asserção principal. Um erro do harness (filho com returncode ≠ 0, ImportError ou AttributeError) **não vale** como controle negativo.

**Regras para o harness:**
- O filho sempre envolve a entrada em `try/except Exception` e sempre imprime o JSON, porque em d05577e o `import main` levanta `ValueError` no cenário C1.
- A asserção principal (comportamento) vem **primeiro**. As contagens de chamadas vêm depois. Exemplo: em d05577e não existe chamada a `dotenv_values`, e o teste não pode falhar por esse motivo antes da asserção principal.
- ORACLE_SANDBOX=1 aparece só no fictício lido pelo subprocesso. O caso de shell usa "0".
- Dados de teste com nomes neutros (SENTINELA_*). O único ORACLE_* fictício é `ORACLE_DSN` no B3, com a rede bloqueada.
- As saídas brutas vão para `docs/entregas/isolamento_env/fase3_controles.md`.

| Passo | Teste (em `tests/test_carga_env_entrada.py`) | Cenário | Asserção principal | Por que falha em d05577e |
|---|---|---|---|---|
| 1 | `test_b4_web_chave_nova_entre_reruns_nao_entra` | fictício `SENTINELA_FASE3=1`; run 1; acrescentar `SENTINELA_TARDIA_FASE3=1`; run 2 | `SENTINELA_TARDIA_FASE3` ausente depois do run 2. Depois: `load_dotenv` chamado 1 vez | o rerun recarrega (reprodução B4) |
| 1 | `test_c1_nul_nao_deixa_oracle_sandbox[cli,web]` | bytes `ORACLE_SANDBOX=1\nSENTINELA_FASE3=1\nVALOR_NUL_FICTICIO=a\x00b\n`. Web: 2 runs. CLI: import, `sys.modules.pop("main")`, import de novo | ORACLE_SANDBOX ausente depois de cada run ou import. Depois: as duas tentativas trazem a mensagem fixa "Carga do .env falhou" (`at.exception` ou a exceção capturada), e `load_dotenv` é chamado 1 vez | fica `'1'` (reprodução C1) |
| 1 | `test_c2a_rerun_apos_falha_nao_promove_a_shell[web,cli]` | run 1 com NUL; tirar a linha NUL do fictício, mantendo ORACLE_SANDBOX=1; run 2 (CLI: re-import) | ORACLE_SANDBOX ausente depois do run 2. Depois: o run 2 continua com o erro fixo (fail-closed) e `load_dotenv` é chamado 1 vez | o run 2 recarrega sem erro, vê `'1'` como "do shell" e o mantém |
| 1 | `test_r_f2_1_duas_sessoes_uma_carga` (web) | fictício ORACLE_SANDBOX=1 e SENTINELA; duas instâncias de AppTest no mesmo filho | `load_dotenv` chamado **1** vez no processo. Depois: ORACLE_SANDBOX ausente | 2 chamadas. A intercalação entre threads não é testável de forma determinística: fica fechada por construção (lock e retrato único) e isso é declarado no log |
| 2 | `test_a3_src_tools_antes_da_entrada_mesmo_destino[cli,web]` | ver P2 | os dois `_caminho_log_efetivo(None)` iguais a `<tmp>/dir_env/kill_approval.log` | a cópia `src` aponta para `C:\AgentDBA\logs\kill_approval.log` (reprodução A3) |
| 3 | `test_b3_nomes_sombreados_sem_valores[cli,web]` | shell `ORACLE_DSN=dsn_shell_ficticio` e `SENTINELA_IGUAL=igual`; fictício `ORACLE_DSN=dsn_arquivo_ficticio`, `SENTINELA_IGUAL=igual` e `SENTINELA_FASE3=1` | um WARNING contém `ORACLE_DSN`. Depois: esse aviso não traz `SENTINELA_IGUAL`; `dsn_` não aparece no log capturado, no stdout, no stderr nem nos elementos `at.*`; `os.environ["ORACLE_DSN"] == "dsn_shell_ficticio"`; o aviso visível (stderr ou `at.warning`) contém `ORACLE_DSN`; `dotenv_values` é chamado 1 vez com `RAIZ/.env`; `leituras_reais == []` | sem aviso |
| 3 | `test_c3_cli_aviso_em_stderr` | fictício ORACLE_SANDBOX=1 | `_AVISO_SANDBOX_DESCARTADA` em `res.stderr` | sem stderr |
| 3 | `test_c3_cli_aviso_com_raiz_em_error` | o filho chama `logging.basicConfig(level=logging.ERROR)` antes do `import main` | aviso em `res.stderr` | sem stderr; o log é suprimido |
| 3 | `test_c3_web_st_warning_em_todo_rerun` | fictício ORACLE_SANDBOX=1; 2 runs | `at.warning` contém o texto fixo no run 1 **e** no run 2 | sem `st.warning` |

Também valem:
- Os testes existentes `test_oracle_sandbox_do_env_descartada` e `test_oracle_sandbox_do_shell_prevalece` (:86-105) continuam passando sem mudança de expectativa.
- Os testes adaptados do P2 não têm controle negativo próprio: em d05577e eles falham por API (`_diretorio_log_aprovacao` ausente), o que não prova nada. Quem prova o passo 2 é o teste A3.

**Verificação acrescentada ao §6 do plano:**
- `git grep -n -E "load_dotenv\(|dotenv_values\(" -- 'src/*.py' app.py`: só dentro dos blocos `carga-env` de `app.py` e `src/main.py`.
- Os blocos entre `# >>> carga-env` e `# <<< carga-env` são idênticos nas duas entradas (diff vazio).
- `git grep -n "_personal_agent_estado_env" -- '*.py'`: só `app.py` e `src/main.py`, nunca `tests/`.
- `git grep -n DIRETORIO_LOG_APROVACAO -- '*.py'`: nada.
- Revisão manual: todo `warning`, `print` ou `st.warning` com `sombreadas` usa só `", ".join(nomes)`.
- Esperado: **16 skipped**, 0 failed, passed = 199 + testes novos.

## Ordem de execução e commits (um por passo, em sequência; nunca dois agentes em app.py, main.py ou oracle_dba.py)

1. **Passo 1:**
   - `mecanico`: harness de `test_carga_env_entrada.py` (redireciona `load_dotenv` e `dotenv_values`, guarda `DotEnv`, filho que não quebra, opções de vários runs, sessões, pré-import e nível da raiz) e os testes do passo 1.
   - Controle negativo em d05577e.
   - Sessão principal (Opus): bloco das duas entradas.
   - pytest, e depois commit.
2. **Passo 2:**
   - Sessão principal: `oracle_dba.py`.
   - `mecanico`: adaptações da tabela do P2 e o teste A3.
   - Controle negativo, e depois commit.
3. **Passo 3:**
   - `mecanico`: **primeiro** o stub e o guarda nas fixtures de fluxo, depois os testes B3 e C3.
   - Controle negativo.
   - Sessão principal: `dotenv_values`, sombreadas, stderr e `st.warning`.
   - pytest, e depois commit.

## Residuais e itens futuros
- C2b (opt-in por invocação no pytest), R-F2-2, GEMINI_API_KEY divergente entre as duas cópias, duplicação `tools.*` × `src.tools.*` e `GenerativeModel` criado no import: ficam como estão, fora de escopo.
- Item futuro: guarda `DotEnv` para a sessão inteira no conftest (P3b).
- Item futuro: filtrar ORACLE_SANDBOX antes de gravar, só se a janela do P1b deixar de ser aceitável.
- Observação: `PYTHON_DOTENV_DISABLED` no perfil desliga o `load_dotenv` sem aviso, mas não o `dotenv_values`. O efeito é fail-closed (sem credenciais). Sugestão: incluir `PYTHON_DOTENV_` na varredura do perfil do §5, passo 0.
