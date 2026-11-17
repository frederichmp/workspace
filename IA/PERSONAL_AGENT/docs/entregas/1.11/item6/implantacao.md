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

**Ensaio sem banco** (`docs/entregas/1.11/verif_item9_ensaio_rollback.md`, parte B):
- Num clone descartável, aplicou-se a v2 em `db/ops_kill.sql` e depois restauraram-se a spec e o body a partir de `rollback_ops_kill_v1.sql`. O resultado foi **idêntico** à v1 do repositório (sha `4823ecca4cfd8b21`), com as colunas v2 mantidas.
- `tests/test_oracle_kill.py` no clone deu 33 passed e 6 skipped. Entre os que passaram está `test_lista_protegida_alinhada_ao_pacote`, que lê `c_protegidos` do `db/ops_kill.sql` restaurado.
- Os testes sandbox de kill **não foram executados**, porque exigem Oracle. O ensaio do rollback **no banco** continua pendente para uma sessão sandbox autorizada.

## 5. Testes que provam cada parte

**Sem conexão** (suíte padrão; provam o lado Python):
- `test_kill_chamada_nomeada_nove_formais`: o fake da conta KILL captura o SQL e exige as 9 associações `nome => :nome`, sem argumento posicional, e binds iguais à reconsulta.
- `test_kill_ponto_unico_de_chamada`: `inspect.getsource(oracle_dba)` contém exatamente uma ocorrência de `KILL_SESSION(`.
- `test_kill_pls00306_vira_erro_oracle`: o fake KILL levanta `oracledb.DatabaseError("ORA-06550 ... PLS-00306")`. O teste exige:
  - 1 execute na conta KILL;
  - `resultado_banco = ERRO_ORACLE` e `executado False`;
  - e-mail "NÃO executada", nunca "Aprovada";
  - nenhuma segunda tentativa.
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

## 6. Decisões do responsável pendentes neste item

1. Aprovar o texto de `ops_kill.sql` (v2), a migração e o rollback.
2. `p_ref_aprovacao` obrigatório (recomendado: liga o JSONL a `OPS_KILL_AUDIT` sem ambiguidade).
3. `program` e `machine` podem ser NULL (comparação null-safe); `username` e `logon_time`, não.
4. Confirmar no passo 0 que não há outros chamadores do pacote.
5. Os testes sandbox de transição dependem da versão do PKG implantada. Proposta: variável `OPS_KILL_PKG_VERSAO=1|2` definida pelo operador, com skip quando não bate.
6. Janela de implantação (seção 3.2): começa no `inicio_janela` da parte 2, antes da spec v2, e termina no primeiro kill sandbox v2 com ENCERRADA. Ou, em vez dela, a alternativa sem janela, que não é recomendada.
