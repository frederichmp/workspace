# Controle de mutação `mut_k4_oficial_dba`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD` + `src/tools/oracle_dba.py`, `src/tools/__init__.py`, `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/fakes_oracle.py`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 225 passed, 6 skipped, 13 warnings in 48.69s | OK |
| m25_vazio_aceito_onde_none_e_aceito | return len(valor) > LIMITE_TEXTO_IDENTIDADE or len(valor) < 1 -> retu… | 1 substituição | 5 failed, 220 passed, 6 skipped, 13 warnings in 48.05s \| caíram: tes… | DETECTADA |
| m31a_sem_validacao_pre_hitl | campos_invalidos = campos_invalidos_identidade(identidade) -> campos_… | 1 substituição | 6 failed, 219 passed, 6 skipped, 13 warnings in 48.00s \| caíram: tes… | DETECTADA |
| m31b_fase_dentro_de_fases_registro_kill | FASES_REGISTRO_KILL: Tuple[str, ...] = ("INTENCAO", "RESULTADO") -> F… | 1 substituição | 1 failed, 224 passed, 6 skipped, 13 warnings in 48.20s \| caíram: tes… | DETECTADA |
| m31c_chave_id_renomeada | "id_intervencao": id_evento, -> "id_evento": id_evento, | 1 substituição | 5 failed, 220 passed, 6 skipped, 13 warnings in 47.72s \| caíram: tes… | DETECTADA |
| m31d_chave_extra_no_evento | "campos_invalidos": list(campos_invalidos), -> "campos_invalidos": li… | 1 substituição | 4 failed, 221 passed, 6 skipped, 13 warnings in 47.65s \| caíram: tes… | DETECTADA |
| m31e_warning_com_valor_de_identidade | \| campos={campos_invalidos} \| id_intervencao={id_evento}" -> \| cam… | 1 substituição | 4 failed, 221 passed, 6 skipped, 13 warnings in 48.17s \| caíram: tes… | DETECTADA |
| m31f_erro_sem_o_nome_da_fase | f"AUDITORIA HITL: FALHA AO GRAVAR {FASE_RECUSA_PRE_HITL} \| id_interv… | 1 substituição | 1 failed, 224 passed, 6 skipped, 13 warnings in 47.72s \| caíram:    … | DETECTADA |
| m31g_erro_sem_errno | f"erro={type(exc).__name__} errno={getattr(exc, 'errno', None)} \| re… | 1 substituição | 1 failed, 224 passed, 6 skipped, 13 warnings in 47.80s \| caíram:    … | DETECTADA |

Resultado: todas DETECTADAS.
