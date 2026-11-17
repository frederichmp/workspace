# Item 6 — Identidade no PKG: proposta para aprovação

**Status: PENDENTE APROVAÇÃO. Nada aqui foi executado no banco nem implementado no Python.**

Arquivos desta pasta:

| Arquivo | Conteúdo |
|---|---|
| `ops_kill.sql` | Texto proposto do novo `db/ops_kill.sql` (instalação completa v2) |
| `ops_kill_v2_migracao_parte1.sql` | Migração, parte 1 (passos 0–2): pré-condições, backup e `ALTER TABLE`. **Não toca no pacote**; o kill v1 continua disponível |
| `ops_kill_v2_migracao_parte2.sql` | Migração, parte 2 (passos 3–4): spec e body v2 (cópia literal de `ops_kill.sql`) e conferências. É um arquivo separado para obrigar uma parada humana depois da parte 1 |
| `rollback_ops_kill_v1.sql` | Spec e body v1 (cópia literal do `db/ops_kill.sql` atual) e conferências |

Os três `.sql` executáveis começam com `WHENEVER SQLERROR EXIT FAILURE ROLLBACK`. Eles foram gerados a partir das fontes por script, e a geração confere que a spec e o body copiados são idênticos à v2 proposta e à v1 do repositório.

Quem executa: **STARTUPADMIN**, com `ALTER SESSION SET CURRENT_SCHEMA = OPS_OWNER`. O `OPS_OWNER` é conta bloqueada e não faz login; ele é só o dono dos objetos.

## 1. O que muda no banco

- `KILL_SESSION` passa de 4 para 9 parâmetros:
  - continuam `p_inst_id`, `p_sid`, `p_serial` e `p_status OUT`;
  - novos: `p_username_esperado`, `p_program_esperado`, `p_machine_esperado`, `p_logon_time_esperado` (`DATE`) e `p_ref_aprovacao` (`id_intervencao` do item 1, 32 caracteres hex).
- **Sem sobrecarga e sem DEFAULT.**
- Ordem das checagens dentro do PKG:
  1. **PARAM_INVALIDO**: ids nulos ou ≤ 0, `username` ou `logon_time` esperado nulo, textos esperados acima de 128 bytes (o tamanho das colunas da `GV$SESSION`), ou `ref` fora de `^[0-9a-f]{32}$`. Esse padrão é aplicado com `REGEXP_LIKE(..., 'c')`, sensível a maiúsculas qualquer que seja o `NLS_SORT`.
  2. **PROPRIA_SESSAO.**
  3. **Um único SELECT** na `GV$SESSION`, que lê o alvo e já calcula os campos divergentes (`DECODE`, comparação null-safe). Os textos são comparados como RAW (`UTL_RAW.CAST_TO_RAW`), então o resultado não depende de `NLS_COMP`/`NLS_SORT` da sessão que chama. Sem linha: ALVO_NAO_ENCONTRADO.
  4. **ALVO_DIVERGENTE**, se houver campo divergente.
  5. **NAO_USUARIO.**
  6. **USUARIO_PROTEGIDO.**
  7. `ALTER SYSTEM KILL SESSION`.
- `OPS_KILL_AUDIT` ganha três colunas anuláveis: `alvo_logon_time`, `ref_aprovacao` e `campos_divergentes`. Os valores observados vão nas colunas `alvo_*`; os esperados divergentes vão em `mensagem`.
- Micro-janela entre o SELECT e o `ALTER SYSTEM`: aceita.
  - O comando é endereçado por `sid` + `serial#`.
  - Se o SID for reutilizado, o `serial#` muda e o banco devolve ORA-00030, tratado como ALVO_NAO_ENCONTRADO.
  - O Oracle não oferece "comparar e matar" atômico.

### 1.1 `p_ref_aprovacao`: origem e uso (é só registro)

| Pergunta | Resposta |
|---|---|
| Quem gera | A aplicação. `registrar_decisao_kill` (item 1) cria `id_intervencao = uuid4().hex`, com 32 caracteres hex minúsculos, no momento em que grava a linha **INTENCAO** em `kill_approval.log`. A linha **RESULTADO** usa o mesmo valor |
| Como chega ao banco | `registrar_decisao_kill` → `executar_kill_verificado(..., id_intervencao)` → `matar_sessao_oracle(..., ref_aprovacao=id_intervencao)` → bind `:p_ref_aprovacao`. O LLM não fornece nem vê esse valor |
| Quem valida | **A aplicação**, antes de conectar: formato `^[0-9a-f]{32}$`; fora disso, PARAM_INVALIDO local. **O pacote**: NOT NULL e o mesmo formato com `'c'`; fora disso, PARAM_INVALIDO, sem kill e com linha de auditoria |
| O que o banco faz | Só grava em `OPS_KILL_AUDIT.ref_aprovacao`, para ligar a linha de auditoria do banco às linhas INTENCAO/RESULTADO do log da aplicação |
| O que o banco **não** faz | Não verifica se a aprovação existe, quem aprovou ou se ainda está no prazo. O banco não lê o log da aplicação. **Não é autorização.** A autorização continua sendo o fluxo HITL da aplicação (itens 1 e 7) mais o grant EXECUTE restrito a STARTUP_KILL |

O texto da spec em `ops_kill.sql` traz o mesmo esclarecimento no comentário de `kill_session`.

## 2. Por que a versão antiga do banco REJEITA os parâmetros novos (e não os ignora)

A afirmação "falha de forma segura em qualquer ordem" só vale se as quatro condições abaixo forem verdadeiras ao mesmo tempo. Cada uma tem um lugar no código e um teste.

**(a) O Python chama por associação NOMEADA, num único bloco anônimo.** Hoje ([oracle_dba.py:728-746](../../../../src/tools/oracle_dba.py#L728-L746)):
```python
cursor.execute(
    """
    BEGIN
        OPS_OWNER.PKG_OPS_KILL.KILL_SESSION(
            p_inst_id => :p_inst_id,
            p_sid     => :p_sid,
            p_serial  => :p_serial,
            p_status  => :p_status
        );
    END;
    """, ...)
```
Proposta v2 (único ponto de chamada; os 9 formais por nome):
```python
"""
BEGIN
    OPS_OWNER.PKG_OPS_KILL.KILL_SESSION(
        p_inst_id             => :p_inst_id,
        p_sid                 => :p_sid,
        p_serial              => :p_serial,
        p_username_esperado   => :p_username_esperado,
        p_program_esperado    => :p_program_esperado,
        p_machine_esperado    => :p_machine_esperado,
        p_logon_time_esperado => :p_logon_time_esperado,
        p_ref_aprovacao       => :p_ref_aprovacao,
        p_status              => :p_status
    );
END;
"""
```

**(b) O banco v1 não tem esses formais.** O bloco anônimo é compilado no servidor durante o `cursor.execute`. Na compilação, o PL/SQL resolve cada `nome =>` contra a spec do pacote.
- Contra a spec v1 ([db/ops_kill.sql:26-31](../../../../db/ops_kill.sql#L26-L31)), `p_username_esperado` não existe. O resultado é `ORA-06550 ... PLS-00306: wrong number or types of arguments in call to 'KILL_SESSION'`.
- PL/SQL não tem argumentos variáveis e não descarta parâmetro desconhecido. O erro é de compilação, então **nada do bloco executa**: não há kill nem linha em `OPS_KILL_AUDIT`.
- O inverso também falha: o Python v1, com 4 argumentos, contra a spec v2 deixa sem valor formais obrigatórios. Também dá PLS-00306.

**(c) A spec v2 não tem DEFAULT nem sobrecarga.** Ver `ops_kill.sql`, `CREATE OR REPLACE PACKAGE pkg_ops_kill`.
- Se algum parâmetro novo tivesse DEFAULT, a chamada v1 **compilaria**, e a proteção passaria a depender só das checagens do body. Com este body, `username` nulo ainda daria PARAM_INVALIDO, mas um DEFAULT em `program`/`machine` desativaria a comparação desses campos sem nenhum erro. É exatamente o caminho silencioso que a decisão de identidade obrigatória quer evitar.
- A migração confere isso em `DBA_ARGUMENTS`: 9 linhas, `OVERLOAD` nulo, nenhum `DEFAULTED = 'Y'`.

**(d) Erro de banco nunca vira "executado" nem tem fallback.**
- `oracledb.DatabaseError` é subclasse de `oracledb.Error` e cai em [oracle_dba.py:765-777](../../../../src/tools/oracle_dba.py#L765-L777): `status_banco = "ERRO_ORACLE"`.
- `executado = resultado_banco in RESULTADOS_KILL_EXECUTADO` ([oracle_dba.py:1147](../../../../src/tools/oracle_dba.py#L1147), conjunto definido em [:40](../../../../src/tools/oracle_dba.py#L40)) dá `False`.
- O e-mail sai pelo ramo "NÃO executada" ([oracle_dba.py:991-1006](../../../../src/tools/oracle_dba.py#L991-L1006)).
- Não existe hoje, e a proposta não cria, nenhum `except` que tente a assinatura antiga.

**(e) Conexão por chamada.** `matar_sessao_oracle` abre a conexão a cada chamada ([oracle_dba.py:721](../../../../src/tools/oracle_dba.py#L721)) e a fecha no `finally` ([:792-800](../../../../src/tools/oracle_dba.py#L792-L800)).
- Por isso nenhum estado de pacote passa de uma chamada para outra, e o bloco é sempre compilado contra a spec vigente.
- Python v1 × spec v2 dá sempre PLS-00306; ORA-04068 não se aplica ao Python atual.
- Se um dia houver pool ou conexão persistente, a primeira chamada depois da recompilação poderá receber ORA-04068. Seria seguro (vira ERRO_ORACLE, sem nova tentativa), mas o pedido do operador falharia e teria de ser repetido.

**Limite desta evidência:** (b) é a semântica de compilação do PL/SQL, mas **não foi executada contra um banco** nesta tarefa. Ela só fica provada pelos testes sandbox da seção 5, que rodam apenas com `ORACLE_SANDBOX=1` numa sessão autorizada.

## 3. Ordem de implantação (primeiro o banco, depois o Python)

### 3.1 Por que não dá para compilar o body v2 mantendo a spec v1

A ordem "compilar o body v2 com a spec v1 mantida e trocar a spec depois" **não funciona no Oracle**:

1. **O body tem de implementar o que a spec declara.**
   - A spec v1 declara `kill_session(p_inst_id, p_sid, p_serial, p_status)`.
   - O body v2 só implementa a versão de 9 parâmetros. Para o compilador, ela seria uma sobrecarga privada.
   - A compilação falha com `PLS-00323: subprogram or cursor 'KILL_SESSION' is declared in a package specification and must be defined in the package body`.
   - O body fica **INVALID**. A partir daí, toda chamada (inclusive a do Python v1) recebe `ORA-04063: package body has errors`.
   - Ou seja: a indisponibilidade começaria **antes**, já na compilação do body, e não depois.
2. **O `CREATE OR REPLACE` da spec invalida o body de qualquer forma.**
   - Mesmo que o body v2 tivesse compilado, a troca posterior da spec o deixaria INVALID, e ele teria de ser recompilado.
   - O Oracle exige que a spec venha primeiro e o body depois.
3. **Manter as duas versões ao mesmo tempo** (o body implementa a de 4 e a de 9 parâmetros, e a spec v1 declara só a de 4) não ajuda:
   - a de 9 parâmetros seria privada, e o Python não conseguiria chamá-la;
   - para torná-la pública, a spec teria de declarar as duas. Isso é a sobrecarga que a decisão de identidade obrigatória exclui, porque deixa vivo o caminho de kill sem identidade.

Portanto a ordem possível é **spec v2 e logo em seguida body v2, no mesmo script** (`ops_kill_v2_migracao_parte2.sql`), e só depois o Python v2. A janela de indisponibilidade é inevitável **sem sobrecarga**; o que se controla é a duração dela.

### 3.2 Sequência com a janela explícita

| Passo | Ação | Kill disponível? |
|---|---|---|
| P | **Pré-requisito, antes de marcar a janela:** ensaio de banco em sandbox (seção 4.1) concluído, com `DBA_ERRORS` vazio para a v2 **e** para a v1 restaurada, e saídas registradas. Sem isso, a janela não é marcada | sim (v1) |
| 0 | **Parte 1.** Pré-condições: dependências, grants, `EXECUTE ANY PROCEDURE`, jobs (scheduler, programas, `DBA_JOBS`), `GV$SQL` (só indício), privilégios do OPS_OWNER, `UTL_RAW`. **Responsável confirma que não há outros chamadores.** | sim (v1) |
| 1 | **Parte 1.** Backup via `DBMS_METADATA` (spec, body, tabela, grants). Comparar com `rollback_ops_kill_v1.sql`; se divergir, **parar** | sim (v1) |
| 2 | **Parte 1.** `ALTER TABLE ... ADD` (aditivo); conferir que o body continua VALID | sim (v1) |
| — | **Parada humana:** avaliar as saídas da parte 1. Sem isso, não executar a parte 2 | sim (v1) |
| 3 | Parar a CLI e a Web (`main.py`, `app.py`), deixar o commit Python v2 pronto e conferido (`pytest -q` verde) | **não** (aplicação parada) |
| **▶ INÍCIO DA JANELA** | **Parte 2:** o script grava `SELECT SYSTIMESTAMP AS inicio_janela` imediatamente antes do `CREATE OR REPLACE` da spec v2. A partir daqui o banco recusa a chamada v1 (PLS-00306) | **não** |
| 4 | **Parte 2.** Spec v2 e, em seguida, body v2 | **não** |
| 5 | **Parte 2.** Conferências: `DBA_ERRORS` vazio; spec e body VALID; `DBA_ARGUMENTS` com 9 linhas, sem sobrecarga e sem DEFAULT; grant presente. Falhou alguma? Rollback (seção 4) | **não** |
| 6 | Implantar o Python v2 (checkout do commit do item 6) e reiniciar a CLI e a Web | **não** (até o passo 7) |
| 7 | Primeiro teste sandbox v2 com identidade correta → ENCERRADA (seção 5) | **sim (v2)** |
| **■ FIM DA JANELA** | Hora do teste do passo 7 com ENCERRADA. Registrar `inicio_janela` e fim no GOVERNANCA_LOG | sim (v2) |
| 8 | Demais testes sandbox v2 (divergência, null-safe, protegido etc.) | sim (v2) |

- **Início da janela:** o `SYSTIMESTAMP` gravado pela parte 2 imediatamente antes da troca da spec.
- **Fim da janela:** o primeiro kill sandbox v2 com ENCERRADA (passo 7).
- **Duração esperada:** a parte 2 leva segundos. O que domina é o passo 6 (implantar e reiniciar a aplicação), por isso o passo 3 deixa tudo pronto antes.
- **Durante toda a janela,** qualquer chamada recebe erro do banco e vira `ERRO_ORACLE` com `executado=False`. Nenhuma sessão é encerrada.
- **Quando fazer:** marcar a janela para quando nenhuma intervenção for necessária.

**Alternativa sem janela (não recomendada):**
- Criar um pacote novo, `PKG_OPS_KILL_V2`, ao lado do atual, conceder EXECUTE, implantar o Python v2 e depois revogar e remover o v1.
- Elimina a indisponibilidade, mas mantém um caminho de kill **sem identidade** (o v1) acessível até ser removido. Exige decisão explícita do responsável.

**Se o Python for implantado ANTES do banco** (Python v2 × PKG v1), cada APROVADO:
- grava INTENCAO, reconsulta, confere o hash e chama o PKG, que recebe PLS-00306;
- grava RESULTADO com `resultado_banco = ERRO_ORACLE` e `executado = False`;
- envia o e-mail "NÃO executada (status ERRO_ORACLE)", e a tela mostra "NÃO executada".

Nenhuma sessão é encerrada e nenhuma linha é gravada em `OPS_KILL_AUDIT`, porque o PKG não chega a rodar. O efeito é **seguro, mas o kill fica indisponível** até o banco ser migrado.

## 4. Rollback

1. Executar `rollback_ops_kill_v1.sql`. As colunas novas ficam, porque o body v1 usa INSERT com lista de colunas. Conferir VALID e o grant.
2. `git revert` do commit Python do item 6.

Entre 1 e 2, o kill fica indisponível (Python v2 × PKG v1 dá ERRO_ORACLE), de forma segura.

**O rollback foi ensaiado SÓ COMO ARQUIVO. Ele NÃO foi ensaiado no banco.** Até aqui, nada prova que a spec e o body v1 restaurados compilam, que o grant se mantém ou que o kill v1 volta a funcionar. **O ensaio no banco (seção 4.1) é pré-requisito da janela de implantação** (passo P da seção 3.2).

O que o ensaio como arquivo prova (`docs/entregas/1.11/verif_item9_ensaio_rollback.md`, parte B):
- Num clone descartável, aplicou-se a v2 em `db/ops_kill.sql` e depois restauraram-se a spec e o body a partir de `rollback_ops_kill_v1.sql`. O texto ficou **idêntico** ao da v1 do repositório (sha `4823ecca4cfd8b21`), com as colunas v2 mantidas.
- `tests/test_oracle_kill.py` no clone deu 33 passed e 6 skipped. Esses testes exercitam o Python. O único que lê o arquivo SQL é `test_lista_protegida_alinhada_ao_pacote` (`c_protegidos`), e ele **não compila nada**.
- Os testes sandbox de kill **não foram executados**, porque exigem Oracle.

### 4.1 Ensaio de banco em sandbox (pré-requisito da janela)

Executado só em **sandbox autorizado**: banco de teste, com `ORACLE_SANDBOX=1` definida apenas na sessão de execução autorizada. Quem executa é o STARTUPADMIN. Todas as saídas vão para `docs/entregas/<tarefa>/` e para o GOVERNANCA_LOG.

1. **Estado inicial:** v1 instalada, Python v1. Rodar os `test_sandbox_kill_*` atuais e registrar que passam (linha de base).
2. **Parte 1** no sandbox (pré-condições, backup, `ALTER TABLE`).
3. **Parte 2** no sandbox. Conferências da v2: `DBA_ERRORS` **vazio**; spec e body VALID; `DBA_ARGUMENTS` com 9 linhas, sem sobrecarga e sem DEFAULT; grant presente.
4. **Testes sandbox de transição:** bloco v1 contra o PKG v2 dá PLS-00306, com o alvo vivo e sem auditoria. Com o Python v2 (branch do item 6): testes sandbox v2 da seção 5.
5. **Rollback:** `rollback_ops_kill_v1.sql` no sandbox. Conferências que **provam que a v1 restaurada compila**:
   - `DBA_ERRORS` **vazio** para `OPS_OWNER.PKG_OPS_KILL`;
   - spec e body **VALID** em `DBA_OBJECTS`;
   - `DBA_ARGUMENTS` com **4** linhas (`P_INST_ID`, `P_SID`, `P_SERIAL`, `P_STATUS`), sem sobrecarga;
   - grant EXECUTE para STARTUP_KILL presente.
6. **Depois do rollback**, com o Python v1: os `test_sandbox_kill_*` atuais passam de novo, como na linha de base do passo 1. As colunas v2 continuam na tabela e não atrapalham.
7. **Registro:** saídas brutas de cada passo e veredito. Só com os passos 3 e 5 limpos a janela de produção pode ser marcada.

O clone de arquivo **não substitui** nenhum desses passos. A checagem de `DBA_ERRORS` só tem valor no banco.

## 5. Testes que provam cada parte

**Sem conexão** (suíte padrão; provam o lado Python):
- `test_kill_chamada_nomeada_nove_formais`: o fake da conta KILL captura o SQL e exige as 9 associações `nome => :nome`, sem argumento posicional, e binds iguais à reconsulta.
- `test_kill_ponto_unico_de_chamada` — **teste de Python com fake**:
  - O fake da conta KILL (`_CursorFake.execute`) registra cada `execute`.
  - O teste conduz o fluxo completo (`conduzir_kill_hitl` com APROVADO) em três cenários: o PKG devolve ENCERRADA; o PKG devolve ALVO_DIVERGENTE; o `execute` levanta erro.
  - Em cada cenário exige **exatamente 1** `execute` na conta KILL e **exatamente 1** conexão KILL. Esse único `execute` tem o SQL `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION` com os 9 binds nomeados.
  - Prova pelo comportamento, não por busca no código-fonte, que não existe segunda chamada nem chamada alternativa de 4 parâmetros em nenhum dos caminhos.
- `test_kill_pls00306_vira_erro_oracle` — **teste de Python com fake; não prova nada sobre o banco**:
  - O fake da conta KILL simula o erro levantando `oracledb.DatabaseError("ORA-06550 ... PLS-00306 ...")` no `execute`.
  - O teste prova só o lado Python: diante desse erro, há 1 `execute` e nenhuma nova tentativa; `resultado_banco = ERRO_ORACLE` e `executado False`; o e-mail é "NÃO executada", nunca "Aprovada"; o RESULTADO é gravado.
  - Que o banco v1 **de fato** devolve PLS-00306 para a chamada v2 só fica provado pelo teste sandbox "Python v2 × PKG v1" (abaixo e seção 4.1).
- `test_identidade_obrigatoria_param_invalido`: identidade vazia ou incompleta, ou `ref` inválida, dá PARAM_INVALIDO antes de qualquer `getenv` ou `connect`.

**Sandbox** (`ORACLE_SANDBOX=1`, só em sessão autorizada; provam o lado banco):
- **Python v2 × PKG v1:** ERRO_ORACLE com `ORA-06550`/`PLS-00306`; sessão alvo viva; contagem de `OPS_KILL_AUDIT` inalterada.
- **Bloco v1 literal (4 argumentos) × PKG v2:** PLS-00306; alvo vivo; sem linha de auditoria.
- **v2 com identidade correta:** ENCERRADA.
- **v2 com `program` ou `logon_time` errado:** ALVO_DIVERGENTE, com linha em `OPS_KILL_AUDIT` (`campos_divergentes` preenchido) e sessão viva.
- **v2 com `program` diferente só em maiúsculas e a sessão chamadora em `NLS_COMP=LINGUISTIC`/`NLS_SORT=BINARY_CI`:** ALVO_DIVERGENTE. Prova que a comparação é binária.
- **Comparação null-safe:** esperado NULL contra observado NULL → ENCERRADA; esperado não nulo contra observado NULL → ALVO_DIVERGENTE.
- **Esperado com mais de 128 bytes, ou `ref` em hexadecimal maiúsculo:** PARAM_INVALIDO, com linha de auditoria.
- **Usuário protegido com a conexão alvo aberta:** USUARIO_PROTEGIDO (corrige o achado 6.5).

## 6. Decisões do responsável neste item

**Aprovadas pelo responsável (2026-11-17):**

| # | Decisão | Status |
|---|---|---|
| 2 | `p_ref_aprovacao` obrigatório | **aprovado** |
| 3 | `program` e `machine` podem ser NULL (comparação null-safe); `username` e `logon_time`, não | **aprovado** |
| 5 | Variável `OPS_KILL_PKG_VERSAO=1\|2`, definida pelo operador; testes sandbox de transição com skip quando a versão não bate | **aprovado** |
| 6 | Janela de implantação da seção 3.2: início no `inicio_janela` da parte 2, antes da spec v2; fim no primeiro kill sandbox v2 com ENCERRADA. A alternativa sem janela foi **rejeitada** | **aprovado** |

**Pendentes:**

| # | Pendência | Depende de |
|---|---|---|
| 1 | Aprovar o texto do SQL v2, da migração e do rollback | Ensaio de banco em sandbox (seção 4.1), que é pré-requisito |
| 4 | Quem pode chamar o pacote (redação do responsável, 2026-11-17). **EXECUTE explícito**: só `STARTUP_KILL`. **EXECUTE efetivo**: também as contas administrativas `STARTUPADMIN`, `SYS` e `SYSTEM`, por herança de `DBA`/`DV_REALM_OWNER`/`EXP_FULL_DATABASE`/`IMP_FULL_DATABASE`, mais `OUTLN` e `WMSYS`, por concessão direta (EXPIRED & LOCKED). Nenhuma conta de aplicação. **Risco aceito, idêntico ao atual** | Parte de privilégios **fechada** (7.3 encerrada). Ainda faltam 0.1 (`DBA_DEPENDENCIES`), 0.3 (jobs) e 0.4 (`GV$SQL`), lidos na parte 1 |
| 7.1 | Contas READ/MUT do executor na conferência de papéis | Nomes a informar pelo responsável |
| 7.2 | Database Vault: **encerrada** (DV inativo). Residual **encerrado**: `DV_REALM_OWNER` só chega a contas administrativas (7.3) | — |
| 7.3 | Leituras 1 e 2: **ENCERRADA** em 2026-11-17 (seção 7.3). Não altera a janela nem a decisão 1 | — |

## 7. Resultados das leituras autorizadas (MODELO, STARTUPADMIN, somente leitura)

Informados pelo responsável em 2026-11-17. **Não executado:** partes 1 e 2, rollback, nenhum ALTER, GRANT ou KILL.

| Checagem | Resultado | Avaliação |
|---|---|---|
| Estado | `PACKAGE` e `PACKAGE BODY` `PKG_OPS_KILL` VALID; `DBA_ARGUMENTS` de `KILL_SESSION` = 4 | Linha de base v1 confirmada. É a mesma assinatura de `rollback_ops_kill_v1.sql` |
| 0.2a | EXECUTE em `OPS_OWNER.PKG_OPS_KILL` concedido **só** a `STARTUP_KILL` | Conforme o esperado |
| 0.2b | `EXECUTE ANY PROCEDURE` concedido a `DBA`, `DV_REALM_OWNER`, `EXP_FULL_DATABASE`, `IMP_FULL_DATABASE`, `OUTLN`, `SYS`, `WMSYS` | **Alcance da consulta (correção de 2026-11-17):** usou `DBA_SYS_PRIVS`, que mostra **só concessões diretas**. Ela não cobre `EXECUTE ANY PROCEDURE` herdado por papel; isso é a leitura 2 (seção 7.3). `DBA`, `DV_REALM_OWNER`, `EXP_FULL_DATABASE` e `IMP_FULL_DATABASE` são **papéis**: todo usuário que os tenha, inclusive por papel aninhado, pode chamar `KILL_SESSION` sem passar pelo grant restrito. **Correção:** a versão anterior desta linha os chamava de "fornecidos pelo Oracle" como se isso tivesse sido verificado. Não tinha sido. A verificação está na seção 7.1, e `DV_REALM_OWNER` continua não verificado (7.2) |
| 0.6 | EXECUTE em `SYS.UTL_RAW` concedido a `PUBLIC` | A compilação da v2 não é bloqueada por esta checagem (definer-rights aceita grant a PUBLIC) |

**Leitura do risco de 0.2b:**
- Quem tem `EXECUTE ANY PROCEDURE` por um papel DBA normalmente também tem `ALTER SYSTEM` e pode encerrar sessões diretamente. Para essas contas, o pacote não é a barreira, e isso vale para a v1 e para a v2.
- A v2 não piora esse quadro: quem a chama por esse caminho ainda precisa passar a identidade correta, senão recebe ALVO_DIVERGENTE.
- O risco que importa é uma **conta de aplicação** do projeto ter um desses papéis: `STARTUP_DIAG`, `STARTUP_KILL` ou as contas READ/MUT do executor, cujos nomes estão no `.env`, que esta sessão não lê.
- As consultas 0.2c e 0.2d, acrescentadas à parte 1, respondem a isso. O responsável deve incluir na conferência os nomes das contas READ/MUT.

### 7.1 Fechamento da pendência 0.2b (2026-11-17, leitura autorizada, MODELO)

Informado pelo responsável:
- Os papéis `EXP_FULL_DATABASE` e `IMP_FULL_DATABASE` estão concedidos **somente** a `DATAPUMP_EXP_FULL_DATABASE`, `DATAPUMP_IMP_FULL_DATABASE`, `DBA` e `SYS`.
- **Nenhuma conta de aplicação** (`STARTUP_KILL`, `STARTUP_DIAG`) recebeu esses papéis. `STARTUPADMIN` também está fora dessa lista.
- `WMSYS` e `OUTLN` estão **EXPIRED & LOCKED**: não fazem login, então não usam o privilégio.

O que isso fecha e o que não fecha:
- **Fecha:** o caminho por `EXP_FULL_DATABASE`/`IMP_FULL_DATABASE` não alcança contas de aplicação; `WMSYS` e `OUTLN` estão inativas.
- **Não muda:** o papel `DBA` dá `EXECUTE ANY PROCEDURE` a quem o tem. Essas contas também podem encerrar sessões diretamente com `ALTER SYSTEM`, e o pacote não é a barreira para elas, nem na v1 nem na v2. É risco aceito e documentado; não é uma regressão da v2.
- **Contas que herdam esse risco** (leitura 2, 7.3): `STARTUPADMIN`, `SYS` e `SYSTEM` (contas de administração), por herança de `DBA`/`DV_REALM_OWNER`/`EXP_FULL_DATABASE`/`IMP_FULL_DATABASE`. Também `OUTLN` e `WMSYS`, por concessão direta, mas EXPIRED & LOCKED, sem execução enquanto bloqueadas. Nenhuma conta de aplicação; `PUBLIC` sem papéis concedidos.
- **Correção do registro de 7.1 (2026-11-17):** o 0.2b usou `DBA_SYS_PRIVS`, só concessões diretas. O fechamento acima vale para o caminho `EXP_FULL_DATABASE`/`IMP_FULL_DATABASE` relatado. Ele **não** encerra a questão do `EXECUTE ANY PROCEDURE` herdado por papel, que é a leitura 2.
- **Fora do relato:** as contas READ/MUT do executor (nomes no `.env`, que esta sessão não lê) não foram citadas na leitura. Se fizerem parte da conferência do responsável, registrar aqui.

### 7.2 Pendência reaberta: Database Vault (não bloqueia a janela)

`DV_REALM_OWNER` aparece em 0.2b como detentor de `EXECUTE ANY PROCEDURE`. Ele **é um papel** do Database Vault, não uma conta. Por isso não aparece em `DBA_USERS`, e a ausência ali não diz nada sobre ele. Consultas de leitura para identificar o que existe:

```sql
-- O papel existe? (esperado: 1 linha se o Database Vault estiver instalado no catálogo)
SELECT role FROM dba_roles WHERE role LIKE 'DV\_%' ESCAPE '\' ORDER BY role;
-- Quem tem o papel (direta ou indiretamente)
SELECT DISTINCT grantee FROM dba_role_privs
 START WITH granted_role = 'DV_REALM_OWNER'
 CONNECT BY PRIOR grantee = granted_role
 ORDER BY grantee;
-- O Database Vault está habilitado? (12c+: dba_dv_status; alternativa: v$option)
SELECT name, status FROM dba_dv_status;
SELECT parameter, value FROM v$option WHERE parameter = 'Oracle Database Vault';
-- Contas típicas de DV (o nome real é definido na configuração do DV)
SELECT username, account_status FROM dba_users
 WHERE username IN (SELECT grantee FROM dba_role_privs WHERE granted_role IN ('DV_OWNER', 'DV_ACCTMGR'))
 ORDER BY username;
```

Critério: nenhuma conta de aplicação do projeto tem `DV_REALM_OWNER`. **Correção:** uma versão anterior deste critério dizia que, com o DV desabilitado, o papel "existe só no catálogo" e a pendência se encerraria. Isso está impreciso. Um papel concedido vale com o DV ativo ou não, e `DV_REALM_OWNER` tem `EXECUTE ANY PROCEDURE` (0.2b). Desabilitar o DV elimina as regras de DV, mas não esse privilégio.

**Resultado (leitura autorizada, MODELO, 2026-11-17), ENCERRADA pelo responsável:**
- `V$OPTION` 'Oracle Database Vault' = FALSE.
- `DBA_DV_STATUS` `DV_CONFIGURE_STATUS` = FALSE.
- 15 papéis `DV_*` presentes no catálogo, sem ativação.
- Conclusão: Database Vault inativo; nenhuma regra de DV bloqueia `ALTER SYSTEM` ou KILL neste banco.

**Checagem residual (não bloqueante, leitura):** quem detém `DV_REALM_OWNER`, direta ou indiretamente. Ela ainda não foi relatada; a leitura de 7.1 cobriu só `EXP_FULL_DATABASE` e `IMP_FULL_DATABASE`. A segunda consulta acima (`START WITH granted_role = 'DV_REALM_OWNER'`) responde a isso. Esperado: nenhuma conta de aplicação.

### 7.3 Pendência: leituras 1 e 2 (somente leitura; nada alterado)

**Correção de registro (2026-11-17):** a afirmação "`STARTUP_KILL` só tem CREATE SESSION" foi confirmada **apenas para privilégios e papéis diretos** (`DBA_SYS_PRIVS` e `DBA_ROLE_PRIVS`, consulta 0.2d). Ela não cobre papéis aninhados nem o que fica efetivo na sessão, e fica **substituída pela leitura 1** quando autorizada.

**Leitura 1 — privilégios e papéis efetivos de `STARTUP_KILL`.** O operador executa conectado **como `STARTUP_KILL`**; a credencial não passa por esta sessão.
```sql
-- Privilégios de sistema efetivos na sessão (diretos + herdados por papéis habilitados)
-- Esperado: só CREATE SESSION
SELECT privilege FROM session_privs ORDER BY privilege;
-- Papéis habilitados na sessão (esperado: nenhum)
SELECT role FROM session_roles ORDER BY role;
-- Papéis concedidos, inclusive os não-default que session_roles não mostra (esperado: nenhum)
SELECT granted_role, default_role FROM user_role_privs ORDER BY granted_role;
```
EXECUTE no pacote é privilégio de objeto e não aparece em `session_privs`; ele já foi confirmado pelo 0.2a.

**Leitura 2 — contas com `EXECUTE ANY PROCEDURE` efetivo**, direto ou herdado por papel (inclusive aninhado). Executar como STARTUPADMIN.
```sql
WITH detentores AS (
  SELECT grantee FROM dba_sys_privs WHERE privilege = 'EXECUTE ANY PROCEDURE'
  UNION
  SELECT grantee FROM dba_role_privs
   START WITH granted_role IN (SELECT grantee FROM dba_sys_privs WHERE privilege = 'EXECUTE ANY PROCEDURE')
   CONNECT BY PRIOR grantee = granted_role
)
SELECT u.username, u.account_status
  FROM dba_users u JOIN detentores d ON d.grantee = u.username
 ORDER BY u.username;
-- Se PUBLIC estiver entre os detentores, TODA conta herda (esperado: 0 linhas)
WITH detentores AS (
  SELECT grantee FROM dba_sys_privs WHERE privilege = 'EXECUTE ANY PROCEDURE'
  UNION
  SELECT grantee FROM dba_role_privs
   START WITH granted_role IN (SELECT grantee FROM dba_sys_privs WHERE privilege = 'EXECUTE ANY PROCEDURE')
   CONNECT BY PRIOR grantee = granted_role
)
SELECT grantee FROM detentores WHERE grantee = 'PUBLIC';
```

Critérios:
- Nenhuma conta de aplicação do projeto (`STARTUP_KILL`, `STARTUP_DIAG` e as contas READ/MUT, cujos nomes o responsável informa) aparece na leitura 2.
- `PUBLIC` não aparece.
- A lista resultante passa a ser, por escrito, o conjunto de contas com **EXECUTE efetivo** no pacote (decisão 4) e o conjunto do risco aceito do DBA (7.1).

**Resultado (2026-11-17, MODELO, só leitura, informado pelo responsável): ENCERRADA.** Não altera a janela nem a decisão 1.

**Correção de registro (2026-11-17):** uma versão anterior desta seção marcava a 7.3 como ENCERRADA. O status correto, informado pelo responsável, é parcialmente fechada.

| Conta / item | `session_privs` | `session_roles` | Avaliação |
|---|---|---|---|
| `STARTUP_KILL` (leitura 1, conectado como a conta) | CREATE SESSION | nenhum | `user_role_privs` **sem linhas**: nenhum papel concedido, habilitado ou não. Privilégio efetivo = CREATE SESSION |
| `STARTUP_DIAG` | CREATE SESSION | `HS_ADMIN_SELECT_ROLE`, `SELECT_CATALOG_ROLE` | Leitura 2 (como STARTUPADMIN): `SELECT_CATALOG_ROLE` concedido **diretamente** (default YES). `HS_ADMIN_SELECT_ROLE` vem **por herança** de `SELECT_CATALOG_ROLE`; não há concessão direta. **Decisão: não revogar** |
| `EXECUTE ANY PROCEDURE` efetivo (leitura 2, como STARTUPADMIN) | — | — | `STARTUPADMIN`, `SYS` e `SYSTEM` (ativas, administração). `OUTLN` e `WMSYS` por concessão direta, EXPIRED & LOCKED (sem execução enquanto bloqueadas). **Nenhuma conta de aplicação** |
| `PUBLIC` | — | — | Sem papéis concedidos |

**Fechamento dos residuais (2026-11-17):**
- **`STARTUP_KILL`:** `user_role_privs` sem linhas, então não há papel concedido, nem habilitado nem não-default. O conjunto efetivo é CREATE SESSION mais o EXECUTE de objeto em `PKG_OPS_KILL` (0.2a).
- **`HS_ADMIN_SELECT_ROLE` em `STARTUP_DIAG`:** é herança de `SELECT_CATALOG_ROLE`, que foi concedido diretamente. Pela regra do responsável, **não revogar**.
  - **Consequência registrada pelo responsável:** `STARTUP_DIAG` tem leitura via Heterogeneous Services, sem escrita nem kill.
  - **Precisão:** o papel dá `SELECT` nas visões de dicionário `HS_*` (configuração do Heterogeneous Services). Sozinho, ele não dá acesso a dados remotos, que exigiria database link.
- **Consulta de referência da leitura 2:** `DBA_ROLE_PRIVS` (`WHERE granted_role IN ('HS_ADMIN_SELECT_ROLE', 'SELECT_CATALOG_ROLE')`). `USER_ROLE_PRIVS` não serve para isso: mostra só os papéis do usuário conectado e não tem coluna `GRANTEE`.
- **Contas READ/MUT do executor:** não constam desta leitura (pendência 7.1).

