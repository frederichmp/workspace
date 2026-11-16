"""Ferramentas de coleta de métricas de SO e Hardware (Windows) com Edge Filtering."""
import json
from typing import Any, Dict, List
import psutil
from src.tools.payloads import (
    DadosHardwareBase,
    PayloadHardwareBase,
    DadosDiscoLocal,
    PayloadDiscoLocal,
)

LIMITE_ALERTA_DISCO_PERCENTUAL = 85.0


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
        return json.dumps(
            {"status": "erro", "coleta": "hardware_base", "mensagem": str(exc)},
            ensure_ascii=False,
        )


def verificar_espaco_disco(drive: str = "C:\\") -> str:
    """Coleta métricas da unidade de disco informada com flag booleana de alerta de capacidade."""
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
        return json.dumps(
            {"status": "erro", "coleta": "disco_local", "unidade": drive, "mensagem": str(exc)},
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
