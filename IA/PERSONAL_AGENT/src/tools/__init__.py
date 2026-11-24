"""Exportação das ferramentas (tools) do Personal Agent."""
from src.tools.oracle_dba import (
    coletar_sessoes_ativas,
    coletar_top_sql,
    coletar_plano_execucao,
    oracle_tools_schema,
)
# A8 (revisão do Gemini; decisao_c1.md ponto 7): matar_sessao_oracle não é exportada. O kill só passa por
# conduzir_kill_hitl / preparar_intervencao_kill + registrar_decisao_kill (src.tools.oracle_dba).
from src.tools.os_tools import (
    coletar_metricas_hardware,
    verificar_espaco_disco,
    coletar_hardware_base,
    coletar_disco_local,
    os_tools_schema,
)
from src.tools.gemini_router import (
    analisar_log_complexo,
    gemini_tools_schema,
)
from src.tools.notificador import enviar_alerta_email
from src.tools.rag_search import (
    buscar_script_interno,
    rag_tools_schema,
)

__all__ = [
    "coletar_sessoes_ativas",
    "coletar_top_sql",
    "coletar_plano_execucao",
    "oracle_tools_schema",
    "coletar_metricas_hardware",
    "verificar_espaco_disco",
    "coletar_hardware_base",
    "coletar_disco_local",
    "os_tools_schema",
    "analisar_log_complexo",
    "gemini_tools_schema",
    "enviar_alerta_email",
    "buscar_script_interno",
    "rag_tools_schema",
]
