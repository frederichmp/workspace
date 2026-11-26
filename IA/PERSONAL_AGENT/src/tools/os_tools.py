"""Ferramentas de coleta de métricas de SO e Hardware (Windows) com Edge Filtering.

R1 ampliada fase 2, K3 (fase2/decisao_c1.md §3 e §8.3): estas são as 2 ferramentas liberadas para o coordenador em
nuvem. Ao LLM vai só o tipo da exceção; o detalhe vai ao log local. verificar_espaco_disco aceita só raiz de unidade
local (D3): caminho UNC ou qualquer outro argumento é recusado sem chamar o psutil.
"""
import json
import logging
import re
from typing import Any, Dict, List
import psutil
from src.tools.payloads import (
    DadosHardwareBase,
    PayloadHardwareBase,
    DadosDiscoLocal,
    PayloadDiscoLocal,
)

LIMITE_ALERTA_DISCO_PERCENTUAL = 85.0

logger = logging.getLogger(__name__)

# D3 (decisao_c1.md §8.3): só raiz de unidade local ("C:" ou "C:\"). fullmatch, e não match com "$", para "C:\n"
# não passar.
_RE_RAIZ_DE_UNIDADE = re.compile(r"[A-Za-z]:\\?")
RESULTADO_UNIDADE_INVALIDA = json.dumps(
    {
        "status": "recusado",
        "coleta": "disco_local",
        "motivo": "UNIDADE_INVALIDA",
        "mensagem": "Só raiz de unidade local, por exemplo C:\\.",
    },
    ensure_ascii=False,
)


def unidade_local_valida(drive: Any) -> bool:
    """True só para str que é exatamente uma raiz de unidade local (D3). Nunca levanta."""
    try:
        return isinstance(drive, str) and _RE_RAIZ_DE_UNIDADE.fullmatch(drive) is not None
    except Exception:
        return False


def coletar_metricas_hardware() -> str:
    """Coleta uso consolidado de CPU e RAM e retorna JSON enxuto (~150 tokens)."""
    try:
        cpu_pct = round(psutil.cpu_percent(interval=0.5), 1)
        mem = psutil.virtual_memory()
        gb_factor = 1024 ** 3

        payload = PayloadHardwareBase(
            status="sucesso",
            coleta="hardware_base",
            dados=DadosHardwareBase(
                cpu_percentual=cpu_pct,
                ram_total_gb=round(mem.total / gb_factor, 1),
                ram_usada_gb=round((mem.total - mem.available) / gb_factor, 1),
                ram_livre_gb=round(mem.available / gb_factor, 1),
                ram_percentual=round(mem.percent, 1),
            ),
        )
        return json.dumps(payload.model_dump(), ensure_ascii=False)
    except Exception as exc:
        # R-c (K3): ao LLM só o tipo; o detalhe vai ao log local.
        try:
            logger.warning(
                "DETALHE LOCAL (fora do LLM) | ferramenta=%s | erro=%s: %s",
                "coletar_metricas_hardware", type(exc).__name__, exc,
            )
        except Exception:
            pass
        return json.dumps(
            {"status": "erro", "coleta": "hardware_base", "mensagem": f"Erro {type(exc).__name__}."},
            ensure_ascii=False,
        )


def verificar_espaco_disco(drive: str = "C:\\") -> str:
    """Coleta métricas da unidade de disco informada com flag booleana de alerta de capacidade.

    Só raiz de unidade local (D3); outro argumento (UNC, caminho, tipo errado) é recusado sem chamar o psutil e sem
    ecoar o argumento."""
    if not unidade_local_valida(drive):
        try:
            logger.warning(
                "UNIDADE RECUSADA (fora do LLM) | ferramenta=verificar_espaco_disco | unidade=%r",
                drive[:200] if isinstance(drive, str) else type(drive).__name__,
            )
        except Exception:
            pass
        return RESULTADO_UNIDADE_INVALIDA
    try:
        uso = psutil.disk_usage(drive)
        gb_factor = 1024 ** 3
        pct_usado = round(uso.percent, 1)

        payload = PayloadDiscoLocal(
            status="sucesso",
            coleta="disco_local",
            dados=DadosDiscoLocal(
                unidade=drive,
                total_gb=round(uso.total / gb_factor, 1),
                livre_gb=round(uso.free / gb_factor, 1),
                percentual_usado=pct_usado,
                alerta_capacidade=pct_usado >= LIMITE_ALERTA_DISCO_PERCENTUAL,
            ),
        )
        return json.dumps(payload.model_dump(), ensure_ascii=False)
    except Exception as exc:
        # R-c (K3): ao LLM só o tipo; o detalhe vai ao log local. A unidade (já validada) vai com %r: sem quebra de
        # linha crua no log. O "unidade" do retorno é residual aceito (9.8.3).
        try:
            logger.warning(
                "DETALHE LOCAL (fora do LLM) | ferramenta=%s | unidade=%r | erro=%s: %s",
                "verificar_espaco_disco", drive, type(exc).__name__, exc,
            )
        except Exception:
            pass
        return json.dumps(
            {"status": "erro", "coleta": "disco_local", "unidade": drive, "mensagem": f"Erro {type(exc).__name__}."},
            ensure_ascii=False,
        )


# Aliases para compatibilidade retroativa
coletar_hardware_base = coletar_metricas_hardware
coletar_disco_local = verificar_espaco_disco

# Schema no padrão OpenAI Tool Calling para exportação ao Orquestrador (Qwen 2.5 / Ollama)
os_tools_schema: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "coletar_metricas_hardware",
            "description": (
                "Coleta o uso atual de CPU (%) e Memória RAM (total, usada, livre em GB e %) "
                "da máquina local Windows."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verificar_espaco_disco",
            "description": (
                "Verifica o espaço total, livre e percentual usado de uma unidade de disco "
                "no Windows (padrão: 'C:\\\\'), incluindo alerta booleano de capacidade crítica."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "drive": {
                        "type": "string",
                        "description": "Unidade de disco a ser verificada, ex: 'C:\\\\'",
                    }
                },
            },
        },
    },
]
