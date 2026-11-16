"""Ferramentas de diagnóstico Oracle Database com Edge Filtering (Top 3 ofensores e parser de DBMS_XPLAN)."""
import json
import re
from typing import Any, List
from src.tools.payloads import (
    MetricasGlobaisDB,
    SessaoOfensoraDB,
    PayloadDBHealthCheck,
    OperacaoCriticaXPlan,
    PayloadDBMSXPlan,
)

# Queries com agregação na borda e FETCH FIRST 3 ROWS ONLY
SQL_METRICAS_GLOBAIS = """
SELECT
    COUNT(*) AS sessoes_ativas,
    SUM(CASE WHEN blocking_session IS NOT NULL THEN 1 ELSE 0 END) AS bloqueios_ativos,
    NVL(
        STATS_MODE(CASE WHEN wait_class <> 'Idle' THEN event END),
        'CPU / None'
    ) AS top_wait_event
FROM gv$session
WHERE status = 'ACTIVE' AND type = 'USER'
"""

SQL_TOP_3_OFENSORES = """
SELECT
    s.sid || ',' || s.serial# AS sid_serial,
    NVL(s.username, 'BACKGROUND') AS usuario,
    s.sql_id,
    s.event AS evento_espera,
    s.seconds_in_wait AS tempo_espera_segundos,
    CASE
        WHEN (SELECT COUNT(*) FROM gv$session b WHERE b.blocking_session = s.sid AND b.blocking_instance = s.inst_id) > 0
        THEN 'Bloqueando ' || (SELECT COUNT(*) FROM gv$session b WHERE b.blocking_session = s.sid AND b.blocking_instance = s.inst_id) || ' sessão'
        ELSE 'Nenhum'
    END AS status_bloqueador
FROM gv$session s
WHERE s.status = 'ACTIVE'
  AND s.type = 'USER'
  AND s.wait_class <> 'Idle'
ORDER BY s.seconds_in_wait DESC
FETCH FIRST 3 ROWS ONLY
"""


def montar_payload_health_check(
    instancia: str,
    sessoes_ativas: int,
    bloqueios_ativos: int,
    top_wait_event: str,
    ofensores_rows: List[dict[str, Any]],
) -> str:
    """Formata e valida o retorno do Health Check do Oracle no padrão enxuto (~300 tokens)."""
    ofensores = [
        SessaoOfensoraDB(
            sid_serial=str(row["sid_serial"]),
            usuario=str(row["usuario"]),
            sql_id=row.get("sql_id"),
            evento_espera=str(row["evento_espera"]),
            tempo_espera_segundos=int(row.get("tempo_espera_segundos") or 0),
            status_bloqueador=str(row.get("status_bloqueador", "Nenhum")),
        )
        for row in ofensores_rows[:3]
    ]

    payload = PayloadDBHealthCheck(
        status="sucesso",
        instancia=instancia,
        metricas_globais=MetricasGlobaisDB(
            sessoes_ativas=sessoes_ativas,
            bloqueios_ativos=bloqueios_ativos,
            top_wait_event=top_wait_event,
        ),
        top_3_ofensores=ofensores,
    )
    return json.dumps(payload.model_dump(), ensure_ascii=False)


def filtrar_dbms_xplan(
    sql_id: str,
    linhas_xplan: List[str],
    custo_minimo_alerta: int = 1000,
) -> str:
    """
    Faz o parse do output bruto do DBMS_XPLAN.DISPLAY_CURSOR,
    extraindo Plan Hash Value, Custo Total e filtrando apenas operações críticas (FULL ou alto custo).
    """
    plan_hash_value = "DESCONHECIDO"
    custo_total = 0
    operacoes_criticas: List[OperacaoCriticaXPlan] = []
    tem_full_scan = False

    regex_phv = re.compile(r"Plan hash value:\s*(\d+)", re.IGNORECASE)
    # Formato padrão da tabela do DBMS_XPLAN: | Id | Operation | Name | Rows | Bytes | Cost (%CPU)| Time |
    regex_linha = re.compile(
        r"^\|\*?\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*([0-9KMG]+)?\s*\|[^|]*\|\s*(\d+)?"
    )

    def _converter_estimativa(valor_str: str) -> int:
        if not valor_str:
            return 0
        valor_str = valor_str.strip().upper()
        multiplicadores = {"K": 1_000, "M": 1_000_000, "G": 1_000_000_000}
        if valor_str[-1] in multiplicadores:
            return int(float(valor_str[:-1]) * multiplicadores[valor_str[-1]])
        return int(valor_str) if valor_str.isdigit() else 0

    for linha in linhas_xplan:
        match_phv = regex_phv.search(linha)
        if match_phv:
            plan_hash_value = match_phv.group(1)
            continue

        match_op = regex_linha.match(linha.strip())
        if match_op:
            id_op = int(match_op.group(1))
            operacao = match_op.group(2).strip()
            objeto = match_op.group(3).strip()
            linhas_est = _converter_estimativa(match_op.group(4) or "0")
            custo_op = int(match_op.group(5)) if match_op.group(5) else 0

            if id_op == 0:
                custo_total = custo_op
                continue

            eh_full = "FULL" in operacao.upper()
            if eh_full:
                tem_full_scan = True

            if eh_full or custo_op >= custo_minimo_alerta:
                operacoes_criticas.append(
                    OperacaoCriticaXPlan(
                        id_operacao=id_op,
                        tipo=operacao,
                        objeto=objeto,
                        custo=custo_op,
                        linhas_estimadas=linhas_est,
                    )
                )

    if tem_full_scan and custo_total >= custo_minimo_alerta:
        alerta = "Encontrado alto custo e varredura total."
    elif tem_full_scan:
        alerta = "Encontrada varredura total (TABLE ACCESS FULL)."
    elif custo_total >= custo_minimo_alerta:
        alerta = "Encontrado alto custo de execução."
    else:
        alerta = "Nenhum alerta crítico de varredura ou custo elevado."

    payload = PayloadDBMSXPlan(
        status="sucesso",
        sql_id=sql_id,
        plan_hash_value=plan_hash_value,
        custo_total=custo_total,
        alerta_arquitetura=alerta,
        operacoes_criticas=operacoes_criticas,
        plano_truncado_para_ia=True,
    )
    return json.dumps(payload.model_dump(), ensure_ascii=False)
