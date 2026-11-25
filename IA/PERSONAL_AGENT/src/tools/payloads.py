"""Contratos de dados (Payloads JSON) com filtro na borda (Edge Filtering) para o Qwen 2.5.

R1 ampliada fase 2, K2 (plano 9.9.8, P1): os payloads de banco (health check e DBMS_XPLAN), sem chamador e com o
campo `instancia`, saíram junto com src/tools/oracle_tools.py. Dado do banco ao LLM só por src/tools/oracle_dba.py.
"""
from typing import Literal
from pydantic import BaseModel, Field


# ==========================================
# 1. Payloads de SO e Hardware
# ==========================================

class DadosHardwareBase(BaseModel):
    cpu_percentual: float = Field(..., description="Uso percentual da CPU")
    ram_total_gb: float = Field(..., description="Total de memória RAM em GB")
    ram_usada_gb: float = Field(..., description="Memória RAM em uso em GB")
    ram_livre_gb: float = Field(..., description="Memória RAM livre em GB")
    ram_percentual: float = Field(..., description="Percentual de uso de RAM")


class PayloadHardwareBase(BaseModel):
    status: Literal["sucesso", "erro"] = "sucesso"
    coleta: Literal["hardware_base"] = "hardware_base"
    dados: DadosHardwareBase


class DadosDiscoLocal(BaseModel):
    unidade: str = Field(..., description="Letra ou caminho da unidade, ex: C:\\")
    total_gb: float = Field(..., description="Capacidade total do disco em GB")
    livre_gb: float = Field(..., description="Espaço livre em GB")
    percentual_usado: float = Field(..., description="Percentual ocupado do disco")
    alerta_capacidade: bool = Field(
        ..., description="True se percentual_usado ultrapassar o limite crítico (ex: >= 85%)"
    )


class PayloadDiscoLocal(BaseModel):
    status: Literal["sucesso", "erro"] = "sucesso"
    coleta: Literal["disco_local"] = "disco_local"
    dados: DadosDiscoLocal
