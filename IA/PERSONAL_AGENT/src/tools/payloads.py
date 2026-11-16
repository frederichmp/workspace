"""Contratos de dados (Payloads JSON) com filtro na borda (Edge Filtering) para o Qwen 2.5."""
from typing import Literal, List, Optional
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


# ==========================================
# 2. Payload de Banco de Dados: Health Check
# ==========================================

class MetricasGlobaisDB(BaseModel):
    sessoes_ativas: int
    bloqueios_ativos: int
    top_wait_event: str


class SessaoOfensoraDB(BaseModel):
    sid_serial: str = Field(..., description="Formato 'SID,SERIAL#'")
    usuario: str
    sql_id: Optional[str] = None
    evento_espera: str
    tempo_espera_segundos: int
    status_bloqueador: str = Field(..., description="Ex: 'Bloqueando N sessão(ões)' ou 'Nenhum'")


class PayloadDBHealthCheck(BaseModel):
    status: Literal["sucesso", "erro"] = "sucesso"
    instancia: str
    metricas_globais: MetricasGlobaisDB
    top_3_ofensores: List[SessaoOfensoraDB] = Field(default_factory=list, max_length=3)


# ==========================================
# 3. Payload de Plano de Execução (DBMS_XPLAN)
# ==========================================

class OperacaoCriticaXPlan(BaseModel):
    id_operacao: int
    tipo: str = Field(..., description="Ex: TABLE ACCESS FULL, HASH JOIN")
    objeto: str = Field(default="", description="Nome da tabela ou índice")
    custo: int
    linhas_estimadas: int


class PayloadDBMSXPlan(BaseModel):
    status: Literal["sucesso", "erro"] = "sucesso"
    sql_id: str
    plan_hash_value: str
    custo_total: int
    alerta_arquitetura: str
    operacoes_criticas: List[OperacaoCriticaXPlan] = Field(default_factory=list)
    plano_truncado_para_ia: bool = True
