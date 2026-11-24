# Controle de mutação `r_k4_dba`

Alvo `src/tools/oracle_dba.py`; testes `tests/test_oracle_kill.py`, `tests/test_item1_intencao.py`, `tests/test_fluxo_cli.py`, `tests/test_fluxo_web.py`; cópia `git archive HEAD`.

| Mutação | Troca | Contagem | Resultado | Status |
|---|---|---|---|---|
| m0 | sem mutação | - | 293 passed, 6 skipped, 13 warnings in 48.83s | OK |
| m25_vazio_aceito_onde_none_e_aceito | return len(valor) > LIMITE_TEXTO_IDENTIDADE or len(valor) < 1 -> retu… | 1 substituição | 5 failed, 288 passed, 6 skipped, 13 warnings in 48.81s \| caíram: tes… | DETECTADA |
| m31a_sem_validacao_pre_hitl | campos_invalidos = campos_invalidos_identidade(identidade) -> campos_… | 1 substituição | 8 failed, 285 passed, 6 skipped, 13 warnings in 48.42s \| caíram: tes… | DETECTADA |
| m31b_fase_dentro_de_fases_registro_kill | FASES_REGISTRO_KILL: Tuple[str, ...] = ("INTENCAO", "RESULTADO") -> F… | 1 substituição | 1 failed, 292 passed, 6 skipped, 13 warnings in 48.19s \| caíram: tes… | DETECTADA |
| m31c_chave_id_renomeada | "id_intervencao": id_evento, -> "id_evento": id_evento, | 1 substituição | 6 failed, 287 passed, 6 skipped, 13 warnings in 48.71s \| caíram: tes… | DETECTADA |
| m31d_chave_extra_no_evento | "campos_invalidos": list(campos_invalidos), -> "campos_invalidos": li… | 1 substituição | 5 failed, 288 passed, 6 skipped, 13 warnings in 48.65s \| caíram: tes… | DETECTADA |
| m31e_warning_com_valor_de_identidade | \| campos={campos_invalidos} \| id_intervencao={id_evento}" -> \| cam… | 1 substituição | 4 failed, 289 passed, 6 skipped, 13 warnings in 48.38s \| caíram: tes… | DETECTADA |
| m31f_erro_sem_o_nome_da_fase | f"AUDITORIA HITL: FALHA AO GRAVAR {FASE_RECUSA_PRE_HITL} \| id_interv… | 1 substituição | 1 failed, 292 passed, 6 skipped, 13 warnings in 48.47s \| caíram:    … | DETECTADA |
| m31g_erro_sem_errno | f"erro={type(exc).__name__} errno={getattr(exc, 'errno', None)} \| re… | 1 substituição | 1 failed, 292 passed, 6 skipped, 13 warnings in 48.57s \| caíram:    … | DETECTADA |

Resultado: todas DETECTADAS.
