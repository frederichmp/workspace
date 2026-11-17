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

| Passo | Ação | Kill disponível? |
|---|---|---|
| 0 | **Parte 1.** Pré-condições: dependências, grants, `EXECUTE ANY PROCEDURE`, jobs (scheduler, programas, `DBA_JOBS`), `GV$SQL` (só indício), privilégios do OPS_OWNER, `UTL_RAW`. **Responsável confirma que não há outros chamadores.** | sim (v1) |
| 1 | **Parte 1.** Backup via `DBMS_METADATA` (spec, body, tabela, grants). Comparar com `rollback_ops_kill_v1.sql`; se divergir, **parar** | sim (v1) |
| 2 | **Parte 1.** `ALTER TABLE ... ADD` (aditivo); conferir que o body continua VALID | sim (v1) |
| — | **Parada humana:** avaliar as saídas da parte 1. Sem isso, não executar a parte 2 | sim (v1) |
| 3 | **Parte 2.** `CREATE OR REPLACE` da spec v2 | **não**: o Python v1 recebe PLS-00306 (seção 2e). Vira ERRO_ORACLE com `executado=False` |
| 4 | **Parte 2.** `CREATE OR REPLACE` do body v2. Conferências: `DBA_ERRORS` vazio, VALID, `DBA_ARGUMENTS` com 9 linhas, grant presente | **não** (Python ainda v1) |
| 5 | Implantar o commit Python do item 6 | sim (v2) |
| 6 | Testes sandbox v2 (seção 5) | sim (v2) |

A janela de indisponibilidade vai do passo 3 ao 5. Ela é intencional: não haver sobrecarga é o que impede um caminho de kill sem identidade. Deve ser marcada para quando nenhuma intervenção for necessária.

**Se o Python for implantado ANTES do banco** (Python v2 × PKG v1), cada APROVADO:
- grava INTENCAO, reconsulta, confere o hash e chama o PKG, que recebe PLS-00306;
- grava RESULTADO com `resultado_banco = ERRO_ORACLE` e `executado = False`;
- envia o e-mail "NÃO executada (status ERRO_ORACLE)", e a tela mostra "NÃO executada".

Nenhuma sessão é encerrada e nenhuma linha é gravada em `OPS_KILL_AUDIT`, porque o PKG não chega a rodar. O efeito é **seguro, mas o kill fica indisponível** até o banco ser migrado.

## 4. Rollback

1. Executar `rollback_ops_kill_v1.sql`. As colunas novas ficam, porque o body v1 usa INSERT com lista de colunas. Conferir VALID e o grant.
2. `git revert` do commit Python do item 6.

Entre 1 e 2, o kill fica indisponível (Python v2 × PKG v1 dá ERRO_ORACLE), de forma segura.

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
6. Janela de implantação (passos 3 a 5).
