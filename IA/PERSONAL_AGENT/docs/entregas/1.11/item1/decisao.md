# Item 1: ordem da aprovação (INTENCAO antes do kill). Decisão

Status: DECISÃO DO seguranca, aguardando conferência do responsável. Nenhum código alterado.

- **Autor:** subagente `seguranca`, modelo **claude-opus-5-5** (Claude Opus 5.5), em 2026-11-17.
- **Base lida:** HEAD `a1e8d30`. Esse commit só altera `docs/GOVERNANCA_LOG.md` sobre `5b8066e`, e `git diff 5b8066e HEAD -- src app.py tests` sai vazio. Logo, as linhas citadas valem para `5b8066e`. O `aa9a0a5` (item 6, **NÃO ACEITO**) está no HEAD. A seção e) diz o que muda se ele for revertido.
- **Fontes:** `CLAUDE.md`; `docs/plans/1.11.md` (decisões 1 e 2, item 1 nas linhas 34-69 e item 7 na linha 151); `docs/entregas/1.11/item6/implantacao.md` §1.1; `docs/entregas/1.11/v2/origem_e_autoria.md`.
- **O que não foi feito:** nada foi executado. Não li `.env`, não conectei ao Oracle e não rodei pytest.

---

## 0. Caminho de decisão atual (o que existe hoje)

| # | Passo | Arquivo:linha | Conexão |
|---|---|---|---|
| 1 | Validação local de inst_id/sid/serial | `oracle_dba.py:1320` | nenhuma |
| 2 | **Pré-consulta DIAG** (o painel é montado com ela) | `oracle_dba.py:1341` → `consultar_alvo_sessao_diag` (sonda TCP em 556, `connect` em 568) | DIAG |
| 3 | Prompt / painel; **decisão humana** | CLI: `oracle_dba.py:1417` → `main.py:110-141`. Web: `app.py:245-262` (pendência), clique → `app.py:324` | nenhuma |
| 4 | Validação, `instante_decisao`, aprovador vazio e TTL nº 1 | `oracle_dba.py:1164-1181` | nenhuma |
| 5 | Ramo não aprovado: 1 linha gravada e retorno | `oracle_dba.py:1183-1234` | nenhuma |
| 6 | `id_intervencao = uuid4().hex` (vem do aa9a0a5) | `oracle_dba.py:1238` | nenhuma |
| 7 | `executar_kill_verificado`: reconsulta, hash, elegibilidade e `matar_sessao_oracle` | `oracle_dba.py:1239` → 953 / 974 / 995 / 1017 | DIAG e depois KILL |
| 8 | **Única linha do log, gravada DEPOIS do kill** | `oracle_dba.py:1253-1263` | — |
| 9 | Log da aplicação e e-mail | `oracle_dba.py:1264-1282` | SMTP |

**Defeito (achado 1.1):**
- O passo 8 vem depois do 7. Se o log falhar, o kill já aconteceu.
- A gravação (`oracle_dba.py:1068-1069`) não chama `flush` nem `fsync`.
- No Windows o arquivo é aberto em modo texto, e cada linha sai em CRLF.

### 0.1 Recusas, o que vai ao log e o que a conta KILL executa (depois da mudança)

| Momento | Recusas | JSONL `kill_approval.log` | Conta KILL |
|---|---|---|---|
| Antes da decisão | `PARAM_INVALIDO` (1320); na pré-consulta: `ALVO_NAO_ENCONTRADO`, `NAO_USUARIO`, `USUARIO_PROTEGIDO`, `ERRO_CONFIG`, `HostInacessivelVPN`, `ERRO_ORACLE` (1341-1363) | nenhuma linha, porque ainda não há decisão; só `logger.warning` (1322, 1344). **Sem mudança** | não tocada |
| Na decisão | `SEM_IDENTIFICACAO`, `REJEITADO_PELO_APROVADOR`, `TIMEOUT` / `APROVACAO_EXPIRADA` (1171-1185) | 1 linha `RESULTADO` | não tocada |
| Falha da INTENCAO | `FALHA_LOG_APROVACAO` | nenhuma linha garantida (ver a4) | não tocada |
| Depois da INTENCAO, antes da KILL | na reconsulta: `ALVO_NAO_ENCONTRADO`, `ERRO_CONFIG`, `HostInacessivelVPN` e `ERRO_ORACLE` da DIAG (955-972); `ALVO_ALTERADO` (975-993); `NAO_USUARIO` e `USUARIO_PROTEGIDO` (995-1008); **TTL nº 2** com `APROVACAO_EXPIRADA` (novo); `PARAM_INVALIDO` local (716-745); `ERRO_CONFIG` da KILL (752-764); `HostInacessivelVPN` (767-782); `ERRO_INTERNO` (novo) | `INTENCAO` + `RESULTADO` | não tocada |
| Conta KILL | status do PKG (`ENCERRADA`, `MARCADA_PARA_KILL`, `NAO_USUARIO`, `USUARIO_PROTEGIDO`, `ALVO_NAO_ENCONTRADO`, `PROPRIA_SESSAO`, `PARAM_INVALIDO`, `ALVO_DIVERGENTE` (v2)); `ERRO_ORACLE` (842-855); nome da classe da exceção (856-868) | `INTENCAO` + `RESULTADO` | ver abaixo |

**O que a conta KILL executa:**
- O Python faz **uma única** chamada, `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION`: um `connect` e um `execute` com binds nomeados, em `oracle_dba.py:788-822`. Não executa SQL de sessão.
- No banco, `STARTUP_KILL` tem só CREATE SESSION e EXECUTE no pacote (plano, linha 26).
- O item 1 não muda nada disso. Muda apenas **quando** esse ponto pode ser alcançado.

---

## a) Gravação durável da INTENCAO

### a1. Rotina de gravação

**DECISÃO:** uma função nova, `_gravar_linha_jsonl_duravel(caminho_log, registro)`, passa a ser o **único** ponto de escrita do `kill_approval.log`. Ela grava todas as linhas, INTENCAO e RESULTADO, inclusive REJEITADO/TIMEOUT.
- **Onde:** logo antes de `registrar_log_aprovacao_kill` (`oracle_dba.py:1025`). Substitui as linhas 1053 e 1068-1069.
- **Montagem separada:** a montagem do dict sai para uma função pura, `_montar_registro_aprovacao_kill` (hoje em 1055-1066). Assim, quem chama tem o registro serializado na mão mesmo quando a gravação falha (ver c3).
- **Assinatura preservada:** `registrar_log_aprovacao_kill` passa a ser `_montar_registro_aprovacao_kill` seguida de `_gravar_linha_jsonl_duravel`.

Chamadas exatas:

```python
# topo do módulo (imports em oracle_dba.py:7-17; constantes perto de :29)
import threading
_LOCK_LOG_APROVACAO = threading.Lock()
_FSYNC_DIRETORIO = os.name == "posix"   # Windows: False (ver a2)

def _fsync_diretorio(diretorio: Path) -> None:
    fd = os.open(diretorio, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def _gravar_linha_jsonl_duravel(caminho_log: Path, registro: Dict[str, Any]) -> None:
    # 1. serializa e codifica ANTES de abrir: erro de encoding não toca o arquivo
    dados = (json.dumps(registro, ensure_ascii=False, default=str) + "\n").encode("utf-8", errors="strict")
    with _LOCK_LOG_APROVACAO:
        caminho_log.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho_log, "a+b") as f:          # binário, append; open builtin (os testes o substituem)
            fim = f.seek(0, os.SEEK_END)
            if fim > 0:
                f.seek(fim - 1)
                if f.read(1) != b"\n":
                    dados = b"\n" + dados              # isola uma linha parcial anterior
            f.write(dados)
            f.flush()
            os.fsync(f.fileno())
        # o close do `with` acontece aqui; uma exceção do close também conta como falha
        if fim == 0 and _FSYNC_DIRETORIO:
            _fsync_diretorio(caminho_log.parent)       # arquivo novo: entrada de diretório durável
```

Justificativa de cada escolha:
- **Modo `a+b`, binário:**
  - os bytes gravados são exatos e não passam pela tradução `\n`→`\r\n` do Windows;
  - `BufferedRandom.write` só retorna depois de escrever tudo; se não conseguir, levanta exceção;
  - o `+` serve só para ler o último byte;
  - com `O_APPEND`, toda escrita vai para o fim, qualquer que seja a posição de leitura.
- **Encoding:** UTF-8 explícito, com `errors="strict"`, aplicado antes do `open`. Um surrogate solto, por exemplo, levanta exceção antes de o arquivo ser tocado. `ensure_ascii=False` continua como hoje (`oracle_dba.py:1069`).
- **Newline:** `b"\n"` literal. O `json.dumps` escapa todo caractere de controle, então cada registro ocupa exatamente uma linha física.
- **Linhas antigas:** o log real tem linhas CRLF gravadas antes desta mudança. Isso é inofensivo:
  - `json.loads` aceita `\r` como espaço em branco;
  - os testes leem com `splitlines()`.
- **Separador defensivo:** depois de um `write` ou `flush` interrompido no meio (ENOSPC, por exemplo), o arquivo pode terminar sem `\n`. Sem o separador, a linha seguinte se colaria na parcial e as duas ficariam ilegíveis. Com ele, a parcial fica isolada numa linha própria, que o auditor reconhece como inválida (c4).
- **`flush` e `os.fsync(f.fileno())`:**
  - o `flush` entrega o buffer do Python ao SO;
  - o `fsync` leva o conteúdo do SO ao disco;
  - no Windows, `os.fsync` vira `_commit`, que vira `FlushFileBuffers`.
- **Lock de módulo:** no Streamlit, cada sessão de navegador roda em uma thread do mesmo processo. No Windows, o append do CRT posiciona no fim e escreve em duas operações, e não há garantia de atomicidade entre threads. O lock serializa as gravações do processo. Duas aplicações gravando ao mesmo tempo (CLI e Web, por exemplo) ficam como risco residual (f).

### a2. fsync do diretório

**DECISÃO:** fazer fsync do diretório **só em POSIX** e **só quando o arquivo era novo** (`fim == 0`). No Windows, não fazer nenhuma chamada sobre o diretório.
- **POSIX:** sem esse fsync, a entrada do diretório do arquivo recém-criado pode se perder numa queda de energia, mesmo depois do fsync do arquivo. Por isso: `os.open(dir, O_RDONLY|O_DIRECTORY)`, depois `os.fsync`, depois `os.close`.
- **Windows:** `os.open` sobre um diretório levanta `PermissionError`, o que faria falhar a primeira gravação de toda instalação. Não existe chamada portável em Python para isso, que exigiria `CreateFile` com `FILE_FLAG_BACKUP_SEMANTICS`. O NTFS registra os metadados em journal, e `FlushFileBuffers` sobre o arquivo cobre os dados e os metadados dele.
- **O que fica como residual:** a durabilidade da entrada de diretório no Windows é a que o NTFS garante, sem chamada explícita.
- **Também residual:** se `mkdir` acabou de criar `data/logs/`, a entrada desse diretório dentro de `data/` não recebe fsync. Isso só acontece na primeira execução de uma instalação.
- **Para teste:** `_FSYNC_DIRETORIO` e `_fsync_diretorio` são nomes de módulo, para que o teste possa substituí-los sem abrir um diretório real e sem skip de plataforma (d, T5).

### a3. Campos da linha INTENCAO (e de todas as linhas)

**DECISÃO:** a linha mantém o esquema atual (`oracle_dba.py:1055-1064`) e ganha dois campos obrigatórios: `fase` e `id_intervencao`. Nenhum outro campo novo.

| Campo | INTENCAO | Regra |
|---|---|---|
| `timestamp` | ISO-8601 UTC com fuso, no momento da gravação (`datetime.now(timezone.utc)`, como em 1056) | o relógio injetável do TTL **não** é usado aqui; o item 7 também não muda isso |
| `fase` | `"INTENCAO"` | obrigatório e keyword-only, **sem default**; só `"INTENCAO"` ou `"RESULTADO"`, qualquer outro valor dá `ValueError` |
| `id_intervencao` | `uuid.uuid4().hex` | obrigatório, keyword-only, sem default; precisa casar com `^[0-9a-f]{32}$` (reusa `_REGEX_REF_APROVACAO`, `oracle_dba.py:56`); fora disso, `ValueError` |
| `aprovador` | aprovador limpo, não vazio | como hoje |
| `decisao` | `"APROVADO"` | INTENCAO com outra decisão dá `ValueError` |
| `resultado_banco` | `null` | INTENCAO com valor diferente de `None` dá `ValueError` |
| `motivo` | `null` | |
| `hash_payload`, `parametros`, `alvo` | como hoje | o `alvo` é o preparado (`oracle_dba.py:1140`) |

- **Onde nasce o id:** o `id_intervencao` passa a ser gerado **antes** do ramo da linha 1183, então REJEITADO e TIMEOUT também o recebem. O plano pede o campo "em todos os registros" (linha 44).
- **Quando a validação roda:** antes do `open`. Uma linha malformada nunca chega ao arquivo e, na INTENCAO, cai em `FALHA_LOG_APROVACAO`.

### a4. Efeito de cada falha da gravação da INTENCAO

**DECISÃO:** **qualquer** `Exception` dentro de `registrar_log_aprovacao_kill(fase="INTENCAO")` dá o desfecho `FALHA_LOG_APROVACAO`. Isso vale para validação, encode, `mkdir`, `open`, `seek`/`read`, `write`, `flush`, `fsync`, `close` e fsync do diretório. Não há nova tentativa, nem gravação de RESULTADO, nem tentativa de "consertar" o arquivo.
- **Onde:** um `try/except Exception` em volta da chamada nova, inserida entre `oracle_dba.py:1238` e `:1239`.
- **`BaseException` não é capturada aqui.** `KeyboardInterrupt` durante a INTENCAO se propaga, e isso é seguro, porque ainda nada foi conectado depois da decisão.

| Falha em | Estado possível do arquivo | Conclusão |
|---|---|---|
| validação / encode / `mkdir` / `open` (caminho é diretório: `IsADirectoryError` em POSIX, `PermissionError` no Windows) | intacto | nada gravado |
| `write` / `flush` | **linha parcial** no fim, ou nada | a próxima gravação fica isolada pelo separador (a1) |
| `fsync` levanta `OSError` com o `write` já no buffer do SO | linha **completa e visível**, mas **sem garantia de persistência** | pode existir uma INTENCAO sem RESULTADO |
| `close` levanta depois de um fsync bem-sucedido | linha completa e provavelmente durável | trata-se como falha mesmo assim (fail-closed) |
| fsync do diretório (POSIX, arquivo novo) | linha completa; a entrada do diretório não está garantida | idem |

Justificativa:
- Em todos os casos falta a **prova durável** de que a aprovação foi registrada antes da ação, que é o motivo da decisão 1.
- Distinguir "linha provavelmente gravada" de "não gravada" não muda o desfecho. Só tornaria o código mais complexo.

### a5. Desfecho `FALHA_LOG_APROVACAO`

**DECISÃO:**
- **Retorno de `registrar_decisao_kill`:**
  - `decisao="APROVADO"` (a decisão humana existiu), `resultado_banco=None`, `executado=False`, `motivo="FALHA_LOG_APROVACAO"`;
  - `falha_registro="INTENCAO"`, `registro=None`;
  - `assunto_email=None`, `email_enviado=None`, `email_detalhe=None`;
  - `id_intervencao=<id>`.
  - Os dois últimos campos (`falha_registro` e `id_intervencao`) são novos no dict e servem só para a tela.
- **`resultado_tool` para o LLM:** `{"status":"abortado","decisao":"APROVADO","motivo":"FALHA_LOG_APROVACAO","resultado_banco":null,"executado":false,"mensagem":"Falha ao gravar o registro de aprovação; intervenção NÃO executada. Nenhuma chamada à conta KILL foi feita."}`. **Sem** `id_intervencao`, como em `oracle_dba.py:1286`.
- **`logger.error`:** uma linha só, sem a mensagem da exceção. A mensagem de um `OSError` traz o caminho e pode trazer outros detalhes, por isso só tipo e errno:
  `AUDITORIA HITL: FALHA_LOG_APROVACAO ({canal}) | id_intervencao={id} | inst_id=..., sid=..., serial=... | Hash={hash} | aprovador={aprovador} | erro={type(exc).__name__} errno={getattr(exc,'errno',None)} | KILL NAO EXECUTADO`.
- **Tela:**
  - CLI (`main.py:144-166`): ramo novo **antes** de `elif desfecho["executado"]` (155), em vermelho: `Intervenção APROVADA por '<aprovador>', mas NÃO EXECUTADA: falha ao gravar o registro de aprovação (FALHA_LOG_APROVACAO). Nenhuma chamada à conta KILL foi feita. Incidente registrado no log da aplicação (id_intervencao=<id>).`
  - Web (`app.py:362-385`): ramo novo antes de 374, com o mesmo texto em `st.error`.
- **E-mail:** **nenhum**, pela decisão 2. A condição é: não chegar a `montar_notificacao_kill` nem a `enviar_alerta_email` (`oracle_dba.py:1272-1282`).

### a6. INTENCAO sem RESULTADO depois de um `FALHA_LOG_APROVACAO`

**DECISÃO:** não se tenta gravar um RESULTADO depois de uma falha da INTENCAO. A ligação fica no log da aplicação, pelo `id_intervencao` do `logger.error` (a5). O auditor que encontrar uma INTENCAO sem RESULTADO procura esse id no log da aplicação:
- **Se achar `FALHA_LOG_APROVACAO` com o mesmo id:**
  - conclusão: **não executado**. A conta KILL não foi chamada, e o código prova isso pelos testes T2 e T1;
  - a INTENCAO é o resto de uma gravação que falhou depois do `write` (fsync ou close);
  - confirmação: **não** deve haver linha em `OPS_KILL_AUDIT` para o alvo (consulta em c4);
  - se houver, é defeito de código e incidente de severidade máxima.
- **Se não achar:** segue a regra geral de c4 (desfecho desconhecido).

Justificativa: uma segunda escrita no mesmo armazenamento que acabou de falhar é a que tem mais chance de falhar de novo ou de deixar outra linha parcial. O id no log da aplicação fecha o caso sem esse risco.

---

## b) Recusa antes de qualquer conexão posterior à decisão humana

### b1. Sequência com falha da INTENCAO

**DECISÃO:** a INTENCAO é gravada **antes** de `executar_kill_verificado`, e portanto antes da reconsulta DIAG, da sonda TCP e de qualquer `getenv` da KILL. Isso confirma o plano, linha 40.

- **CLI:**
  1. `conduzir_kill_hitl` (1403) chama `preparar_intervencao_kill`: validação (1320), depois **DIAG nº 1** (1341: sonda 556 e `connect` 568);
  2. `solicitar_aprovacao` (1417) é a **decisão**;
  3. `registrar_decisao_kill` (1418): validação, `instante_decisao` (1164-1167), aprovador e TTL nº 1 (1171-1181), `id` gerado;
  4. **INTENCAO** levanta exceção, e a função retorna `FALHA_LOG_APROVACAO`;
  5. **não alcança** 1239: sem reconsulta DIAG, sem `verificar_acessibilidade_host`, sem `os.getenv("ORACLE_USER_KILL")`, sem `oracledb.connect` da KILL, sem SMTP.
- **Web:**
  1. execução N do script: `app.py:221` faz a pré-consulta (**DIAG nº 1**), e o painel é exibido;
  2. execução N+1 (clique): `processar_decisao_hitl` (`app.py:324-346`, sem Oracle);
  3. pelo commit 1c do plano, a pendência é copiada e limpa **antes** da chamada;
  4. `registrar_decisao_kill` (349) segue a mesma sequência da CLI a partir do passo 3.
- **Exceções da KILL:** a conta KILL só é alcançável por `matar_sessao_oracle`, e esta só é chamada em `oracle_dba.py:1017`, dentro de `executar_kill_verificado`. Hoje há um único chamador, na linha 1239.

### b2. Pré-consulta DIAG de `preparar_intervencao_kill`

**DECISÃO:** a pré-consulta está **conforme**. A regra precisa ser **redigida** como "nenhuma conexão depois da decisão". O texto "sem DIAG" do plano (linhas 40 e 47) deve ser lido como "sem **re**consulta DIAG".
- A pré-consulta acontece antes de existir decisão. Logo, também não existe INTENCAO a gravar.
- É só leitura, pela conta DIAG, e é ela que gera o hash exibido. Sem ela não haveria o que aprovar.
- O teste do plano (linha 61) já exige "1 DIAG", que é exatamente essa pré-consulta.

**Redação proposta para o plano**, a aplicar pelo responsável ou pela sessão principal, já que eu não edito o plano:

> Depois da decisão humana, nenhuma conexão ao Oracle (DIAG ou KILL) e nenhuma sonda TCP ao listener (`verificar_acessibilidade_host`) ocorre no fluxo de kill antes de a INTENCAO estar gravada com `fsync`; se a gravação falhar, nenhuma ocorre. A pré-consulta DIAG de `preparar_intervencao_kill` é anterior à decisão, somente leitura, e não é afetada.

- **Por que a sonda conta:** é uma conexão TCP ao host do banco (`oracle_dba.py:87`, chamada em 556 e 767).
- **Fora do escopo do item 1:** outras `tool_calls` do mesmo turno do LLM, que a CLI continua executando no laço de `main.py:199`. Ver f.

### b3. Teste que prova b sem conexão

**DECISÃO:** a prova é o teste T2, `test_falha_log_intencao_nao_chama_kill`, especificado em d.
- **Contagem por conta:** `_OracleFake(..., kill_permitido=False)` (`tests/fakes_oracle.py:93-110`). Se a KILL for alcançada, `pytest.fail`.
- **Contagem por momento:** o `solicitar_aprovacao` do teste guarda `list(fake.conexoes)`, `len(fake.sql_executado)` e o contador de chamadas da sonda **no instante da decisão**. Depois, o teste exige:
  - `fake.conexoes == conexoes_na_decisao == [USER_DIAG_FAKE]`;
  - nenhuma chamada nova à sonda depois da decisão.
- A sonda é envolvida por um contador sobre o fake que o teste já instala.
- Não é preciso mudar o fake.

---

## c) Linha RESULTADO em cada caso de falha do kill

### c1. Campos

**DECISÃO:** a linha RESULTADO do ramo APROVADO tem:
- `timestamp`, `fase="RESULTADO"`, o **mesmo** `id_intervencao` da INTENCAO;
- `aprovador`, `decisao="APROVADO"`, `resultado_banco=<status>`, `motivo`, `hash_payload`, `parametros`, `alvo`.

O `motivo` é `null`, com duas exceções: em `ERRO_INTERNO` e `INTERROMPIDO` ele recebe o nome da classe da exceção. A mensagem da exceção nunca entra.

`executado` e `falha_registro` **ficam no retorno** (`desfecho`) e **não entram no JSONL**:
- **`executado`:** é derivado de `resultado_banco in RESULTADOS_KILL_EXECUTADO` (`oracle_dba.py:41`, `:1251`). Gravá-lo criaria uma segunda fonte de verdade. Pior: diria `false` em casos cujo estado real no banco é desconhecido (`ERRO_ORACLE` depois do `execute`, ver c4).
- **`falha_registro`:** uma linha gravada não tem como registrar a própria falha.

Retorno do ramo APROVADO: `decisao`, `resultado_banco`, `executado`, `motivo` (hoje `None`, linha 1294), `falha_registro` (`None` ou `"RESULTADO"`), `id_intervencao`, `resultado_tool` (sem o id), `registro`, `assunto_email`, `email_enviado` e `email_detalhe`.

### c2. Tabela por caso

E-mail "NÃO executada" = `montar_notificacao_kill` (1100-1110), sem mudança. "KILL" = conexões à conta KILL.

| Caso | Origem (linha atual) | `resultado_banco` | `motivo` | KILL | E-mail | Estado real |
|---|---|---|---|---|---|---|
| `ERRO_ORACLE` no `execute` (PLS-00306, ORA-00600, timeout) | 842-855 | `ERRO_ORACLE` | null | 1 | NÃO executada | PLS-00306: não executado, porque o bloco não compila. Os demais: **a conferir** (c4) |
| `ERRO_ORACLE` na reconsulta DIAG | 644-649, que vira 955-972 | `ERRO_ORACLE` | null | 0 | NÃO executada | não executado. No JSONL não se distingue do caso acima, então também se confere |
| `ALVO_DIVERGENTE` (PKG v2) | p_status, 823 | `ALVO_DIVERGENTE` | null | 1 | NÃO executada | não executado (o PKG recusou) |
| `ALVO_ALTERADO` | 975-993 | `ALVO_ALTERADO` | null | 0 | NÃO executada | não executado |
| `ALVO_NAO_ENCONTRADO` na reconsulta | 955-972 | `ALVO_NAO_ENCONTRADO` | null | 0 | NÃO executada | não executado |
| `NAO_USUARIO` / `USUARIO_PROTEGIDO` na reconsulta | 995-1008 | idem | null | 0 | NÃO executada | não executado |
| **TTL nº 2** com `APROVACAO_EXPIRADA` | **novo**, entre 1008 e 1010 | `APROVACAO_EXPIRADA` | null | 0 | NÃO executada | não executado |
| `ERRO_CONFIG` / `HostInacessivelVPN` da DIAG | 545-562, que vira 955-972 | idem | null | 0 | NÃO executada | não executado |
| `ERRO_CONFIG` / `HostInacessivelVPN` da KILL | 752-782; sem `status_banco`, cai no `motivo` em 1250 | idem | null | 0 | NÃO executada | não executado |
| `PARAM_INVALIDO` local (identidade da reconsulta incompleta) | 716-745 | `PARAM_INVALIDO` | null | 0 | NÃO executada | não executado |
| Exceção não-Oracle dentro do `try` da KILL | 856-868 (sem `status_banco`, então vale o nome da classe) | nome da classe | null | 1 | NÃO executada | **a conferir**. Mantido como está: fora do item 1 |
| **`ERRO_INTERNO`**: `Exception` que escapa de `executar_kill_verificado` | **novo** `except Exception` em volta de 1239 | `ERRO_INTERNO` | `type(exc).__name__` | 0 no código atual | NÃO executada | ver abaixo |
| **`INTERROMPIDO`**: `BaseException` (`KeyboardInterrupt`, `SystemExit`) | **novo** `except BaseException` em volta de 1239 | `INTERROMPIDO` | `type(exc).__name__` | 0 ou 1 | **nenhum** | **desconhecido** |

Notas da tabela:
- **ERRO_INTERNO, 0 KILL no código atual:** as exceções que podem escapar vêm de pontos fora dos `try`: sonda (556, 767), `getenv`, `calcular_hash_identidade` (974). Todos são anteriores ao `connect` da KILL. Mesmo assim, o auditor confere (c4), porque o código pode mudar.
- **Mensagem do `resultado_tool` em ERRO_INTERNO:** `{"status":"erro","motivo":"ERRO_INTERNO","status_banco":"ERRO_INTERNO","tipo_erro":<classe>,"mensagem":"Erro interno no fluxo de kill; estado no banco não confirmado. Consulte OPS_KILL_AUDIT."}`, sem `str(exc)`.

**DECISÃO: TTL nº 2.**
- **Onde:** em `executar_kill_verificado`, depois da elegibilidade (`oracle_dba.py:1008`) e antes de montar a identidade e chamar `matar_sessao_oracle` (1010-1023). É a **última** checagem antes da conta KILL.
- **Assinatura:** ganha o keyword-only obrigatório, sem default, `aprovacao_expirada: Callable[[], bool]`. Em `registrar_decisao_kill` ele é montado como `lambda: _aprovacao_expirada(preparado_em, (agora or _agora_utc)())`.
- **Por que o callable, e não `preparado_em, agora` como diz o plano (linha 41):**
  - o item 7 troca a base do TTL para `preparado_monotonic`. Com o callable, essa troca fica num único ponto, `registrar_decisao_kill`;
  - os dois pontos de TTL usam sempre a mesma função;
  - a assinatura de `executar_kill_verificado` não muda de novo.
- **Docstring a corrigir:** com isso o relógio passa a ser lido duas vezes. A docstring em `oracle_dba.py:1159` ("lido uma única vez") precisa mudar.
- **Efeito nos testes:** o helper `_relogio_relativo` (`tests/test_oracle_kill.py:460-462`) devolve o mesmo delta nas duas leituras, então os testes atuais não mudam de expectativa.
- **Decisão no registro:** no ponto 2 a decisão registrada continua `APROVADO`, e não TIMEOUT. A INTENCAO já existe e a aprovação humana foi dada no prazo. Quem venceu foi a janela de execução. O e-mail "NÃO executada (status APROVACAO_EXPIRADA)" é verdadeiro.

**DECISÃO: exceções sem try/finally.** Ficam dois `except` explícitos em volta da chamada da linha 1239:
- `except Exception as exc`:
  - `resultado_exec` vira o JSON `ERRO_INTERNO` acima, com `logger.error` (tipo apenas);
  - o fluxo **continua normalmente**: RESULTADO, log, e-mail "NÃO executada" e retorno.
- `except BaseException as exc`:
  - monta o RESULTADO com `resultado_banco="INTERROMPIDO"` e `motivo=type(exc).__name__`;
  - grava **uma vez** com `_gravar_linha_jsonl_duravel`, dentro de `try/except Exception`;
  - chama `logger.critical("... INTERROMPIDO ... desfecho desconhecido; consulte OPS_KILL_AUDIT | id_intervencao=...")`, e, se a gravação falhou, o registro serializado vai junto;
  - **`raise`**;
  - não envia e-mail: o processo está saindo, e o SMTP prenderia a saída.
- **Por que não try/finally:** o `finally` rodaria também no caminho normal e exigiria um flag para não gravar duas vezes. Os dois `except` deixam claro qual RESULTADO cada caminho grava.
- **Exceção de teste:** o `Failed` do `pytest.fail` (o fake da KILL) é `BaseException` e passa pelo segundo ramo, com `raise`. O teste continua falhando, como deve.

### c3. Falha da própria gravação da RESULTADO

**DECISÃO (ramo APROVADO, depois do kill):**
- monta o registro (`_montar_registro_aprovacao_kill`) e chama `_gravar_linha_jsonl_duravel` dentro de `try/except Exception`. Substitui 1253-1263;
- se falhar:
  - `registro=None`, `falha_registro="RESULTADO"`;
  - `logger.critical(f"AUDITORIA HITL: FALHA AO GRAVAR RESULTADO | id_intervencao={id} | erro={type(exc).__name__} | registro={json.dumps(registro, ensure_ascii=False, default=str)}")`. Esse é o registro completo, sem credenciais, porque o dict não tem credenciais;
  - a **exceção não se propaga**;
- **e-mail enviado assim mesmo:**
  - o assunto ganha o prefixo `"[REGISTRO DE RESULTADO FALHOU] "`;
  - o corpo ganha a linha: `ATENÇÃO: a linha RESULTADO não foi gravada em kill_approval.log; registro completo no log da aplicação (CRITICAL), id_intervencao=<id>.`;
- **tela:** a CLI mostra um aviso vermelho e a Web um `st.error`, com o id.

Justificativa: o kill pode ter acontecido. Esconder isso, ou derrubar o fluxo, é pior do que avisar por todos os canais. É o que diz o plano, linha 48.

**DECISÃO (REJEITADO/TIMEOUT, ramo 1183-1234):**
- se a gravação falhar, `logger.error` com o registro serializado;
- o desfecho segue normal, com `falha_registro="RESULTADO"` e `registro=None`;
- sem e-mail, como hoje;
- a conta KILL não é tocada em nenhum momento desse ramo.

### c4. O caso não coberto e a regra do auditor

**DECISÃO:** declarar como **não coberto** pelo código:
- queda do processo ou de energia, ou `kill -9`, entre o fsync da INTENCAO e o fsync da RESULTADO, inclusive entre o kill e a RESULTADO;
- segundo Ctrl+C durante a gravação do `INTERROMPIDO`;
- falha simultânea do JSONL e do log da aplicação.

A cobertura desses casos é a regra do auditor.

**Regra do auditor** (a constar no GOVERNANCA_LOG ou num procedimento, quando o item 1 for executado):

1. **Linhas que não são JSON válido:** gravação interrompida (a4). Registrar como incidente e ignorar no pareamento.
2. **Linhas sem `fase`:** formato antigo, anterior à 1.11. Valem como registro único, como antes.
3. **Agrupar por `id_intervencao`:**
   - **INTENCAO + RESULTADO** com `resultado_banco`:
     - em `ENCERRADA` ou `MARCADA_PARA_KILL`: executado;
     - em {`ALVO_ALTERADO`, `ALVO_DIVERGENTE`, `ALVO_NAO_ENCONTRADO`, `NAO_USUARIO`, `USUARIO_PROTEGIDO`, `PROPRIA_SESSAO`, `APROVACAO_EXPIRADA`, `PARAM_INVALIDO`, `ERRO_CONFIG`, `HostInacessivelVPN`}: não executado;
     - **qualquer outro valor** (`ERRO_ORACLE`, `ERRO_INTERNO`, `INTERROMPIDO`, nome de classe, `DESCONHECIDO`): **a conferir** em `OPS_KILL_AUDIT`.
   - **INTENCAO sem RESULTADO:** procurar o id no log da aplicação:
     - `FALHA_LOG_APROVACAO`: não executado (a6);
     - `FALHA AO GRAVAR RESULTADO`: usar o registro serializado do CRITICAL;
     - `INTERROMPIDO` no CRITICAL: desfecho desconhecido;
     - nada encontrado: **desfecho desconhecido**.
     Em todos esses casos, conferir em `OPS_KILL_AUDIT`.
   - **RESULTADO com `decisao=APROVADO` sem INTENCAO:** a ordem foi violada. Incidente, porque não deveria existir depois do item 1.
4. **Conferência em `OPS_KILL_AUDIT`:**
   - **com o aa9a0a5 aceito e o PKG v2 implantado:**
     - consulta: `WHERE ref_aprovacao = :id_intervencao`, com igualdade exata e 32 hex;
     - linha presente: o `status_codigo` é o desfecho;
     - ausente: o PKG não foi alcançado, ou o bloco não compilou (PLS-00306), e o kill não aconteceu;
   - **com o aa9a0a5 revertido (PKG v1):**
     - `ref_aprovacao` fica NULL, porque a coluna existe desde a parte 1 mas o v1 não a preenche;
     - consulta: `WHERE inst_id = :inst_id AND sid = :sid AND serial_no = :serial AND dt_evento BETWEEN :t0 AND :t1`, sendo `t0` = `timestamp` da INTENCAO e `t1` = `t0` + `APROVACAO_TTL_SEGUNDOS` + o call timeout do item 7;
     - **`dt_evento` é TIMESTAMP sem fuso, gravado no relógio do servidor** (`db/ops_kill.sql:13`, `DEFAULT SYSTIMESTAMP`). O timestamp da INTENCAO está em UTC. Converter e aplicar margem para a diferença de relógio;
     - conferir também `alvo_username` contra o `alvo` do JSONL;
     - mais de uma linha na janela é ambíguo e exige análise manual.

---

## d) Testes sem conexão

Todos rodam com `_OracleFake` e `ambiente_fake`, sem `ORACLE_SANDBOX`, com log em `tmp_path` e usuários fictícios (`USER_DIAG_FAKE`/`USER_KILL_FAKE`). Nenhum skip de plataforma. Falhas de E/S são injetadas assim:
- `monkeypatch.setattr(oracle_dba, "open", proxy, raising=False)`, que sombreia o `open` builtin só no módulo;
- `monkeypatch.setattr(os, "fsync", ...)`;
- `monkeypatch.setattr(oracle_dba, "_fsync_diretorio", ...)` e `monkeypatch.setattr(oracle_dba, "_FSYNC_DIRETORIO", ...)`.

### d1. Testes novos

| # | Teste (arquivo) | Prova | Exige |
|---|---|---|---|
| T1 | `test_intencao_gravada_antes_da_conta_kill` (`test_oracle_kill.py`) | a, b | Uma lista `eventos`, alimentada pelo `connect` do fake e por um espião de `os.fsync`; o espião só conta fd de arquivo regular (`stat.S_ISREG(os.fstat(fd).st_mode)`). Ordem obrigatória: `connect DIAG` (com o JSONL vazio), ≥1 `fsync`, `connect DIAG` (o JSONL já tem a INTENCAO), `connect KILL` (o JSONL tem **só** a INTENCAO), `fsync`. No `connect` da KILL: INTENCAO com `decisao=APROVADO`, `resultado_banco=None`. No fim: 2 linhas, INTENCAO depois RESULTADO, com o mesmo id. Com o aa9a0a5 aceito, o id é igual ao bind `p_ref_aprovacao` |
| T2 | `test_falha_log_intencao_nao_chama_kill`, parametrizado: `caminho_diretorio`, `encode_falha` (aprovador com `"\ud800"`), `write_parcial` (o proxy grava metade dos bytes e levanta `OSError(ENOSPC)`), `flush_levanta`, `fsync_levanta`, `close_levanta`, `fsync_diretorio_levanta` | a, b | Desfecho `APROVADO`/`FALHA_LOG_APROVACAO`, `executado False`, `resultado_banco None`, `falha_registro "INTENCAO"`, `registro None`, `assunto_email None`. `fake.conexoes == [USER_DIAG_FAKE]`, igual ao snapshot tirado na decisão. 0 chamadas à sonda depois da decisão. `kill_permitido=False`. 0 e-mail. Um ERROR no caplog com `FALHA_LOG_APROVACAO` e o id. `"senha-fake"` ausente. `resultado_tool` sem o id. Arquivo: 0 linhas válidas, ou exatamente 1 INTENCAO com o id do caplog, e nunca uma RESULTADO. Em `encode_falha` o arquivo não existe |
| T3 | `test_linha_parcial_anterior_isolada` | a | O arquivo começa com `{"fase": "INTEN` sem `\n`. Um REJEITADO depois disso: a linha parcial fica intacta e isolada, e a linha nova faz parse e é a última |
| T4 | `test_log_aprovacao_faz_fsync` (o nome vem do plano) | a | `os.fsync` em fd regular: 1 vez por REJEITADO e 2 por APROVADO. Os bytes novos terminam em `b"\n"` e não contêm `b"\r\n"` (modo binário) |
| T5 | `test_fsync_diretorio_so_quando_arquivo_novo`, parametrizado com `_FSYNC_DIRETORIO` True/False | a | Com True: `_fsync_diretorio` chamado uma vez na primeira gravação e nenhuma vez na segunda. Com False (Windows): nunca chamado. Roda em qualquer SO, porque o espião substitui a função |
| T6 | `test_registro_fase_e_id_validados` | a | `fase` ausente ou `id_intervencao` ausente dão `TypeError`. `fase="X"`, INTENCAO com `decisao≠APROVADO`, INTENCAO com `resultado_banco≠None` e id fora de 32 hex dão `ValueError`. Em todos os casos o arquivo não é criado |
| T7 | `test_ttl_vence_entre_reconsulta_e_kill` (plano) | c | Relógio sequencial: +10 s na decisão, +301 s no recheck. Resultado: 2 DIAG, 0 KILL, `decisao APROVADO`, RESULTADO `APROVACAO_EXPIRADA` com o mesmo id, 1 e-mail "NÃO executada" |
| T8 | `test_resultado_por_caso_de_falha`, parametrizado com os casos de c2 que não têm teste próprio: `ora00600`, `alvo_nao_encontrado_reconsulta`, `nao_usuario_reconsulta`, `usuario_protegido_reconsulta`, `erro_config_diag` (`delenv` dentro do `solicitar_aprovacao`), `host_inacessivel` (a sonda devolve False depois da decisão), `erro_config_kill`, `param_invalido_local` (reconsulta com `LOGON_TIME=None`) | c | Exatamente 2 linhas, INTENCAO e RESULTADO, com o mesmo id. `resultado_banco` igual ao esperado, `executado False`, `falha_registro None`, 1 e-mail "NÃO executada". Conexões KILL conforme a tabela c2 (0 ou 1) |
| T9 | `test_erro_interno_grava_resultado` | c | A sonda levanta `RuntimeError("segredo-xyz")` na 2ª chamada. Resultado: sem exceção para quem chamou, 2 linhas, RESULTADO `ERRO_INTERNO` com `motivo "RuntimeError"`, 0 KILL, 1 e-mail "NÃO executada". `"segredo-xyz"` ausente do JSONL e do `resultado_tool` |
| T10 | `test_interrupcao_grava_resultado_e_propaga` | c | A sonda levanta `KeyboardInterrupt` na 2ª chamada. `pytest.raises(KeyboardInterrupt)`. 2 linhas, RESULTADO `INTERROMPIDO` com `motivo "KeyboardInterrupt"`, 0 KILL, 0 e-mail, CRITICAL no caplog |
| T11 | `test_falha_registro_resultado_nao_silenciosa` (plano) | c | O proxy de `open` falha só na 2ª gravação. Resultado: 1 KILL, sem exceção, `falha_registro "RESULTADO"`. O CRITICAL contém o id, `"resultado_banco": "ENCERRADA"` e o JSON parseável do registro. O assunto do e-mail começa com `[REGISTRO DE RESULTADO FALHOU]`. O JSONL só tem a INTENCAO |
| T12 | `test_falha_registro_rejeitado_e_timeout` (plano) | c | REJEITADO e TIMEOUT com a gravação falhando: sem exceção, 0 KILL, ERROR com o registro serializado, `falha_registro "RESULTADO"`, 0 e-mail |
| T13 | `test_cli_falha_log_aprovacao` / `test_web_falha_log_aprovacao` (plano) | a, b | Tela com "NÃO EXECUTADA" e "nenhuma chamada à conta KILL", 0 KILL, 0 e-mail. Web: `hitl_pendente is None` e painel ausente |
| T14 | `test_web_excecao_em_registrar_decisao` / CLI `..._excecao_rota_kill` (plano, 9.3) | c | `RuntimeError` não quebra o app. Pendência limpa, mensagem `tool` com `executado: null`, texto "estado desconhecido". CLI imprime `ERRO interno no fluxo de kill; estado desconhecido` (`main.py:268-271`) |

T1 já cobre a ordem pedida pelo plano (linha 60), e T2 cobre a linha 61, ampliada para write, flush, close, encode e fsync do diretório.

### d2. Mudanças de expectativa aceitas pela decisão 1 (2 linhas por APROVADO)

Lista do plano (linha 69). Todas vão para a lista de asserções alteradas no GOVERNANCA_LOG, com esta justificativa: "sem a INTENCAO não há prova de que a aprovação foi registrada antes da ação".

| Teste | Antes | Depois (sem enfraquecer) |
|---|---|---|
| `test_cli_aprovado_encerrada`, `test_cli_aprovado_nao_usuario`, `test_cli_alvo_alterado` (`test_fluxo_cli.py:167,182,222`, com `_um_registro` em 158) | 1 linha | 2 linhas: `[0]` INTENCAO (`APROVADO`, `resultado_banco None`), `[1]` RESULTADO. As asserções atuais passam a valer para `[1]`. Além disso: mesmo id, 32 hex |
| `test_web_aprovado_encerrada`, `test_web_aprovado_nao_usuario`, `test_web_alvo_alterado` (`test_fluxo_web.py:230,258,320`) | 1 linha | idem |
| `test_aprovacao_dentro_do_ttl_executa` (2 parâmetros, `test_oracle_kill.py:566-569`) | `len == 1` | `len == 2`. As asserções de `decisao`/`motivo None` passam para a RESULTADO, mais as asserções de fase e id |
| `test_registro_log_contem_decisao_e_resultado_banco_separados` (`test_oracle_kill.py:613-615`) | 2 linhas | 3 linhas: `intencao, aprovado, rejeitado`. O laço que exige `decisao`/`resultado_banco` e a ausência de `status_banco` passa a valer para as 3 linhas |

**Mudanças só de chamada**, sem mudança de expectativa, a declarar também: `fase` e `id_intervencao` ficam obrigatórios. Isso afeta as 4 chamadas diretas a `registrar_log_aprovacao_kill` em `test_oracle_kill.py:194, 210, 239, 651`, que ganham `fase="RESULTADO", id_intervencao="0"*32`. O item 3 reescreve o teste das linhas 194/210, e lá a correção entra junto.

**Sem mudança:**
- REJEITADO e TIMEOUT continuam com 1 linha (por exemplo, `test_oracle_kill.py:500-501`). Cabe acrescentar `fase == "RESULTADO"`, o que só fortalece a asserção.
- `_ultimo_registro` (668), `[-1]` em 392, `test_kill_chamada_nomeada_nove_formais` e `test_kill_pls00306_vira_erro_oracle` continuam corretos, porque a RESULTADO é a última linha. Cabe acrescentar a igualdade de id com a INTENCAO.

**Nenhuma asserção existente é removida ou afrouxada.** Se algum teste existente falhar por outro motivo, o caso é reportado; a expectativa não é ajustada.

---

## e) Com o aa9a0a5 aceito ou revertido

**DECISÃO:** a ordem, as falhas, os campos e os testes são **os mesmos** nos dois casos. Mudam só a ligação com o banco e a chave que o auditor usa.

| Ponto | aa9a0a5 **aceito** | aa9a0a5 **revertido** (código de `aa9a0a5~1`) |
|---|---|---|
| `import uuid` | já existe (`oracle_dba.py:16`) | **acrescentar**: não existe em `aa9a0a5~1` (conferido; lá só há `import re`) |
| Validação do id | reusa `_REGEX_REF_APROVACAO` (56) | criar uma regex igual, de nome neutro (`_REGEX_ID_INTERVENCAO`) |
| `registrar_log_aprovacao_kill` | o `id_intervencao` opcional (1035, 1065-1066) passa a obrigatório | acrescentar `id_intervencao` (não existe) e `fase` |
| `executar_kill_verificado` | `ref_aprovacao=id` (942) e `aprovacao_expirada` | só `aprovacao_expirada`; não há ref |
| `ALVO_DIVERGENTE` | existe (PKG v2) e fica no T8 | não existe; sai do T8 |
| Chave do auditor | `OPS_KILL_AUDIT.ref_aprovacao = id` | inst_id/sid/serial_no + janela de `dt_evento` (c4) |
| Testes do item 6 (`test_oracle_kill.py:672-749`) | continuam valendo | saem junto com o revert |

---

## f) Riscos residuais e observações (sem mudança no item 1)

1. **OneDrive:** `data/logs/` fica dentro de uma pasta sincronizada pelo OneDrive.
   - O fsync garante o disco local, não a sincronização.
   - Um lock temporário do OneDrive faz o `open` falhar. Na INTENCAO isso dá `FALHA_LOG_APROVACAO` (fail-closed, aceitável); na RESULTADO, CRITICAL.
   - Recomendação para a operação: apontar o `PERSONAL_AGENT_LOG_DIR` do item 2 para fora do OneDrive.
2. **Vários processos:** o lock é só dentro do processo. CLI e Web gravando ao mesmo tempo podem, no Windows, sobrepor linhas. Aceito como residual, porque o uso é de um operador por vez.
3. **`ERRO_ORACLE` depois do `execute`:** o e-mail e a tela dizem "NÃO executada", mas com o call timeout do item 7 o PKG pode ter concluído o kill. O texto é uma questão de mensagens, a levar ao item 7 ou à tarefa seguinte. Por enquanto, a regra do auditor (c4) cobre o caso.
4. **CLI e `tool_calls` restantes:** depois de um kill recusado, a CLI continua executando as outras ferramentas que o LLM pediu no mesmo turno (`main.py:199`). Elas só usam a DIAG e não alcançam a KILL sem um novo HITL. Fora do escopo do item 1.
5. **Item 7:** o TTL monotônico muda só o callable `aprovacao_expirada` (c2). Não conflita com esta decisão.

> **Adendo 2026-11-18 (achado A, revisão Gemini; decisão `abc/decisao_A.md`).** Em b1, Web, passo 2, onde se lê "execução N+1 (clique): `processar_decisao_hitl` (`app.py:324-346`, sem Oracle)", leia-se: "execução N+1 (clique): o script roda de cima para baixo. **Antes** de `processar_decisao_hitl` (hoje `app.py:754`), a barra lateral e a telemetria, fora do fluxo de kill, fazem a sonda TCP (`app.py:579`) e, se o host estiver acessível, `coletar_sessoes_ativas` (`app.py:631`) e `coletar_top_sql` (`app.py:686`), com 2 conexões `ORACLE_USER_DIAG` somente leitura e nenhuma KILL. O `st.rerun()` seguinte (`app.py:755`) as repete, inclusive após `FALHA_LOG_APROVACAO`. `processar_decisao_hitl`, até a INTENCAO, não faz conexão." O título da seção b deve ser lido como na redação de b2: "nenhuma conexão **do fluxo de kill** posterior à decisão humana antes da INTENCAO". A decisão b não muda. A suspensão da telemetria no rerun de decisão fica como item próprio, junto com o R1 da sonda.
