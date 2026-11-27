# C1 da parte A do SQL v2 (`1.11-sqlv2-parte2`): decisão do `seguranca`

- **Modelo:** claude-opus-5-5 (subagente `seguranca`). Só leitura, sem Oracle e sem pytest. A única gravação é este arquivo.
- **Base:** `main` em `871ae13`. Todo `arquivo:linha` foi conferido nesta sessão (L9).
- **Escopo:** as 6 perguntas de `passo0.md:30-39`, para o rascunho v2 (`docs/entregas/1.11/item6/`) e o lado Python.
- **Área §2:** `matar_sessao_oracle` e `RECUSAS_PKG_SEM_KILL` são "Kill e auditoria" (`PROCESSO.md:31`), escritos só por Opus. O SQL é a proposta do "Pacote no banco" (`:33`): commit "PENDENTE APROVAÇÃO".

## 0. Fatos conferidos agora

| Fato | Onde |
|---|---|
| O SELECT só trata `NO_DATA_FOUND`. Erro no SELECT, no `UTL_RAW` ou nas etapas 4 a 6 sai do PKG como exceção, sem `registra` | `ops_kill.sql:140-156`, `:160-178`, `:203-205` |
| O único `WHEN OTHERS` é o do `ALTER SYSTEM`: -31 dá MARCADA, -30 dá ALVO_NAO_ENCONTRADO, o resto dá ERRO_ORACLE com `SQLERRM` | `ops_kill.sql:184-199` |
| `v_type <> 'USER'` com `v_type` nulo dá NULL e segue para o ELSIF. Se o usuário não for protegido, o fluxo **chega ao kill** (ver A1) | `ops_kill.sql:172-177` |
| Python: lista fechada. Fora de EXECUTADO e RECUSAS, o desfecho é desconhecido. Exceção depois do `execute` também é desconhecida | `oracle_dba.py:84`, `:89-92`, `:1182-1200`, `:1216-1264` |
| `executado` exige `resultado_desconhecido False` | `oracle_dba.py:2218-2220` |
| **Correção ao `passo0.md:28`:** o teste de amarração já existe. O K2 exige `literais v_status == RECUSAS ∪ EXECUTADO ∪ {ERRO_ORACLE}`, mas lê só `ops_kill.sql` e usa a regex `[A-Z_]+` | `tests/test_oracle_kill.py:1524-1539` |
| Nenhum teste lê `ops_kill_v2_migracao_parte2.sql`, que é o arquivo que roda no MODELO. O cabeçalho promete "cópia literal" | grep em `tests/` sem resultado; `parte2.sql:6` |
| Spec e body da parte 2 são **hoje** idênticos aos de `ops_kill.sql`. Sonda `python -I -c` (só leitura) sobre os blocos `CREATE OR REPLACE PACKAGE [BODY] ... END pkg_ops_kill;/`: `2 2 [True, True]` | sonda desta sessão |
| O fake grava qualquer `status_pkg` | `tests/fakes_oracle.py:140-148`, `:203-217` |
| `status_codigo VARCHAR2(40) NOT NULL` e `mensagem VARCHAR2(400)`, sem CHECK. A parte 1 só faz ADD de 3 colunas | `ops_kill.sql:34-35`; `parte1.sql:75-79` |
| `implantacao.md:206` cita `test_kill_pls00306_vira_erro_oracle`, que não existe. Os testes reais são `test_item1_intencao.py:563` e `:638`, e dão desconhecido, não "NÃO executada" | grep em `tests/` |

## 1. Q1: erro antes do kill. Código `ERRO_PRE_KILL`

**Decisão:**
- As etapas 1 a 6 ficam num bloco próprio, com `WHEN OTHERS` que grava `ERRO_PRE_KILL`.
- O kill passa a exigir uma flag positiva, `v_pode_encerrar`. Ela só vira TRUE na **última** instrução do bloco, e apenas quando todas as checagens passaram.
- O motivo da flag: o `WHEN OTHERS` novo troca "exceção, logo não há kill" (garantia estrutural de hoje) por "status preenchido, logo não há kill" (garantia que depende de um dado). Com a flag, a garantia volta a ser estrutural. Se o handler for alterado e esquecer o `v_status`, a flag continua FALSE. O `registra` com `status_codigo` nulo então viola o NOT NULL, a exceção sobe e o Python dá desconhecido. Nos dois casos não há kill.

**Texto exato:** substitui `ops_kill.sql:102-207` e, de forma idêntica, `parte2.sql:76-181`. Onde está "(atual)", o texto continua igual ao de hoje.

```sql
  ) IS
    v_solicitante VARCHAR2(128) := SYS_CONTEXT('USERENV', 'SESSION_USER');
    v_user   VARCHAR2(128);
    v_prog   VARCHAR2(128);
    v_mach   VARCHAR2(128);
    v_type   VARCHAR2(10);
    v_logon  DATE;
    v_div    VARCHAR2(64);
    v_status VARCHAR2(40);
    v_msg    VARCHAR2(400);
    -- TRUE só na última instrução do bloco das etapas 1 a 6, com todas as checagens
    -- aprovadas. Exceção antes dela o deixa FALSE: sem ele, não há ALTER SYSTEM.
    v_pode_encerrar BOOLEAN := FALSE;
  BEGIN
    -- Etapas 1 a 6: nenhuma encerra sessão. Erro em qualquer delas vira ERRO_PRE_KILL,
    -- com linha em OPS_KILL_AUDIT e sem ALTER SYSTEM. O WHEN OTHERS deste bloco não
    -- cobre a etapa 7 nem o registra, que ficam depois do END do bloco.
    BEGIN
      -- 1. (comentário atual :113-118)
      IF (condição atual :119-127) THEN
        v_status := 'PARAM_INVALIDO';
      -- 2. Própria sessão
      ELSIF (condição atual :131-132) THEN
        v_status := 'PROPRIA_SESSAO';
      ELSE
        -- 3. (SELECT atual :136-156, sem mudança, com o WHEN NO_DATA_FOUND -> 'ALVO_NAO_ENCONTRADO')
        -- 4. (atual :158-168)
        -- 5/6. Tipo e usuário protegido, sobre os valores OBSERVADOS.
        --      v_type nulo conta como não USER (null-safe).
        IF v_status IS NULL THEN
          IF v_type IS NULL OR v_type <> 'USER' THEN
            v_status := 'NAO_USUARIO';
          ELSIF v_user IS NULL
             OR INSTR(c_protegidos, ',' || UPPER(v_user) || ',') > 0 THEN
            v_status := 'USUARIO_PROTEGIDO';
          END IF;
        END IF;

        IF v_status IS NULL THEN
          v_pode_encerrar := TRUE;
        END IF;
      END IF;
    EXCEPTION
      WHEN OTHERS THEN
        v_status := 'ERRO_PRE_KILL';
        v_pode_encerrar := FALSE;
        v_msg := SUBSTRB(SQLERRM, 1, 400);
        -- Depois de exceção, as variáveis do INTO não são observação confiável.
        v_user := NULL; v_prog := NULL; v_mach := NULL; v_logon := NULL; v_div := NULL;
    END;

    -- 7. Encerramento: único ALTER SYSTEM do pacote. Micro-janela residual SELECT -> ALTER
    --    SYSTEM aceita: o comando é endereçado por sid + serial#; se a sessão não existir
    --    mais (inclusive SID reutilizado, com serial# novo), o Oracle devolve ORA-00030.
    IF v_pode_encerrar AND v_status IS NULL THEN
      BEGIN
        (EXECUTE IMMEDIATE atual :185-187)
        v_status := 'ENCERRADA';
      EXCEPTION
        WHEN OTHERS THEN
          IF SQLCODE = -31 THEN
            v_status := 'MARCADA_PARA_KILL';
          ELSIF SQLCODE = -30 THEN
            v_status := 'ALVO_AUSENTE_NO_KILL';
          ELSE
            v_status := 'ERRO_ORACLE';
            v_msg := SUBSTRB(SQLERRM, 1, 400);
          END IF;
      END;
    END IF;

    (registra atual :203-205)
    p_status := v_status;
  END kill_session;
```

**Cabeçalho do arquivo:** depois de `ops_kill.sql:13`, entra a linha `-- Erro antes do ALTER SYSTEM -> ERRO_PRE_KILL (sem kill, com auditoria); ORA-00030 no ALTER SYSTEM -> ALVO_AUSENTE_NO_KILL.`

**Respostas:**
- **Registro:** sim. O `registra` grava a linha com `status_codigo = 'ERRO_PRE_KILL'`, `mensagem = SUBSTRB(SQLERRM,1,400)`, `alvo_*` nulos e `ref_aprovacao`. Segundo a documentação Oracle (não verificado), depois de TOO_MANY_ROWS as variáveis do INTO ficam indefinidas, e por isso o handler as anula.
- **Python:** sim, o `ERRO_PRE_KILL` entra em `RECUSAS_PKG_SEM_KILL`. A prova é estrutural: o handler está textualmente antes do único `EXECUTE IMMEDIATE`. Em PL/SQL, o handler só cobre instruções anteriores a ele no mesmo bloco, e a flag fica FALSE. A garantia vale para o texto aprovado e instalado (ver §6, conferência `DBA_SOURCE`).
- **Texto ao LLM:** é fixo, e o `SQLERRM` nunca chega ao Python, que só recebe `p_status`.

Em `oracle_dba.py`, depois de `:108`:
```python
MENSAGEM_ERRO_PRE_KILL = (
    "Erro no procedimento de encerramento antes do comando de encerramento. "
    "Encerramento NÃO executado. Detalhe só em OPS_KILL_AUDIT."
)
```
Em `matar_sessao_oracle`, logo depois do ramo ALVO_DIVERGENTE (`:1189-1191`):
```python
        elif status_banco == "ERRO_PRE_KILL":
            # Erro capturado pelo PKG antes do comando de encerramento; o texto do erro fica só em OPS_KILL_AUDIT (R1).
            mensagem = MENSAGEM_ERRO_PRE_KILL
```
O texto não contém `PKG_OPS_KILL`, `OPS_OWNER`, `KILL_SESSION` nem `OPS_KILL_PKG_VERSAO` (`test_r1_saida_llm.py:310`; `test_oracle_kill.py:2050`).

## 2. Q2: ORA-00030 com código próprio, `ALVO_AUSENTE_NO_KILL`

- **Decisão:** o -30 do `ALTER SYSTEM` passa a dar `ALVO_AUSENTE_NO_KILL`. O `ALVO_NAO_ENCONTRADO` fica só para o `NO_DATA_FOUND` do SELECT.
- **Por que este nome, e não `ALVO_SAIU_ANTES_DO_KILL`:** o nome registra o que o PKG observou (não havia sessão com esse `sid,serial#` no comando), sem afirmar a causa (L2). O ORA-00030 não distingue a sessão que saiu da que foi limpa depois de um kill concorrente.
- **Fica nas recusas sem kill:** o ORA-00030 diz que não há sessão com esse `sid,serial#`, então esta chamada não encerrou nada. Isso é o esperado pela documentação Oracle, não verificado no banco (L7). É o mesmo risco aceito em P2 (`1.11-V2-item6.md:369`); o código novo não muda o risco, só o torna visível.
- **Mensagem ao LLM:** `MENSAGEM_RECUSA_PKG` genérica (mudança mínima). O código diz o motivo.
- **Comentário novo:** substitui `oracle_dba.py:86-92`, porque o atual diz que o ALVO_NAO_ENCONTRADO vem do ORA-00030.
```python
# p_status do PKG_OPS_KILL v2 que provam que nenhuma sessão foi encerrada por esta chamada. Lista FECHADA.
# - Antes do comando de encerramento (bloco das etapas 1 a 6 do PKG): PARAM_INVALIDO, PROPRIA_SESSAO,
#   ALVO_NAO_ENCONTRADO, ALVO_DIVERGENTE, NAO_USUARIO, USUARIO_PROTEGIDO e ERRO_PRE_KILL (erro capturado
#   antes do comando, que não roda).
# - No comando: ALVO_AUSENTE_NO_KILL (ORA-00030: não havia sessão com esse sid,serial#).
# Qualquer outro p_status (ERRO_ORACLE, vazio, nulo, código novo) é resultado desconhecido (sqlv2/decisao_c1.md).
RECUSAS_PKG_SEM_KILL: Tuple[str, ...] = (
    "PARAM_INVALIDO", "PROPRIA_SESSAO", "ALVO_NAO_ENCONTRADO",
    "ALVO_DIVERGENTE", "NAO_USUARIO", "USUARIO_PROTEGIDO",
    "ERRO_PRE_KILL", "ALVO_AUSENTE_NO_KILL",
)
```

## 3. Q3: `ERRO_ORACLE` devolvido pelo PKG continua desconhecido

- **Decisão:** sem mudança. O `ERRO_ORACLE` fica fora das duas listas e na lista declarada de desconhecidos.
- **Motivo:** o código chegou a rodar o `ALTER SYSTEM`. Há erros que podem chegar depois de o kill ter sido postado, como o ORA-01013 (cancelamento) ou um erro remoto em RAC. Enumerar códigos "seguros" (ORA-01031, ORA-00026, ORA-00027, ORA-00029) exigiria verificação no banco (L7) e acrescentaria superfície. O custo do falso desconhecido é conferir a `GV$SESSION`, e é aceitável.
- **Não adotado:** renomear para `ERRO_NO_KILL`. Ajudaria a perícia (separa "o PKG devolveu" de "exceção"), mas está fora da pergunta e não muda a segurança.

## 4. Q4: amarração SQL × Python × fake

**a) K2** (`test_oracle_kill.py:1524-1539`):
- passa a rodar sobre os dois arquivos;
- troca `{"ERRO_ORACLE"}` pela constante de teste `DESCONHECIDOS_DECLARADOS_PKG = {"ERRO_ORACLE"}`, disjunta das duas listas;
- `RECUSAS_ESPERADAS_PKG` (`:1483-1485`) ganha `"ERRO_PRE_KILL"` e `"ALVO_AUSENTE_NO_KILL"`. A mudança de expectativa é declarada: o conjunto cresce, e nenhuma asserção fica mais fraca.

**b) Teste novo, `test_c1_pkg_estrutura_do_kill_session`** (parametrizado nos dois arquivos). Ele extrai o `PROCEDURE kill_session ... END kill_session;` do PACKAGE BODY, tira os comentários `--[^\n]*` e exige:
```python
assert len(re.findall(r"EXECUTE\s+IMMEDIATE", p)) == 1 and len(re.findall(r"ALTER\s+SYSTEM", p)) == 1
pos_exec = re.search(r"EXECUTE\s+IMMEDIATE", p).start()
others = [m.start() for m in re.finditer(r"WHEN\s+OTHERS\s+THEN", p)]
assert len(others) == 2 and others[0] < pos_exec < others[1]
assert re.match(r"WHEN\s+OTHERS\s+THEN\s+v_status\s*:=\s*'ERRO_PRE_KILL'\s*;", p[others[0]:])
verdadeiros = [m.start() for m in re.finditer(r"v_pode_encerrar\s*:=\s*TRUE\s*;", p)]
assert len(verdadeiros) == 1 and verdadeiros[0] < others[0]
assert re.search(r"v_pode_encerrar\s+BOOLEAN\s*:=\s*FALSE\s*;", p)
assert re.search(r"IF\s+v_pode_encerrar\s+AND\s+v_status\s+IS\s+NULL\s+THEN\s+BEGIN\s+EXECUTE\s+IMMEDIATE", p)
chamadas = [m.start() for m in re.finditer(r"\bregistra\s*\(", p)]
assert len(chamadas) == 1 and chamadas[0] > others[1]
assert re.findall(r"\bp_status\s*:=\s*([^;]+);", p) == ["v_status"]
assert len(re.findall(r"\bv_status\s*:=", p)) == len(re.findall(r"\bv_status\s*:=\s*'[A-Z_]+'\s*;", p))
assert re.search(r"SQLCODE\s*=\s*-30\s+THEN\s+v_status\s*:=\s*'ALVO_AUSENTE_NO_KILL'\s*;", p)
assert len(re.findall(r"'ALVO_NAO_ENCONTRADO'", p)) == 1
assert re.search(r"IF\s+v_type\s+IS\s+NULL\s+OR\s+v_type\s*<>\s*'USER'\s+THEN", p)   # só se A1 for aprovado
```
A contagem de `v_status :=` fecha um buraco: hoje, um `v_status := 'X2'` (com dígito) ou não literal não entra na regex do K2, e o K2 passa.

**c) Teste novo, `test_c1_parte2_e_copia_literal`:** os blocos `CREATE OR REPLACE PACKAGE (BODY )?pkg_ops_kill AS.*?END pkg_ops_kill;\n/` dos dois arquivos, com CRLF normalizado, são 2 e iguais. Hoje ele passa (sonda do §0); é guarda, e o controle negativo é o M7.

**d) O fake recusa código fora do contrato.** Em `fakes_oracle.py`:
- `STATUS_CONTRATO_PKG = frozenset(re.findall(r"v_status\s*:=\s*'([A-Z_]+)'", <ops_kill.sql>))`, lido do SQL. É uma fonte independente das listas do Python, para não ser tautologia.
- Em `_OracleFake.__init__` entra o kwarg explícito `status_fora_do_contrato=False`, sem `**kwargs`: um erro de digitação dá TypeError e não é ignorado (L17).
- Se `status_pkg` for str com a forma `[A-Z][A-Z0-9_]*`, não estiver no contrato e o kwarg estiver desligado, o fake dá `raise AssertionError("... fora do contrato do PKG v2 ...")`.
- `""`, `None` e minúsculas continuam aceitos como injeção de falha.
- Único ajuste nos testes existentes: `test_oracle_kill.py:1463` passa `status_fora_do_contrato=(status_pkg == "XYZ")`.

Testes do fake:
- `_OracleFake([], status_pkg="ALVO_SAIU_ANTES_DO_KILL")` levanta;
- com `status_fora_do_contrato=True`, não levanta;
- `""`, `None`, `"encerrada"`, `"ERRO_PRE_KILL"`, `"ALVO_AUSENTE_NO_KILL"` e `"ERRO_ORACLE"` não levantam;
- com `monkeypatch.setattr(oracle_dba, "RECUSAS_PKG_SEM_KILL", ... + ("FANTASMA",))`, o `"FANTASMA"` ainda levanta.

**e) Fluxo:**
- `test_k2_recusas_do_pkg_nao_sao_desconhecidas_nem_executadas` (`:1488-1510`) cobre os dois códigos novos. Para o ERRO_PRE_KILL, exige `mensagem == MENSAGEM_ERRO_PRE_KILL`.
- `test_r1_varredura_matar_sessao_oracle` (`test_r1_saida_llm.py:167-203`) ganha dois casos, `("erro_pre_kill", dict(status_pkg="ERRO_PRE_KILL"), "ERRO_PRE_KILL")` e `("alvo_ausente_no_kill", ..., "ALVO_AUSENTE_NO_KILL")`. Os dois exigem `resultado_desconhecido is False` e `"ORA-" not in texto`.

## 5. Q5: colunas, grants e rollback

- **Colunas:** não mudam. `ERRO_PRE_KILL` tem 13 bytes e `ALVO_AUSENTE_NO_KILL` tem 20. Cabem em `status_codigo VARCHAR2(40)`, `v_status VARCHAR2(40)` e na var de 128 do Python (`oracle_dba.py:1148`). Não há CHECK. A spec não muda (9 formais), então o `DBA_ARGUMENTS` continua com 9 linhas e `test_item1_intencao.py:625` não muda.
- **Grants e privilégios:** nenhum novo. `SQLERRM`, `SUBSTRB` e BOOLEAN local são da linguagem. A conta KILL continua só com EXECUTE no PKG (`ops_kill.sql:215`).
- **Rollback:** `rollback_ops_kill_v1.sql` e `backup_instalado_v1.sql` não mudam. As linhas com os códigos novos ficam em `OPS_KILL_AUDIT` e não atrapalham a v1.
- **Migração:** a parte 1 não muda. A parte 2 recebe o mesmo body (§4c) e a conferência do §6.

## 6. Q6: `implantacao.md`

| Onde | Texto novo (resumo exato do conteúdo) |
|---|---|
| §1 `:24-31` | Entre as etapas 6 e 7: "Erro em qualquer etapa de 1 a 6: **ERRO_PRE_KILL**, com auditoria (`SQLERRM` em `mensagem`) e sem `ALTER SYSTEM`; o kill exige a flag `v_pode_encerrar`." |
| `:35` | "...o banco devolve ORA-00030, com código próprio **ALVO_AUSENTE_NO_KILL** (nenhuma sessão encerrada por esta chamada; NÃO executado, risco P2)." |
| §2(d) `:96-100` | Sem números de linha (L9). Exceção antes do `execute`: ERRO_ORACLE com desconhecido False. A partir do `execute`: ERRO_ORACLE com desconhecido **True**. `executado` só para `RESULTADOS_KILL_EXECUTADO` com desconhecido False (`registrar_decisao_kill`). Nenhum `except` tenta a assinatura antiga. |
| §3.2 `:139-152` | Ver o quadro abaixo. |
| `:158-163` | Título: "Gate ligado com o PKG v1 (erro de operação)". PLS-00306, RESULTADO `ERRO_ORACLE` com `resultado_desconhecido True`, e-mail e tela "resultado desconhecido: conferir sessão", nada em `OPS_KILL_AUDIT`. Testes sem conexão: `test_pls00306_no_execute_e_resultado_desconhecido` e T6 (`tests/test_item1_intencao.py`). |
| §4 `:167-170` | 1. Desligar o gate: parar a CLI e a Web e subir sem `OPS_KILL_PKG_VERSAO` (sem o aviso HABILITADO). 2. `rollback_ops_kill_v1.sql`, depois conferir VALID e o grant. 3. Sem `git revert`: o Python v2 com o gate desligado não chama o PKG, e o kill fica indisponível até nova decisão. A ordem 1 e 2 evita PLS-00306, que daria desconhecido. |
| `:206-209` | Troca o nome inexistente pelos dois testes reais e "NÃO executada" por "resultado desconhecido". |
| §5 sandbox `:212-219` | Acrescenta: "ERRO_PRE_KILL e ALVO_AUSENTE_NO_KILL **não têm teste sandbox** (não são provocáveis de forma determinística). Prova: testes estáticos do C1 e a conferência `DBA_SOURCE`." |
| §4.1 passo 3 `:185` | Acrescenta a conferência `DBA_SOURCE` abaixo. |

**Quadro §3.2 com o gate (S3):**
- **P (antes da janela):** ensaio 4.1 limpo.
- **3 (antes da janela):** a aplicação já roda a `main` integrada com o gate desligado. Conferir que nenhuma subida mostra "HABILITADO".
- **Durante a janela:** `KILL_DESABILITADO`, sem chamar o PKG.
- **▶ Início:** `inicio_janela`.
- **4:** spec e body v2.
- **5:** conferências e `DBA_SOURCE`. Se alguma falhar, rollback, e o gate continua desligado.
- **6:** só a sessão do operador sobe com `OPS_KILL_PKG_VERSAO=2` no shell, com o aviso "HABILITADO". É reinício, não implantação.
- **7:** sandbox ENCERRADA.
- **■ Fim.**
- **8:** demais testes.

**Conferência nova na parte 2** (depois de `parte2.sql:205`; esperado: 2 linhas, cada código com 1):
```sql
-- (2 linhas: ALVO_AUSENTE_NO_KILL 1; ERRO_PRE_KILL 1) O body instalado é o desta proposta.
SELECT REGEXP_SUBSTR(text, 'ALVO_AUSENTE_NO_KILL|ERRO_PRE_KILL') AS codigo, COUNT(*) AS linhas
  FROM dba_source
 WHERE owner = 'OPS_OWNER' AND name = 'PKG_OPS_KILL' AND type = 'PACKAGE BODY'
   AND REGEXP_LIKE(text, 'v_status := ''(ALVO_AUSENTE_NO_KILL|ERRO_PRE_KILL)''')
 GROUP BY REGEXP_SUBSTR(text, 'ALVO_AUSENTE_NO_KILL|ERRO_PRE_KILL')
 ORDER BY 1;
```
Ela fica fora dos blocos do pacote, então o §4c não muda. A regex do K2 não a captura, porque depois de `'` vem `'`.

## 7. A1 (fora das 6 perguntas): `v_type` nulo

- **O que acontece hoje:** `v_type <> 'USER'` com NULL **não recusa** (`ops_kill.sql:172`). A `GV$SESSION.TYPE` nula é improvável (inferência), mas é falha aberta.
- **Proposta:** `IF v_type IS NULL OR v_type <> 'USER' THEN` (já no texto do §1), com mutante M14. Decisão do responsável.

## 8. Ataque

- **Entradas:** LLM, CLI, Web e o rerun convergem no único `execute` de `matar_sessao_oracle`, por `registrar_decisao_kill`. A mudança é só de classificação do `p_status` e vale igual para todas. Não há leitura nova de ambiente, nem estado compartilhado novo entre abas, CLI e Web.
- **TOCTOU:**
  - entre a reconsulta DIAG e o PKG, a proteção é a checagem de identidade do PKG, que não muda;
  - entre o SELECT e o `ALTER SYSTEM`, continua a micro-janela, agora com código próprio;
  - a flag é variável em memória e não abre janela nova.
- **Exceção ou interrupção:**
  - falha do `registra` **depois** do kill: o handler do pré-kill não a cobre (asserção `chamadas[0] > others[1]` e só 2 `WHEN OTHERS`), a exceção sobe e o Python dá desconhecido;
  - erro na declaração (`SYS_CONTEXT`) ou pacote inválido (ORA-04068/04063): exceção, falso desconhecido conservador;
  - ORA-01013 dentro do bloco pré-kill: vira ERRO_PRE_KILL, sem kill. O cliente que cancelou já viu exceção, então desconhecido.
- **Versões cruzadas:**
  - Python atual × PKG novo: os códigos novos ficam fora das listas, e o resultado é desconhecido;
  - Python novo × v2 antigo: exceção (desconhecido) ou ALVO_NAO_ENCONTRADO (P2).
  - Falha fechado nos dois sentidos.
- **Concorrência (inferência, pré-existente, fora do escopo):** duas aprovações do mesmo alvo podem dar ORA-00031 na segunda. Ela relataria "executado" por um kill que foi da primeira. É imprecisão de atribuição, sem kill indevido.

## 9. Registros por desfecho

| `p_status` | Kill rodou? | OPS_KILL_AUDIT | JSONL `resultado_banco` / desconhecido | E-mail | LLM |
|---|---|---|---|---|---|
| ERRO_PRE_KILL | não (estrutural) | linha, `SQLERRM` 400 B, `alvo_*` nulos | ERRO_PRE_KILL / False | "NÃO executada (status ERRO_PRE_KILL)" (`:1818-1828`) | `MENSAGEM_ERRO_PRE_KILL` |
| ALVO_AUSENTE_NO_KILL | sim, ORA-00030 | linha, `alvo_*` do SELECT | ALVO_AUSENTE_NO_KILL / False | "NÃO executada" | `MENSAGEM_RECUSA_PKG` |
| ERRO_ORACLE (PKG) | sim, outro erro | linha com `SQLERRM` | ERRO_ORACLE / True | "resultado desconhecido" (`:1794-1806`) | `MENSAGEM_RESULTADO_DESCONHECIDO` |
| exceção depois do `execute` | talvez | talvez nenhuma | ERRO_ORACLE ou tipo / True | "resultado desconhecido" | código só (`:1216-1264`) |

O log local de erro (`_registrar_erro_local`) só aparece nos ramos de exceção. O status devolvido vai ao logger, com WARNING quando `executado=False` (`oracle_dba.py:2260-2267`).

## 10. Mutantes, com controle negativo (cada teste novo falha no código atual)

| Id | Mutação | Mata | Hoje |
|---|---|---|---|
| M1 | tira `v_status := 'ERRO_PRE_KILL'` do handler | K2 e §4b | — |
| M2 | põe o `EXECUTE IMMEDIATE` dentro do bloco pré-kill | §4b (`others[0] < pos_exec`) | — |
| M3 | `WHEN OTHERS` no nível da procedure, cobrindo o `registra` | §4b (2 `WHEN OTHERS`) | — |
| M4 | `v_pode_encerrar := TRUE` no handler | §4b (1 TRUE, antes do handler) | — |
| M5 | guarda do passo 7 sem a flag | §4b | — |
| M6 | -30 volta a dar `ALVO_NAO_ENCONTRADO` | K2 e §4b | — |
| M7 | muda o body só na parte 2 | §4c | **sobrevive hoje** |
| M8 | acrescenta `v_status := 'X2';` | §4b (contagem) | **sobrevive ao K2 de hoje** |
| M9 | tira ERRO_PRE_KILL de RECUSAS | K2 e §4e | — |
| M10 | ERRO_PRE_KILL também em EXECUTADO | K2 (disjuntas) | — |
| M11 | ramo ERRO_PRE_KILL com `MENSAGEM_RECUSA_PKG` | §4e | — |
| M12 | o fake sem a checagem de contrato | §4d | **sobrevive hoje** |
| M13 | o contrato do fake lido das listas do Python | §4d (FANTASMA) | — |
| M14 | `v_type <> 'USER'` sem o IS NULL (se A1 for aprovado) | §4b | — |

Controles no código atual:
- os casos novos do `test_k2_recusas` falham hoje, porque o ERRO_PRE_KILL dá desconhecido True;
- o §4b falha hoje, porque não há ERRO_PRE_KILL;
- o §4d falha hoje: o kwarg não existe (TypeError) e o fake não levanta.

## 11. PENDENTE APROVAÇÃO (responsável)

1. **Texto do pacote:** bloco ERRO_PRE_KILL, flag, ALVO_AUSENTE_NO_KILL e a conferência `DBA_SOURCE` na parte 2. Commit "PENDENTE APROVAÇÃO".
2. **Aceite de risco:** os dois códigos novos contam como "NÃO executado".
   - O ERRO_PRE_KILL tem prova só no texto.
   - O ALVO_AUSENTE_NO_KILL tem prova pela documentação do ORA-00030.
   - Nenhum dos dois tem evidência em sandbox, porque não são provocáveis. É a extensão do P2.
3. **A1:** incluir ou não o `v_type` null-safe.
4. **Rollback sem `git revert`:** o kill fica indisponível depois do rollback.
5. **Fora desta decisão, sem mudança:** privilégios, grants, lista de usuários protegidos e hash do `registry/`.

## 12. Fato × inferência

- **Fato:** §0 e as linhas citadas, conferidos agora, mais a sonda de igualdade dos blocos.
- **Esperado pela documentação Oracle, não verificado:**
  - a semântica do ORA-00030 e do ORA-00031;
  - as variáveis do INTO indefinidas depois de TOO_MANY_ROWS;
  - o handler cobrir só as instruções anteriores do seu bloco;
  - o `DBA_SOURCE` em linhas.
- **Inferência:** `GV$SESSION.TYPE` nula ser improvável; o ORA-00031 na segunda aprovação concorrente.
