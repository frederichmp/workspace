# Controle de mutação `mut_item6_a`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `src/main.py`, `app.py`, `tests/fakes_oracle.py`, `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 123 passed, 6 skipped, 13 warnings in 22.58s | OK |
| m1_assinatura_v1_4_binds |                     p_username_esperado   => :p_username_esperado,\n … | 'de' aparece 0 vez(es); precisa de 1 (alvo com 2063 CRLF e 0 LF só) | - | ERRO |
| m2_ordem_trocada_bloco_e_binds |                     p_username_esperado   => :p_username_esperado,\n … | 'de' aparece 0 vez(es); precisa de 1 (alvo com 2063 CRLF e 0 LF só) | - | ERRO |
| m3_ordem_trocada_so_binds |                     p_username_esperado   => :p_username_esperado,\n … | 'de' aparece 0 vez(es); precisa de 1 (alvo com 2063 CRLF e 0 LF só) | - | ERRO |
| m4_ref_aleatorio |             p_ref_aprovacao=ref_aprovacao, ->             p_ref_aprov… | 1 substituição | 4 failed, 119 passed, 6 skipped, 13 warnings in 20.58s \| caíram: tes… | DETECTADA |
| m5_logon_cru_sem_var_date |             p_logon_time_esperado=logon_var, ->             p_logon_t… | 1 substituição | 4 failed, 119 passed, 6 skipped, 13 warnings in 20.60s \| caíram: tes… | DETECTADA |
| m6_ref_com_default_none |     identidade_esperada: Dict[str, Any],\n    ref_aprovacao: str,\n -… | 'de' aparece 0 vez(es); precisa de 1 (alvo com 2063 CRLF e 0 LF só) | - | ERRO |
| m7_sem_validacao_local |     invalidos = campos_invalidos_identidade_e_ref(identidade_esperada… | 'de' aparece 0 vez(es); precisa de 1 (alvo com 2063 CRLF e 0 LF só) | - | ERRO |
| m8_strip_no_username |             p_username_esperado=identidade_esperada["username"], ->  … | 1 substituição | 2 failed, 121 passed, 6 skipped, 13 warnings in 20.80s \| caíram: tes… | DETECTADA |

Resultado: controle INVÁLIDO ou ERRO.
