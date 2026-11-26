# Conferência B: 1.11-V2-item6, reconferência estreita do passo 7

- Modelo: claude-opus-5-5 (agente de segurança, só leitura; não conectou ao Oracle e não rodou o pytest).
- Base: branch `item6/v2`, HEAD `ede7525`. Comparação: `diff_item6.diff` (conferido em `conferencia.md`) contra `diff_item6_v2.diff`.
- Escopo: só o que mudou entre os dois diffs. Os residuais de `conferencia.md` ficam como estão.

## Veredito: CONFORME

## 1. O que mudou entre os diffs (fato verificado, `diff` dos dois arquivos)

Só três arquivos têm hunks diferentes. `src/tools/oracle_dba.py` e `tests/fakes_oracle.py` estão idênticos nos dois diffs.

1. `app.py:513`: o literal "erro do Oracle a partir da chamada ao PKG" passa a ser "erro a partir da chamada ao PKG".
2. `src/main.py:260`: a mesma troca de literal.
3. `tests/test_item1_intencao.py:567-592`: novo `test_kill_ponto_unico_de_chamada` (def em `:576`), parametrizado em 3 cenários.

## 2. Ponto (1): o teste fecha o achado de `conferencia.md` §4

Requisito (`conferencia.md:36`): fluxo completo nos cenários ENCERRADA, ALVO_DIVERGENTE e erro no `execute`, cada um com exatamente 1 `execute` e 1 conexão KILL, sem fallback v1 nem retentativa.

| Exigência | Onde | Veredito |
|---|---|---|
| 3 cenários pelo fluxo completo aprovado (`conduzir_kill_hitl` com `_aprovar()`) | parametrize `:567-574` | OK |
| 1 conexão KILL | `fake.conexoes_kill == [USER_KILL_FAKE]`. O fake anota o `user` antes de qualquer desvio (`tests/fakes_oracle.py:121-122`, `:133-135`) | OK |
| 1 execute na conta KILL | filtro por conta sobre `sql_executado`. O fake anota antes de levantar `erro_kill` (`tests/fakes_oracle.py:69-72`), então o cenário de erro também conta a tentativa | OK |
| É o bloco v2 com 9 formais em ordem | regex dos formais no SQL e `list(binds)` contra `ORDEM_BINDS_KILL_V2` (`:58-61`, 9 nomes) | OK |
| Desfecho certo por cenário | `resultado_banco` = ENCERRADA / ALVO_DIVERGENTE / ERRO_ORACLE | OK |

Controle negativo medido (fato verificado nas saídas fornecidas):
- A m16 (`mut_item6_m16.json`) põe um `cursor.execute` v1 de 4 formais dentro de `if status_banco == "ALVO_DIVERGENTE":`. É a mesma mutação proposta em `conferencia.md:41`.
- Antes (`mut_item6_m16_antes.md`): m0 com 123 passed e 6 skipped. m16 PASSOU (123 passed), ou seja, o achado estava aberto.
- Depois (`mut_item6_m16_depois.md`): m0 com 126 passed (+3, as parametrizações novas) e 6 skipped (baseline mantido). A m16 foi DETECTADA: caiu só `test_kill_ponto_unico_de_chamada[alvo_divergente-...]`, em `tests/test_item1_intencao.py:588`, `assert 2 == 1` ("exatamente 1 execute na conta KILL").
- O resultado bate com o esperado em `conferencia.md:59` (L17: a correção foi medida pela própria mutação).

Limites (inferência, sem medição):
- A m16 só exercita o ramo ALVO_DIVERGENTE e a contagem de `execute`.
- Uma retentativa nos ramos ENCERRADA ou erro, ou uma segunda conexão KILL, cairia nas mesmas asserções diretas (`len == 1` e `== [USER_KILL_FAKE]`), que leem listas anotadas incondicionalmente pelo fake.
- Não há mutação medida para esses ramos. Não bloqueia: as asserções são idênticas nos 3 cenários e o fake não tem caminho que pule a anotação.

## 3. Ponto (2): texto de tela do D8 não vaza nada

- A troca só remove "do Oracle" de um literal fixo. As interpolações não mudam: `id_aprovador_limpo`/`aprovador`, `MENSAGEM_RESULTADO_DESCONHECIDO` (constante, `src/tools/oracle_dba.py:49`) e `resultado_banco`.
- O texto fica correto para os dois ramos que levam a `resultado_desconhecido`: o erro Oracle (`oracle_dba.py:906`) e a exceção não Oracle do D8 (`oracle_dba.py:927`, só `type(exc).__name__`). Isso fecha a nota cosmética de `conferencia.md:76`.
- Nenhum teste dependia do literal antigo: o grep de "erro do Oracle a partir" em `*.py` não acha nada fora de `oracle_dba.py:906`, que não mudou. Nenhuma expectativa de teste foi alterada.
- Nenhum teste fixa o literal novo. Por ser texto fixo sem dado, isso não é defeito.

## 4. Mudança proposta

Nenhuma.

## 5. Residuais e decisões do responsável

- Os residuais de `conferencia.md` permanecem como listados.
- Nada novo para PENDENTE APROVAÇÃO: não há mudança no pacote, em privilégios, em `registry/` nem em usuários protegidos.
