# PERSONAL AGENT DBA - Código Completo para Revisão Arquitetural

## Arquivo: `requirements.txt`
```text
python-dotenv>=1.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
psutil>=5.9.0
oracledb>=2.0.0
openai>=1.0.0
google-generativeai>=0.8.0
streamlit>=1.40.0
pandas>=2.0.0
chromadb>=1.0.0
langchain>=0.3.0
langchain-community>=0.3.0
langchain-text-splitters>=0.3.0
sentence-transformers>=3.0.0
rich>=13.0.0

```

## Arquivo: `.env.example`
```text
# ==============================================================================
# COFRE DE CREDENCIAIS - ORACLE DATABASE (Modo Thin)
# ==============================================================================
ORACLE_USER=system_ou_usuario_monitoramento
ORACLE_PASSWORD=sua_senha_segura_aqui
ORACLE_DSN=192.168.1.100:1521/PRDMV

# ==============================================================================
# CONFIGURAÇÕES DE LLM / SEGUNDO CÉREBRO (GEMINI API & OLLAMA LOCAL)
# ==============================================================================
GEMINI_API_KEY=your_gemini_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=qwen2.5:7b

# ==============================================================================
# CONFIGURAÇÕES DE ALERTA (SMTP GMAIL - HITL)
# ==============================================================================
EMAIL_REMETENTE=seu_email@gmail.com
EMAIL_SENHA_APP=sua_senha_de_aplicativo_de_16_digitos
EMAIL_DESTINATARIO=equipe_dba@suaempresa.com.br

# ==============================================================================
# CONFIGURAÇÕES GERAIS DO AGENTE
# ==============================================================================
AGENT_NAME=PersonalAgentDBA
LOG_LEVEL=INFO

```

## Arquivo: `src/prompts/system_prompt.txt`
```text
Você é o Agente Coordenador, o cérebro central de um sistema autônomo local de administração de TI e Banco de Dados.
Seus princípios absolutos são:
1. Precisão acima de velocidade.
2. Evidência acima de opinião.

DIRETRIZES DE COMPORTAMENTO E DELEGAÇÃO:
- Nunca invente métricas, queries, logs ou estados do sistema. Chame as ferramentas.
- Para problemas simples, responda no formato: Diagnóstico, Evidências, Possíveis Causas e Próximo Passo.
- REGRA DE OURO: Se você extrair um plano de execução (DBMS_XPLAN) muito extenso ou um log de deadlock que você não consegue analisar com profundidade, acione IMEDIATAMENTE a ferramenta 'analisar_log_complexo' para terceirizar a análise. Não tente adivinhar.

```

## Arquivo: `src/tools/payloads.py`
```py
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

```

## Arquivo: `src/tools/os_tools.py`
```py
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

```

## Arquivo: `src/tools/oracle_dba.py`
```py
"""
Módulo de conexão e diagnóstico Oracle Database em Modo Thin.
Aplica isolamento de credenciais via variáveis de ambiente (.env),
pré-validação rápida de rede/VPN (Socket TCP) e Edge Filtering.
"""
import json
import os
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
import oracledb
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env na raiz do projeto
load_dotenv()


def _extrair_host_porta(dsn: str) -> Tuple[str, int]:
    """
    Extrai o IP/Hostname e a porta a partir de uma string Easy Connect (ex: 10.10.20.16:1521/MODELO).
    Se a porta não for informada, assume a porta padrão 1521 do Oracle Listener.
    """
    parte_endereco = dsn.split("/")[0].strip()
    if ":" in parte_endereco:
        host, porta_str = parte_endereco.split(":", 1)
        try:
            return host.strip(), int(porta_str.strip())
        except ValueError:
            return host.strip(), 1521
    return parte_endereco, 1521


def verificar_acessibilidade_host(dsn: str, timeout: float = 3.0) -> Dict[str, Any]:
    """
    Valida rapidamente via Socket TCP se o host e a porta do banco estão acessíveis
    (ex: verificando se a VPN está conectada) antes de tentar abrir sessão no Oracle.
    Evita que o Agente fique travado esperando timeouts longos de TNS.
    """
    host, porta = _extrair_host_porta(dsn)
    inicio = time.perf_counter()
    try:
        with socket.create_connection((host, porta), timeout=timeout):
            latencia_ms = round((time.perf_counter() - inicio) * 1000, 1)
            return {
                "acessivel": True,
                "host": host,
                "porta": porta,
                "latencia_ms": latencia_ms,
            }
    except (socket.timeout, ConnectionRefusedError, OSError) as net_err:
        return {
            "acessivel": False,
            "host": host,
            "porta": porta,
            "erro_rede": str(net_err),
        }


def coletar_sessoes_ativas() -> str:
    """
    1. Valida se o host do banco está acessível na rede/VPN (pré-check TCP rápido).
    2. Conecta ao banco de dados Oracle em modo Thin utilizando as credenciais do .env.
    3. Contabiliza o total de sessões de usuário ativas na GV$SESSION e retorna JSON estruturado.
    """
    user = os.getenv("ORACLE_USER")
    password = os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user, password, dsn]):
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn or "NAO_CONFIGURADO",
                "mensagem": (
                    "Credenciais incompletas no cofre (.env). "
                    "Verifique ORACLE_USER, ORACLE_PASSWORD e ORACLE_DSN."
                ),
            },
            ensure_ascii=False,
        )

    # 1. Pré-validação de Rede / VPN (Fail-Fast em 3 segundos)
    check_rede = verificar_acessibilidade_host(dsn, timeout=3.0)
    if not check_rede["acessivel"]:
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn,
                "host_acessivel": False,
                "tipo_erro": "HostInacessivelVPN",
                "mensagem": (
                    f"Host {check_rede['host']}:{check_rede['porta']} inacessível. "
                    "Verifique se a VPN está conectada ou se há bloqueio de firewall."
                ),
                "detalhe_rede": check_rede["erro_rede"],
            },
            ensure_ascii=False,
        )

    connection: Optional[oracledb.Connection] = None
    cursor: Optional[oracledb.Cursor] = None

    try:
        # 2. Conexão em modo Thin nativo do python-oracledb
        connection = oracledb.connect(
            user=user,
            password=password,
            dsn=dsn,
        )
        cursor = connection.cursor()

        query = """
            SELECT COUNT(*)
            FROM GV$SESSION
            WHERE status = 'ACTIVE'
              AND type = 'USER'
        """
        cursor.execute(query)
        row = cursor.fetchone()
        total_ativas = int(row[0]) if row else 0

        # Busca até 3 sessões de usuário (excluindo a própria sessão de coleta) com SID e SERIAL#
        query_top_sessoes = """
            SELECT sid,
                   serial# AS serial,
                   NVL(username, 'BACKGROUND') AS usuario,
                   status,
                   sql_id,
                   CASE
                       WHEN state = 'WAITING' THEN event
                       ELSE 'ON CPU (Consumindo Processamento)'
                   END AS evento_espera
            FROM GV$SESSION
            WHERE type = 'USER'
              AND sid <> SYS_CONTEXT('USERENV', 'SID')
            ORDER BY CASE WHEN status = 'ACTIVE' THEN 0 ELSE 1 END,
                     seconds_in_wait DESC
            FETCH FIRST 3 ROWS ONLY
        """
        cursor.execute(query_top_sessoes)
        colunas_sess = [col[0].lower() for col in cursor.description]
        sessoes_detalhe = [dict(zip(colunas_sess, r)) for r in cursor.fetchall()]

        return json.dumps(
            {
                "status": "sucesso",
                "instancia": dsn,
                "host_acessivel": True,
                "latencia_rede_ms": check_rede["latencia_ms"],
                "sessoes_ativas": total_ativas,
                "sessoes_identificadas": sessoes_detalhe,
            },
            ensure_ascii=False,
        )

    except oracledb.Error as db_err:
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn,
                "host_acessivel": True,
                "tipo_erro": "OracleError",
                "mensagem": str(db_err),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn,
                "host_acessivel": True,
                "tipo_erro": type(exc).__name__,
                "mensagem": str(exc),
            },
            ensure_ascii=False,
        )
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def coletar_top_sql(limite: int = 3) -> str:
    """
    Obtém as instruções SQL mais pesadas baseadas em tempo total de execução (elapsed_time),
    ignorando schemas de sistema e truncando o texto da query em 100 caracteres (Edge Filtering).
    """
    user = os.getenv("ORACLE_USER")
    password = os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user, password, dsn]):
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn or "NAO_CONFIGURADO",
                "mensagem": (
                    "Credenciais incompletas no cofre (.env). "
                    "Verifique ORACLE_USER, ORACLE_PASSWORD e ORACLE_DSN."
                ),
            },
            ensure_ascii=False,
        )

    # Pré-validação de Rede / VPN (Fail-Fast em 3 segundos)
    check_rede = verificar_acessibilidade_host(dsn, timeout=3.0)
    if not check_rede["acessivel"]:
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn,
                "host_acessivel": False,
                "tipo_erro": "HostInacessivelVPN",
                "mensagem": (
                    f"Host {check_rede['host']}:{check_rede['porta']} inacessível. "
                    "Verifique se a VPN está conectada ou se há bloqueio de firewall."
                ),
                "detalhe_rede": check_rede["erro_rede"],
            },
            ensure_ascii=False,
        )

    connection: Optional[oracledb.Connection] = None
    cursor: Optional[oracledb.Cursor] = None

    try:
        connection = oracledb.connect(
            user=user,
            password=password,
            dsn=dsn,
        )
        cursor = connection.cursor()

        query = """
        SELECT s.sql_id,
               s.executions,
               ROUND(s.elapsed_time / 1000000, 2) AS elapsed_seg_total,
               ROUND((s.elapsed_time / 1000000) / GREATEST(s.executions, 1), 2) AS elapsed_por_exec,
               SUBSTR(s.sql_text, 1, 100) AS sql_text_curto
        FROM gv$sqlarea s
        WHERE s.parsing_schema_name NOT IN ('SYS', 'SYSTEM', 'SYSMAN', 'DBSNMP')
          AND s.executions > 0
          AND UPPER(s.sql_text) NOT LIKE '%DBMS_XPLAN%'
          AND UPPER(s.sql_text) NOT LIKE '%GV$SQLAREA%'
          AND UPPER(s.sql_text) NOT LIKE '%GV$SESSION%'
          AND EXISTS (SELECT 1 FROM gv$sql_plan p WHERE p.sql_id = s.sql_id AND p.id > 0)
        ORDER BY s.elapsed_time DESC
        FETCH FIRST :limite ROWS ONLY
        """

        cursor.execute(query, limite=int(limite))
        colunas = [col[0].lower() for col in cursor.description]

        top_sqls = []
        for linha in cursor.fetchall():
            top_sqls.append(dict(zip(colunas, linha)))

        return json.dumps(
            {
                "status": "sucesso",
                "instancia": dsn,
                "host_acessivel": True,
                "top_sql": top_sqls,
            },
            ensure_ascii=False,
        )

    except Exception as exc:
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn,
                "mensagem": str(exc),
            },
            ensure_ascii=False,
        )
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def coletar_plano_execucao(sql_id: str) -> str:
    """Extrai o plano de execução real de um SQL_ID via DBMS_XPLAN."""
    user = os.getenv("ORACLE_USER")
    password = os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user, password, dsn]):
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn or "NAO_CONFIGURADO",
                "mensagem": (
                    "Credenciais incompletas no cofre (.env). "
                    "Verifique ORACLE_USER, ORACLE_PASSWORD e ORACLE_DSN."
                ),
            },
            ensure_ascii=False,
        )

    # Pré-validação de Rede / VPN (Fail-Fast em 3 segundos)
    check_rede = verificar_acessibilidade_host(dsn, timeout=3.0)
    if not check_rede["acessivel"]:
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn,
                "host_acessivel": False,
                "tipo_erro": "HostInacessivelVPN",
                "mensagem": (
                    f"Host {check_rede['host']}:{check_rede['porta']} inacessível. "
                    "Verifique se a VPN está conectada ou se há bloqueio de firewall."
                ),
                "detalhe_rede": check_rede["erro_rede"],
            },
            ensure_ascii=False,
        )

    connection: Optional[oracledb.Connection] = None
    cursor: Optional[oracledb.Cursor] = None

    try:
        connection = oracledb.connect(
            user=user,
            password=password,
            dsn=dsn,
        )
        cursor = connection.cursor()

        # Utiliza formato 'TYPICAL' para evitar o excesso de metadados do 'ADVANCED'
        query = "SELECT PLAN_TABLE_OUTPUT FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(:sql_id, NULL, 'TYPICAL'))"

        cursor.execute(query, sql_id=sql_id)

        linhas_plano = []
        for row in cursor.fetchall():
            # Remove espaços vazios nas bordas para economizar tokens
            linha = row[0].strip() if row[0] else ""
            if linha:
                linhas_plano.append(linha)

        # Filtro na Borda: Proteção contra planos gigantes (ex: relatórios com dezenas de joins)
        plano_truncado = False
        if len(linhas_plano) > 40:
            linhas_plano = linhas_plano[:40]
            linhas_plano.append("... [PLANO TRUNCADO PARA PROTEGER CONTEXTO DA IA] ...")
            plano_truncado = True

        return json.dumps(
            {
                "status": "sucesso",
                "sql_id": sql_id,
                "plano_execucao": "\n".join(linhas_plano),
                "truncado": plano_truncado,
            },
            ensure_ascii=False,
        )

    except Exception as exc:
        return json.dumps(
            {
                "status": "erro",
                "sql_id": sql_id,
                "mensagem": str(exc),
            },
            ensure_ascii=False,
        )
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def matar_sessao_oracle(sid: int, serial: int) -> str:
    """
    Executa o comando destrutivo ALTER SYSTEM KILL SESSION 'sid,serial' IMMEDIATE
    no banco de dados Oracle. Deve ser protegido por barreira HITL no orquestrador.
    """
    user = os.getenv("ORACLE_USER")
    password = os.getenv("ORACLE_PASSWORD")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user, password, dsn]):
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn or "NAO_CONFIGURADO",
                "mensagem": (
                    "Credenciais incompletas no cofre (.env). "
                    "Verifique ORACLE_USER, ORACLE_PASSWORD e ORACLE_DSN."
                ),
            },
            ensure_ascii=False,
        )

    # Sanitização estrita de inteiros para evitar SQL Injection em comando DDL/ALTER SYSTEM
    try:
        sid_int = int(sid)
        serial_int = int(serial)
    except (ValueError, TypeError):
        return json.dumps(
            {
                "status": "erro",
                "mensagem": f"Parâmetros inválidos para KILL SESSION: sid={sid}, serial={serial}. Devem ser inteiros.",
            },
            ensure_ascii=False,
        )

    # Pré-validação de Rede / VPN (Fail-Fast em 3 segundos)
    check_rede = verificar_acessibilidade_host(dsn, timeout=3.0)
    if not check_rede["acessivel"]:
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn,
                "host_acessivel": False,
                "tipo_erro": "HostInacessivelVPN",
                "mensagem": (
                    f"Host {check_rede['host']}:{check_rede['porta']} inacessível. "
                    "Verifique se a VPN está conectada ou se há bloqueio de firewall."
                ),
                "detalhe_rede": check_rede["erro_rede"],
            },
            ensure_ascii=False,
        )

    connection: Optional[oracledb.Connection] = None
    cursor: Optional[oracledb.Cursor] = None

    try:
        connection = oracledb.connect(
            user=user,
            password=password,
            dsn=dsn,
        )
        cursor = connection.cursor()

        comando_kill = f"ALTER SYSTEM KILL SESSION '{sid_int},{serial_int}' IMMEDIATE"
        cursor.execute(comando_kill)

        return json.dumps(
            {
                "status": "sucesso",
                "instancia": dsn,
                "acao": "KILL_SESSION",
                "sid_serial": f"{sid_int},{serial_int}",
                "mensagem": f"Sessão '{sid_int},{serial_int}' encerrada com sucesso (IMMEDIATE).",
            },
            ensure_ascii=False,
        )

    except oracledb.Error as db_err:
        err_msg = str(db_err)
        # No Oracle, ORA-00031 (session marked for kill) em sessão ON CPU significa que o KILL IMMEDIATE foi aceito e está finalizando o rollback
        if "ORA-00031" in err_msg:
            return json.dumps(
                {
                    "status": "sucesso",
                    "instancia": dsn,
                    "acao": "KILL_SESSION",
                    "sid_serial": f"{sid_int},{serial_int}",
                    "mensagem": f"Sessão '{sid_int},{serial_int}' encerrada/marcada para kill imediato (ORA-00031).",
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn,
                "sid_serial": f"{sid_int},{serial_int}",
                "tipo_erro": "OracleError",
                "mensagem": err_msg,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {
                "status": "erro",
                "instancia": dsn,
                "sid_serial": f"{sid_int},{serial_int}",
                "tipo_erro": type(exc).__name__,
                "mensagem": str(exc),
            },
            ensure_ascii=False,
        )
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


# Schema no padrão OpenAI Tool Calling para exportação ao Orquestrador (Qwen 2.5 / Ollama)
oracle_tools_schema: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "coletar_sessoes_ativas",
            "description": (
                "Valida a conectividade de rede/VPN com o servidor Oracle e, se acessível, "
                "conecta em modo Thin retornando o número exato de sessões de usuários ativas "
                "(status = 'ACTIVE' e type = 'USER') na GV$SESSION."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "coletar_top_sql",
            "description": (
                "Obtém as instruções SQL (Top SQL) mais pesadas em execução no banco de dados Oracle, "
                "baseadas em tempo de CPU/Elapsed Time."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limite": {
                        "type": "integer",
                        "description": "Quantidade de queries para retornar. Padrão: 3",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "coletar_plano_execucao",
            "description": (
                "Obtém o plano de execução (DBMS_XPLAN) de um SQL_ID no banco Oracle. "
                "Use para investigar gargalos de custo, acesso (Full Table Scan) e cardinalidade."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_id": {
                        "type": "string",
                        "description": "O identificador alfanumérico exato do SQL (ex: '8m4x7b9q2zv1c').",
                    }
                },
                "required": ["sql_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "matar_sessao_oracle",
            "description": (
                "Encerra uma sessão problemática no banco. "
                "Usar apenas quando o usuário pedir explicitamente para matar ou derrubar a sessão."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sid": {
                        "type": "integer",
                        "description": "O identificador numérico SID da sessão no Oracle.",
                    },
                    "serial": {
                        "type": "integer",
                        "description": "O número SERIAL# da sessão no Oracle.",
                    },
                },
                "required": ["sid", "serial"],
            },
        },
    },
]


if __name__ == "__main__":
    print("Iniciando teste isolado...")

    # Substituído pelo SQL_ID real retornado no banco de teste (10.10.20.16:1521/MODELO)
    sql_id_teste = "2z0udr4rc402m"

    print(f"\nExtraindo Plano de Execução para {sql_id_teste}...")
    resultado_plano = coletar_plano_execucao(sql_id=sql_id_teste)
    print(resultado_plano)

```

## Arquivo: `src/tools/gemini_router.py`
```py
"""
Módulo de Roteamento LLM (LLM Routing) para a API do Google Gemini (Fase 3).
Atua como Segundo Cérebro (Analista Sênior em Nuvem) para decifrar logs extensos,
traces, deadlocks e planos de execução complexos (DBMS_XPLAN).
"""
import json
import os
import warnings
from typing import Any, Dict, List

# Suprime o aviso de depreciação do pacote google.generativeai no terminal
warnings.filterwarnings("ignore")

import google.generativeai as genai
from google.generativeai.types import RequestOptions
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração da API com a chave do cofre (.env) usando transport="rest" (compatível com VPN corporativa)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY and GEMINI_API_KEY != "sua_chave_aqui":
    genai.configure(api_key=GEMINI_API_KEY, transport="rest")

# Instancia o modelo Gemini
MODELO_GEMINI_PADRAO = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
model = genai.GenerativeModel(MODELO_GEMINI_PADRAO)


def analisar_log_complexo(dados_brutos: str, contexto_solicitacao: str) -> str:
    """
    Envia dados brutos extensos (logs, traces, deadlocks ou DBMS_XPLAN) e o contexto da
    solicitação para o Google Gemini em nuvem, exigindo retorno estrito no formato executivo:
    Diagnóstico, Evidências, Possíveis Causas e Próximo Passo.
    """
    load_dotenv(override=True)
    api_key = os.getenv("GEMINI_API_KEY", "")

    if not api_key or api_key in ("sua_chave_aqui", "your_gemini_api_key_here"):
        return json.dumps(
            {
                "status": "erro",
                "origem": "gemini_router",
                "mensagem": (
                    "Chave GEMINI_API_KEY não configurada ou inválida no arquivo .env. "
                    "Insira uma chave válida do Google AI Studio para acionar o Analista em Nuvem."
                ),
            },
            ensure_ascii=False,
        )

    try:
        # Usa transport="rest" para evitar travamento de gRPC em redes com VPN ativa
        genai.configure(api_key=api_key, transport="rest")

        prompt_estruturado = f"""Você é um Analista Sênior de Infraestrutura e Banco de Dados Oracle em Nuvem (Segundo Cérebro).
O Agente Coordenador Local escalou esta análise para você devido à alta complexidade ou volume dos dados.

CONTEXTO DA SOLICITAÇÃO:
{contexto_solicitacao}

DADOS BRUTOS / EVIDÊNCIAS COLETADAS:
{dados_brutos}

INSTRUÇÃO OBRIGATÓRIA DE FORMATO:
Analise tecnicamente os dados acima com rigor sênior e retorne sua resposta OBRIGATORIAMENTE utilizando este formato executivo exato:

* Diagnóstico: (resumo técnico objetivo do problema raiz identificado)
* Evidências: (trechos exatos do log, métricas, wait events, custos ou operações que comprovam o diagnóstico)
* Possíveis Causas: (ordenadas da mais provável para a menos provável)
* Próximo Passo: (ação técnica recomendada, comando de ajuste, criação de índice ou investigação complementar)
"""

        modelos_tentativa = [
            "gemini-3.1-flash-lite-preview",
            "gemini-2.5-flash",
            "gemini-3-flash-preview",
            "gemini-2.5-flash-lite",
            "gemini-flash-latest",
        ]
        ultimo_erro = None

        for nome_modelo in dict.fromkeys(modelos_tentativa):
            try:
                instancia_modelo = genai.GenerativeModel(nome_modelo)
                resposta = instancia_modelo.generate_content(
                    prompt_estruturado,
                    request_options=RequestOptions(retry=None, timeout=30.0),
                )
                return json.dumps(
                    {
                        "status": "sucesso",
                        "modelo_utilizado": nome_modelo,
                        "analise_especialista": resposta.text,
                    },
                    ensure_ascii=False,
                )
            except Exception as mod_err:
                ultimo_erro = mod_err
                err_str = str(mod_err).lower()
                if any(
                    code in err_str
                    for code in ("404", "not found", "429", "quota", "503", "unavailable", "demand")
                ):
                    continue
                raise mod_err

        raise RuntimeError(f"Falha ao invocar modelos Gemini: {ultimo_erro}")

    except Exception as exc:
        return json.dumps(
            {
                "status": "erro",
                "origem": "gemini_router",
                "tipo_erro": type(exc).__name__,
                "mensagem": str(exc),
            },
            ensure_ascii=False,
        )


# Schema no padrão OpenAI Tool Calling para exportação ao Orquestrador
gemini_tools_schema: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "analisar_log_complexo",
            "description": (
                "Analista Sênior em Nuvem para analisar logs, traces, deadlocks e planos de "
                "execução muito extensos que o modelo local não consiga decifrar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dados_brutos": {
                        "type": "string",
                        "description": (
                            "O conteúdo bruto do log de erro, trace, deadlock graph ou "
                            "plano de execução (DBMS_XPLAN) a ser analisado."
                        ),
                    },
                    "contexto_solicitacao": {
                        "type": "string",
                        "description": (
                            "Explicação do contexto do problema, instância afetada e "
                            "o que o Agente Local precisa descobrir."
                        ),
                    },
                },
                "required": ["dados_brutos", "contexto_solicitacao"],
            },
        },
    }
]


if __name__ == "__main__":
    print("Iniciando teste isolado do Roteador Gemini (Fase 3)...")

    log_teste = """
    ORA-00060: deadlock detected while waiting for resource
    Deadlock graph:
                         ---------Blocker(s)--------  ---------Waiter(s)---------
    Resource Name        process session holds waits  process session holds waits
    TX-000a0015-0001402b      42    1045     X             51     832           X
    TX-00090004-0000981a      51     832     X             42    1045           X
    Rows waited on:
      Session 1045: obj - rowid = 0001A4F2 - AAAaTyAAGAAAACrAAA (tabela PEDIDOS_VENDA)
      Session 832:  obj - rowid = 0001A4F5 - AAAaT1AAGAAAADMAAB (tabela ESTOQUE_ITENS)
    """
    contexto_teste = (
        "Análise de incidente de travamento recorrente no banco de produção PRDMV "
        "durante o fechamento de pedidos."
    )

    print("\nEnviando payload de teste para analisar_log_complexo()...")
    resultado = analisar_log_complexo(
        dados_brutos=log_teste,
        contexto_solicitacao=contexto_teste,
    )
    print("\n[Resultado do Teste]:")
    print(resultado)

```

## Arquivo: `src/tools/notificador.py`
```py
"""
Módulo de Notificação de Alertas Críticos via SMTP (Gmail App Password).
Integrado à barreira de segurança HITL (Human-in-the-Loop) para governança de intervenções DBA.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Tuple
from dotenv import load_dotenv

load_dotenv()


def enviar_alerta_email(assunto: str, corpo: str) -> Tuple[bool, str]:
    """Envia um e-mail de alerta utilizando SMTP do Gmail (TLS na porta 587)."""
    load_dotenv(override=True)
    remetente = os.getenv("EMAIL_REMETENTE", "").strip()
    # Remove espaços caso a senha de app de 16 dígitos tenha sido colada com espaços
    senha = os.getenv("EMAIL_SENHA_APP", "").replace(" ", "").strip()
    destinatario = os.getenv("EMAIL_DESTINATARIO", "").strip()

    if not all([remetente, senha, destinatario]) or "seu_email" in remetente:
        return False, "Credenciais de e-mail ausentes ou não configuradas no .env."

    try:
        msg = MIMEMultipart()
        msg["From"] = remetente
        msg["To"] = destinatario
        msg["Subject"] = assunto

        msg.attach(MIMEText(corpo, "plain", "utf-8"))

        # Conexão segura com o Gmail (TLS)
        servidor = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        servidor.starttls()
        servidor.login(remetente, senha)
        servidor.send_message(msg)
        servidor.quit()

        return True, "E-mail enviado com sucesso."
    except Exception as e:
        return False, f"Falha ao enviar e-mail: {str(e)}"


if __name__ == "__main__":
    print("Testando envio de alerta por e-mail...")
    ok, mensagem = enviar_alerta_email(
        assunto="[AGENTE DBA] Teste de Configuração SMTP",
        corpo="Este é um teste automático do módulo notificador.py do Personal Agent.",
    )
    print(f"Sucesso: {ok} | Mensagem: {mensagem}")

```

## Arquivo: `src/tools/rag_indexer.py`
```py
"""
Módulo de Indexação RAG Local (Retrieval-Augmented Generation) para Scripts Oracle DBA.
Lê todos os arquivos .sql e .txt do repositório de scripts homologados (./MeusScripts e SCRIPT STARTUP GIT/oracle),
quebra em chunks de 1000 caracteres (overlap 200), gera embeddings locais (all-MiniLM-L6-v2)
e persiste no banco vetorial ChromaDB (./chroma_db).
"""
import shutil
import warnings
from pathlib import Path
from typing import List

warnings.filterwarnings("ignore")

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Caminhos base do projeto e do repositório de scripts Oracle do Workspace
SRC_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SRC_DIR.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent.parent

MEUS_SCRIPTS_DIR = PROJECT_ROOT / "MeusScripts"
ORACLE_WORKSPACE_SCRIPTS_DIR = WORKSPACE_ROOT / "SCRIPT STARTUP GIT" / "oracle"
CHROMA_DB_DIR = PROJECT_ROOT / "chroma_db"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def sincronizar_scripts_oracle() -> Path:
    """
    Garante que a pasta ./MeusScripts exista e sincroniza os scripts .sql e .txt
    do diretório 'SCRIPT STARTUP GIT/oracle' do Workspace para dentro de ./MeusScripts.
    """
    MEUS_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    if ORACLE_WORKSPACE_SCRIPTS_DIR.exists():
        contador = 0
        for ext in ("*.sql", "*.txt", "*.md"):
            for arquivo in ORACLE_WORKSPACE_SCRIPTS_DIR.rglob(ext):
                rel_path = arquivo.relative_to(ORACLE_WORKSPACE_SCRIPTS_DIR)
                destino = MEUS_SCRIPTS_DIR / rel_path
                destino.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(arquivo, destino)
                contador += 1
        print(
            f"[RAG Indexer]: {contador} arquivos sincronizados de "
            f"'{ORACLE_WORKSPACE_SCRIPTS_DIR}' para '{MEUS_SCRIPTS_DIR}'."
        )
    return MEUS_SCRIPTS_DIR


def indexar_base_conhecimento(
    pasta_scripts: str | Path = MEUS_SCRIPTS_DIR,
    pasta_chroma: str | Path = CHROMA_DB_DIR,
) -> int:
    """
    Lê todos os arquivos .sql e .txt de ./MeusScripts usando DirectoryLoader + TextLoader,
    divide em chunks de 1000 caracteres (overlap 200) e persiste os vetores no ChromaDB local.
    Retorna o total de chunks indexados.
    """
    pasta_alvo = Path(pasta_scripts)
    if not pasta_alvo.exists() or not any(pasta_alvo.rglob("*.*")):
        sincronizar_scripts_oracle()

    documentos = []
    # Carrega arquivos .sql e .txt com detecção automática de encoding (UTF-8 / Latin-1)
    for padrao in ("**/*.sql", "**/*.txt"):
        loader = DirectoryLoader(
            str(pasta_alvo),
            glob=padrao,
            loader_cls=TextLoader,
            loader_kwargs={"autodetect_encoding": True},
            show_progress=False,
            use_multithreading=True,
        )
        documentos.extend(loader.load())

    if not documentos:
        print(f"[RAG Indexer]: Nenhum arquivo .sql ou .txt encontrado em '{pasta_alvo}'.")
        return 0

    print(f"[RAG Indexer]: {len(documentos)} arquivos carregados. Gerando chunks...")

    # Quebra os arquivos em chunks de 1000 caracteres com 200 de overlap
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n-- ====", "\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_documents(documentos)

    print(
        f"[RAG Indexer]: Inicializando modelo de embeddings '{EMBEDDING_MODEL_NAME}'..."
    )
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

    # Limpa índice anterior caso exista para evitar duplicação ao reindexar
    caminho_chroma = Path(pasta_chroma)
    if caminho_chroma.exists():
        shutil.rmtree(caminho_chroma)

    print(f"[RAG Indexer]: Gravando {len(chunks)} chunks em '{caminho_chroma}'...")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(caminho_chroma),
    )

    return len(chunks)


if __name__ == "__main__":
    print("=== Iniciando Indexação da Base de Conhecimento DBA (RAG Local) ===")
    sincronizar_scripts_oracle()
    total_chunks = indexar_base_conhecimento()
    print(f"\n[Concluído]: {total_chunks} chunks salvos com sucesso em '{CHROMA_DB_DIR}'!")

```

## Arquivo: `src/tools/rag_search.py`
```py
"""
Módulo de Busca Semântica RAG Local (Retrieval-Augmented Generation) para o Agente Coordenador.
Consulta o banco vetorial local (./chroma_db) com embeddings HuggingFace (all-MiniLM-L6-v2)
para recuperar scripts SQL homologados e manuais do DBA.
"""
import json
import warnings
from pathlib import Path
from typing import Any, Dict, List

warnings.filterwarnings("ignore")

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

SRC_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = SRC_DIR.parent
CHROMA_DB_DIR = PROJECT_ROOT / "chroma_db"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Cache em memória para evitar recarregar o modelo de embeddings a cada chamada do Agente
_EMBEDDINGS_INSTANCE = None
_VECTORSTORE_INSTANCE = None


def _obter_vectorstore() -> Chroma:
    """Inicializa e mantém em cache a conexão com o ChromaDB local e o modelo de embeddings."""
    global _EMBEDDINGS_INSTANCE, _VECTORSTORE_INSTANCE
    if _EMBEDDINGS_INSTANCE is None:
        _EMBEDDINGS_INSTANCE = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)
    if _VECTORSTORE_INSTANCE is None:
        _VECTORSTORE_INSTANCE = Chroma(
            persist_directory=str(CHROMA_DB_DIR),
            embedding_function=_EMBEDDINGS_INSTANCE,
        )
    return _VECTORSTORE_INSTANCE


def buscar_script_interno(tema_ou_problema: str) -> str:
    """
    Realiza busca de similaridade semântica (Top 3) no ChromaDB local (./chroma_db)
    e retorna os trechos e caminhos dos scripts SQL homologados em formato JSON.
    """
    if not CHROMA_DB_DIR.exists():
        return json.dumps(
            {
                "status": "erro",
                "mensagem": (
                    f"Base vetorial não encontrada em '{CHROMA_DB_DIR}'. "
                    "Execute 'python src/tools/rag_indexer.py' primeiro."
                ),
            },
            ensure_ascii=False,
        )

    try:
        vectorstore = _obter_vectorstore()
        resultados = vectorstore.similarity_search_with_score(tema_ou_problema, k=3)

        scripts_encontrados = []
        arquivos_vistos = set()
        for doc, score in resultados:
            caminho_origem = doc.metadata.get("source", "desconhecido")
            try:
                nome_relativo = str(
                    Path(caminho_origem).relative_to(PROJECT_ROOT / "MeusScripts")
                )
            except ValueError:
                nome_relativo = Path(caminho_origem).name

            # Se o arquivo completo for compacto (<= 3000 caracteres), entrega o script SQL inteiro
            # para garantir que o Agente receba tanto o cabeçalho explicativo quanto a query SQL executável.
            conteudo_final = doc.page_content.strip()
            caminho_path = Path(caminho_origem)
            if caminho_path.exists() and nome_relativo not in arquivos_vistos:
                try:
                    texto_completo = caminho_path.read_text(encoding="utf-8", errors="replace").strip()
                    if len(texto_completo) <= 3000:
                        conteudo_final = texto_completo
                    else:
                        conteudo_final = texto_completo[:3000] + "\n-- ... [TRUNCADO] ..."
                except Exception:
                    pass
            arquivos_vistos.add(nome_relativo)

            scripts_encontrados.append(
                {
                    "arquivo": nome_relativo.replace("\\", "/"),
                    "score_distancia": round(float(score), 4),
                    "conteudo_sql": conteudo_final,
                }
            )

        return json.dumps(
            {
                "status": "sucesso",
                "consulta": tema_ou_problema,
                "total_encontrado": len(scripts_encontrados),
                "scripts_homologados": scripts_encontrados,
            },
            ensure_ascii=False,
        )

    except Exception as exc:
        return json.dumps(
            {
                "status": "erro",
                "consulta": tema_ou_problema,
                "mensagem": str(exc),
            },
            ensure_ascii=False,
        )


# Schema no padrão OpenAI Tool Calling para exportação ao Orquestrador
rag_tools_schema: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "buscar_script_interno",
            "description": (
                "Pesquisa na base de conhecimento local do DBA por scripts SQL homologados, "
                "manuais ou queries históricas. Use sempre que precisar de uma query complexa "
                "que você não sabe de cor."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tema_ou_problema": {
                        "type": "string",
                        "description": (
                            "O tema técnico, sintoma ou problema a ser pesquisado na base de scripts "
                            "(ex: 'bloqueio de linha lock', 'uso de tablespace', 'sessões inativas', 'rman backup')."
                        ),
                    }
                },
                "required": ["tema_ou_problema"],
            },
        },
    }
]


if __name__ == "__main__":
    print("=== Teste Isolado de Busca RAG Local (Top 3 Scripts DBA) ===")
    consulta_teste = "script para identificar bloqueios de linha e sessões bloqueadoras (locks)"
    print(f"\nPesquisando por: '{consulta_teste}'...")
    resultado_json = buscar_script_interno(consulta_teste)
    print("\n[Resultado do RAG]:")
    print(resultado_json)

```

## Arquivo: `src/main.py`
```py
"""Orquestrador Central do Personal Agent (Windows + Oracle DBA + Gemini Cloud Router + Barreira HITL & Notificador) com Auditoria Completa."""
import json
import logging
import os
import socket
import sys
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# Garante que os pacotes em src/ sejam resolvidos independentemente do diretório de execução
SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
for path_str in (str(ROOT_DIR), str(SRC_DIR)):
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

load_dotenv(ROOT_DIR / ".env")

# Configuração do Log de Auditoria (Formato: YYYY-MM-DD HH:MM:SS | INFO | Mensagem)
LOG_FILE_ROOT = ROOT_DIR / "auditoria_oracle.log"
LOG_FILE_DATA = ROOT_DIR / "data" / "logs" / "auditoria_oracle.log"
LOG_FILE_DATA.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE_ROOT, encoding="utf-8"),
        logging.FileHandler(LOG_FILE_DATA, encoding="utf-8"),
    ],
)
# Silencia logs de transporte HTTP para manter o auditoria_oracle.log 100% limpo
for noisy_logger in ("httpx", "httpx2", "httpcore", "httpcore2", "openai"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# 1. Importando as Ferramentas de SO
from tools.os_tools import (
    os_tools_schema,
    coletar_metricas_hardware,
    verificar_espaco_disco,
)

# 2. Importando as Ferramentas do Oracle (Incluindo matar_sessao_oracle - Fase 4 HITL)
from tools.oracle_dba import (
    oracle_tools_schema,
    coletar_sessoes_ativas,
    coletar_top_sql,
    coletar_plano_execucao,
    matar_sessao_oracle,
)

# 3. Importando a Ferramenta de Nuvem (Gemini), o Notificador SMTP e a Busca RAG Local
from tools.gemini_router import (
    gemini_tools_schema,
    analisar_log_complexo,
)
from tools.notificador import enviar_alerta_email
from tools.rag_search import (
    rag_tools_schema,
    buscar_script_interno,
)


def _inicializar_cliente_coordenador() -> tuple[OpenAI, str]:
    """
    Conecta prioritariamente ao Ollama local (http://localhost:11434/v1 com qwen2.5:7b).
    Caso o serviço local do Ollama não esteja ativo na máquina no momento do teste,
    ativa automaticamente o endpoint compatível OpenAI usando a GEMINI_API_KEY do .env.
    """
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.5):
            return (
                OpenAI(base_url="http://localhost:11434/v1", api_key="local"),
                "qwen2.5:7b",
            )
    except OSError:
        gemini_key = os.getenv("GEMINI_API_KEY", "local")
        return (
            OpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=gemini_key,
            ),
            "gemini-3.1-flash-lite-preview",
        )


client, MODELO = _inicializar_cliente_coordenador()

# 4. Unificando o Catálogo de Ferramentas (Agora com 4 frentes: SO + Oracle + Gemini Cloud + RAG Local)
todas_ferramentas = (
    os_tools_schema + oracle_tools_schema + gemini_tools_schema + rag_tools_schema
)

# 5. System Prompt do Coordenador
SYSTEM_PROMPT = """Você é o Agente Coordenador, o cérebro central de um sistema autônomo local de administração de TI e Banco de Dados.
Seus princípios absolutos são:
1. Precisão acima de velocidade.
2. Evidência acima de opinião.

DIRETRIZES DE COMPORTAMENTO E DELEGAÇÃO:
- Nunca invente métricas, queries, logs ou estados do sistema. Chame as ferramentas.
- Para problemas simples, responda no formato: Diagnóstico, Evidências, Possíveis Causas e Próximo Passo.
- REGRA DE OURO: Se você extrair um plano de execução (DBMS_XPLAN) ou quando o usuário pedir uma análise profunda do plano de execução, acione IMEDIATAMENTE a ferramenta 'analisar_log_complexo' passando o plano extraído para terceirizar a análise. Não tente adivinhar.
- SEGURANÇA (HITL): Apenas acione 'matar_sessao_oracle' quando o usuário solicitar explicitamente para matar ou encerrar uma sessão informando SID e SERIAL.
"""


def executar_agente(prompt_usuario: str) -> None:
    print(f"\n[Usuário]: {prompt_usuario}")

    # Inicia o contexto com o System Prompt + Pergunta do Usuário
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt_usuario},
    ]

    # Loop de Tool Calling
    max_passos = 6
    passo = 0

    while passo < max_passos:
        passo += 1
        response = client.chat.completions.create(
            model=MODELO,
            messages=messages,
            tools=todas_ferramentas,
        )

        mensagem_resposta = response.choices[0].message

        # Se o LLM não solicitou mais ferramentas, imprime a resposta final e encerra
        if not mensagem_resposta.tool_calls:
            print(f"\n[Agente Coordenador]:\n{mensagem_resposta.content}")
            return

        messages.append(mensagem_resposta)

        for tool_call in mensagem_resposta.tool_calls:
            nome_funcao = tool_call.function.name
            argumentos = (
                json.loads(tool_call.function.arguments)
                if tool_call.function.arguments
                else {}
            )
            print(f"[Sistema]: O Agente decidiu executar '{nome_funcao}'...")

            # 2. Auditoria: Registra a intenção do LLM (O que ele decidiu fazer)
            if (
                nome_funcao.startswith("coletar_")
                or nome_funcao == "analisar_log_complexo"
                or nome_funcao == "matar_sessao_oracle"
                or nome_funcao == "buscar_script_interno"
            ):
                logging.info(f"AGENTE ACIONOU: {nome_funcao} | PARÂMETROS: {argumentos}")

            # 3. Roteamento Dinâmico (Switch Case / If-Elif) com Barreira HITL + Notificador SMTP
            try:
                # Rotas do Windows
                if nome_funcao == "coletar_metricas_hardware":
                    resultado_tool = coletar_metricas_hardware()
                elif nome_funcao == "verificar_espaco_disco":
                    resultado_tool = verificar_espaco_disco(
                        argumentos.get("drive", "C:\\")
                    )

                # Rotas do Oracle
                elif nome_funcao == "coletar_sessoes_ativas":
                    resultado_tool = coletar_sessoes_ativas()
                elif nome_funcao == "coletar_top_sql":
                    resultado_tool = coletar_top_sql(argumentos.get("limite", 3))
                elif nome_funcao == "coletar_plano_execucao":
                    resultado_tool = coletar_plano_execucao(argumentos.get("sql_id"))

                elif nome_funcao == "matar_sessao_oracle":
                    sid = argumentos.get("sid")
                    serial = argumentos.get("serial")

                    # 1. Barreira HITL (Pausa a execução)
                    print(
                        f"\n\033[91m[ALERTA CRÍTICO]: O agente deseja matar a sessão SID {sid}, SERIAL {serial}.\033[0m"
                    )
                    aprovacao = (
                        input("Você aprova esta ação destrutiva? [S/N]: ")
                        .strip()
                        .upper()
                    )

                    if aprovacao == "S":
                        logging.info(
                            f"AUDITORIA HITL: APROVADO pelo DBA humano | "
                            f"AÇÃO: {nome_funcao} | SID={sid}, SERIAL={serial}"
                        )
                        # 2. Dispara e-mail de alerta de intervenção
                        assunto = f"[AGENTE DBA] Intervenção Crítica Aprovada: Kill Session {sid},{serial}"
                        corpo = (
                            f"O agente identificou anomalias e o encerramento da sessão "
                            f"SID {sid} (Serial: {serial}) foi aprovado manualmente via terminal."
                        )
                        sucesso_email, msg_email = enviar_alerta_email(assunto, corpo)
                        print(f"[Sistema]: Notificação por e-mail: {msg_email}")
                        logging.info(
                            f"NOTIFICAÇÃO SMTP: Sucesso={sucesso_email} | Detalhe: {msg_email}"
                        )

                        # 3. Executa a ação no banco
                        resultado_tool = matar_sessao_oracle(sid, serial)
                    else:
                        # 4. Aborta e avisa o LLM
                        print("[Sistema]: Ação abortada pelo administrador.")
                        logging.warning(
                            f"AUDITORIA HITL: REJEITADO pelo DBA humano | "
                            f"AÇÃO: {nome_funcao} | SID={sid}, SERIAL={serial}"
                        )
                        resultado_tool = json.dumps(
                            {
                                "status": "abortado",
                                "mensagem": "O DBA humano negou a execução da ação.",
                            },
                            ensure_ascii=False,
                        )

                # Rota: Nuvem / Gemini
                elif nome_funcao == "analisar_log_complexo":
                    resultado_tool = analisar_log_complexo(
                        dados_brutos=argumentos.get("dados_brutos", ""),
                        contexto_solicitacao=argumentos.get(
                            "contexto_solicitacao",
                            "Análise de performance solicitada pelo DBA.",
                        ),
                    )

                # Rota: Base de Conhecimento RAG Local (Scripts DBA Homologados)
                elif nome_funcao == "buscar_script_interno":
                    resultado_tool = buscar_script_interno(
                        tema_ou_problema=argumentos.get("tema_ou_problema", "")
                    )

                else:
                    resultado_tool = json.dumps(
                        {"erro": f"Ferramenta {nome_funcao} desconhecida."},
                        ensure_ascii=False,
                    )

            except Exception as e:
                resultado_tool = json.dumps(
                    {"erro_execucao": str(e)}, ensure_ascii=False
                )

            # 4. Auditoria: Registra a evidência/resultado retornado pelo banco ou pelo bloqueio HITL
            if (
                nome_funcao.startswith("coletar_")
                or nome_funcao == "analisar_log_complexo"
                or nome_funcao == "matar_sessao_oracle"
                or nome_funcao == "buscar_script_interno"
            ):
                logging.info(f"RESULTADO ORACLE: {resultado_tool}")

            # Devolve o JSON com as evidências para a IA ler
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": nome_funcao,
                    "content": resultado_tool,
                }
            )

    # Caso atinja o limite de passos de ferramentas, gera o laudo final com o que foi coletado
    resposta_final = client.chat.completions.create(
        model=MODELO,
        messages=messages,
    )
    print(f"\n[Agente Coordenador]:\n{resposta_final.choices[0].message.content}")


if __name__ == "__main__":
    print("Iniciando Agente Híbrido (Windows + Oracle + Gemini Cloud + HITL + RAG Local)...")

    # Teste 5: Busca RAG Local na Base de Scripts Homologados do DBA
    executar_agente(
        "Busque na nossa base de conhecimento interna um script SQL homologado para identificar bloqueios de linha (locks) mostrando o ROWID bloqueado."
    )

```

## Arquivo: `app.py`
```py
"""
Personal Agent DBA - Dashboard Web Interativo (Streamlit)
Unifica Monitoramento de Hardware Windows, Diagnóstico Oracle Database (Modo Thin + VPN Check),
Roteamento LLM em Nuvem (Gemini API) e Barreira de Segurança HITL (Human-in-the-Loop) com Alerta SMTP.

Para executar:
    streamlit run app.py
"""
import json
import logging
import os
import socket
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# ==============================================================================
# 1. CONFIGURAÇÃO DE CAMINHOS, AMBIENTE E AUDITORIA
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src" if (BASE_DIR / "src").exists() else BASE_DIR
ROOT_DIR = BASE_DIR if (BASE_DIR / "src").exists() else BASE_DIR.parent

for path_str in (str(ROOT_DIR), str(SRC_DIR)):
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

load_dotenv(ROOT_DIR / ".env")

LOG_FILE_ROOT = ROOT_DIR / "auditoria_oracle.log"
LOG_FILE_DATA = ROOT_DIR / "data" / "logs" / "auditoria_oracle.log"
LOG_FILE_DATA.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE_ROOT, encoding="utf-8"),
        logging.FileHandler(LOG_FILE_DATA, encoding="utf-8"),
    ],
)
for noisy_logger in ("httpx", "httpx2", "httpcore", "httpcore2", "openai"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# Importação das Ferramentas do Agente
from tools.os_tools import (
    os_tools_schema,
    coletar_metricas_hardware,
    verificar_espaco_disco,
)
from tools.oracle_dba import (
    oracle_tools_schema,
    verificar_acessibilidade_host,
    coletar_sessoes_ativas,
    coletar_top_sql,
    coletar_plano_execucao,
    matar_sessao_oracle,
)
from tools.gemini_router import (
    gemini_tools_schema,
    analisar_log_complexo,
)
from tools.notificador import enviar_alerta_email
from tools.rag_search import (
    rag_tools_schema,
    buscar_script_interno,
)

# Catálogo Unificado de Ferramentas (Windows + Oracle + Gemini Cloud + RAG Local)
TODAS_FERRAMENTAS = (
    os_tools_schema + oracle_tools_schema + gemini_tools_schema + rag_tools_schema
)

SYSTEM_PROMPT = """Você é o Agente Coordenador, o cérebro central de um sistema autônomo local de administração de TI e Banco de Dados.
Seus princípios absolutos são:
1. Precisão acima de velocidade.
2. Evidência acima de opinião.

DIRETRIZES DE COMPORTAMENTO E DELEGAÇÃO:
- Nunca invente métricas, queries, logs ou estados do sistema. Chame as ferramentas.
- Para problemas simples, responda no formato: Diagnóstico, Evidências, Possíveis Causas e Próximo Passo.
- REGRA DE OURO: Se você extrair um plano de execução (DBMS_XPLAN) ou quando o usuário pedir uma análise profunda do plano de execução, acione IMEDIATAMENTE a ferramenta 'analisar_log_complexo' passando o plano extraído para terceirizar a análise. Não tente adivinhar.
- SEGURANÇA (HITL): Acione 'matar_sessao_oracle' apenas quando o usuário solicitar explicitamente para matar, derrubar ou encerrar uma sessão (usando o SID e SERIAL informados pelo usuário ou identificados via 'coletar_sessoes_ativas').
"""


# ==============================================================================
# 2. CONEXÃO COM O MOTOR LLM E VERIFICAÇÕES DE STATUS
# ==============================================================================
def verificar_status_ollama() -> bool:
    """Verifica via socket rápido se o serviço Ollama local está respondendo na porta 11434."""
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.4):
            return True
    except OSError:
        return False


def obter_cliente_llm() -> tuple[OpenAI, str, bool]:
    """
    Retorna (cliente_openai, nome_modelo, ollama_ativo).
    Prioriza o Ollama local (qwen2.5:7b) e usa o endpoint compatível Gemini caso o Ollama esteja offline.
    """
    if verificar_status_ollama():
        return (
            OpenAI(base_url="http://localhost:11434/v1", api_key="local"),
            os.getenv("MODEL_NAME", "qwen2.5:7b"),
            True,
        )
    gemini_key = os.getenv("GEMINI_API_KEY", "local")
    return (
        OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=gemini_key,
        ),
        "gemini-3.1-flash-lite-preview",
        False,
    )


def serializar_mensagem_assistant(mensagem_resposta: Any) -> Dict[str, Any]:
    """Converte o objeto ChatCompletionMessage em dicionário puro para persistir no st.session_state."""
    msg_dict: Dict[str, Any] = {
        "role": "assistant",
        "content": mensagem_resposta.content or "",
    }
    if mensagem_resposta.tool_calls:
        msg_dict["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in mensagem_resposta.tool_calls
        ]
    return msg_dict


# ==============================================================================
# 3. ORQUESTRADOR ADAPTADO PARA STREAMING E BARREIRA HITL (st.session_state)
# ==============================================================================
def executar_agente_ui(prompt_usuario: str) -> Generator[str, None, None]:
    """
    Executa o ciclo de decisão do Agente Coordenador fazendo yield de eventos de progresso
    para o Streamlit. Caso o Agente solicite 'matar_sessao_oracle', ativa
    st.session_state.hitl_pendente e pausa imediatamente o loop aguardando decisão nos botões da UI.
    """
    client, modelo_ativo, _ = obter_cliente_llm()

    # Adiciona a pergunta do usuário ao contexto do LLM
    st.session_state.llm_messages.append({"role": "user", "content": prompt_usuario})

    max_passos = 6
    passo = 0

    while passo < max_passos:
        passo += 1
        yield f"🧠 Consultando Agente Coordenador (`{modelo_ativo}` - Passo {passo})..."

        response = client.chat.completions.create(
            model=modelo_ativo,
            messages=st.session_state.llm_messages,
            tools=TODAS_FERRAMENTAS,
        )
        mensagem_resposta = response.choices[0].message

        # Caso o LLM tenha concluído o raciocínio e gerado o laudo final
        if not mensagem_resposta.tool_calls:
            texto_final = mensagem_resposta.content or "Diagnóstico concluído."
            st.session_state.llm_messages.append(
                {"role": "assistant", "content": texto_final}
            )
            st.session_state.messages.append(
                {"role": "assistant", "content": texto_final}
            )
            yield "✅ Laudo técnico consolidado."
            return

        # Registra a mensagem do assistant contendo as chamadas de ferramentas
        st.session_state.llm_messages.append(
            serializar_mensagem_assistant(mensagem_resposta)
        )

        # Processa cada ferramenta solicitada
        for idx, tool_call in enumerate(mensagem_resposta.tool_calls):
            nome_funcao = tool_call.function.name
            argumentos = (
                json.loads(tool_call.function.arguments)
                if tool_call.function.arguments
                else {}
            )

            # Auditoria: Registra intenção do Agente
            if (
                nome_funcao.startswith("coletar_")
                or nome_funcao == "analisar_log_complexo"
                or nome_funcao == "matar_sessao_oracle"
            ):
                logging.info(f"AGENTE ACIONOU: {nome_funcao} | PARÂMETROS: {argumentos}")

            # ------------------------------------------------------------------
            # BARREIRA HITL BASEADA EM ESTADO (Pausa o fluxo sem usar input())
            # ------------------------------------------------------------------
            if nome_funcao == "matar_sessao_oracle":
                sid_alvo = argumentos.get("sid")
                serial_alvo = argumentos.get("serial")

                # Se houver outras tool_calls na mesma resposta que ainda não rodaram, guarda-as
                calls_restantes = mensagem_resposta.tool_calls[idx + 1 :]
                st.session_state.hitl_pendente = {
                    "tool_call_id": tool_call.id,
                    "nome_funcao": nome_funcao,
                    "sid": sid_alvo,
                    "serial": serial_alvo,
                    "calls_restantes": [
                        {
                            "id": c.id,
                            "name": c.function.name,
                            "arguments": c.function.arguments,
                        }
                        for c in calls_restantes
                    ],
                }
                yield (
                    f"🛑 **BARREIRA HITL ATIVADA:** Aguardando aprovação humana para "
                    f"`ALTER SYSTEM KILL SESSION '{sid_alvo},{serial_alvo}' IMMEDIATE`..."
                )
                return

            # Execução normal das ferramentas de coleta e análise
            yield f"🔧 Executando ferramenta `{nome_funcao}`..."
            try:
                if nome_funcao == "coletar_metricas_hardware":
                    resultado_tool = coletar_metricas_hardware()
                elif nome_funcao == "verificar_espaco_disco":
                    resultado_tool = verificar_espaco_disco(
                        argumentos.get("drive", "C:\\")
                    )
                elif nome_funcao == "coletar_sessoes_ativas":
                    resultado_tool = coletar_sessoes_ativas()
                elif nome_funcao == "coletar_top_sql":
                    resultado_tool = coletar_top_sql(argumentos.get("limite", 3))
                elif nome_funcao == "coletar_plano_execucao":
                    resultado_tool = coletar_plano_execucao(argumentos.get("sql_id"))
                elif nome_funcao == "analisar_log_complexo":
                    resultado_tool = analisar_log_complexo(
                        dados_brutos=argumentos.get("dados_brutos", ""),
                        contexto_solicitacao=argumentos.get(
                            "contexto_solicitacao",
                            "Análise de performance solicitada pelo DBA.",
                        ),
                    )
                elif nome_funcao == "buscar_script_interno":
                    resultado_tool = buscar_script_interno(
                        tema_ou_problema=argumentos.get("tema_ou_problema", "")
                    )
                else:
                    resultado_tool = json.dumps(
                        {"erro": f"Ferramenta {nome_funcao} desconhecida."},
                        ensure_ascii=False,
                    )
            except Exception as exc:
                resultado_tool = json.dumps(
                    {"erro_execucao": str(exc)}, ensure_ascii=False
                )

            # Auditoria: Registra o resultado retornado pela ferramenta
            if (
                nome_funcao.startswith("coletar_")
                or nome_funcao == "analisar_log_complexo"
            ):
                logging.info(f"RESULTADO ORACLE: {resultado_tool}")

            st.session_state.llm_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": nome_funcao,
                    "content": resultado_tool,
                }
            )


def processar_decisao_hitl(aprovado: bool) -> None:
    """
    Processa o clique do DBA nos botões 'Aprovar Execução' ou 'Abortar' da barreira HITL,
    registra na trilha de auditoria, dispara o alerta SMTP (se aprovado) e retoma o LLM.
    """
    pendencia = st.session_state.hitl_pendente
    if not pendencia:
        return

    sid = pendencia["sid"]
    serial = pendencia["serial"]
    tool_call_id = pendencia["tool_call_id"]
    nome_funcao = pendencia["nome_funcao"]

    if aprovado:
        logging.info(
            f"AUDITORIA HITL: APROVADO pelo DBA humano (Web UI) | "
            f"AÇÃO: {nome_funcao} | SID={sid}, SERIAL={serial}"
        )
        assunto = f"[AGENTE DBA] Intervenção Crítica Aprovada: Kill Session {sid},{serial}"
        corpo = (
            f"O agente identificou anomalias e o encerramento da sessão "
            f"SID {sid} (Serial: {serial}) foi aprovado manualmente via Dashboard Web Streamlit."
        )
        sucesso_email, msg_email = enviar_alerta_email(assunto, corpo)
        logging.info(
            f"NOTIFICAÇÃO SMTP: Sucesso={sucesso_email} | Detalhe: {msg_email}"
        )

        resultado_tool = matar_sessao_oracle(sid=sid, serial=serial)
        aviso_ui = (
            f"✅ **Intervenção Aprovada pelo DBA:** Comando `KILL SESSION '{sid},{serial}'` enviado ao Oracle. "
            f"*(Notificação SMTP: {msg_email})*"
        )
    else:
        logging.warning(
            f"AUDITORIA HITL: REJEITADO pelo DBA humano (Web UI) | "
            f"AÇÃO: {nome_funcao} | SID={sid}, SERIAL={serial}"
        )
        resultado_tool = json.dumps(
            {
                "status": "abortado",
                "mensagem": "O DBA humano negou a execução da ação via Dashboard.",
            },
            ensure_ascii=False,
        )
        aviso_ui = f"🛑 **Ação Abortada pelo DBA:** O encerramento da sessão `{sid},{serial}` foi negado."

    logging.info(f"RESULTADO ORACLE: {resultado_tool}")

    # Devolve o resultado da decisão HITL para o contexto do LLM
    st.session_state.llm_messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": nome_funcao,
            "content": resultado_tool,
        }
    )

    # Caso houvesse outras tool_calls pendentes no mesmo turno, preenche como abortadas/canceladas
    for call_extra in pendencia.get("calls_restantes", []):
        st.session_state.llm_messages.append(
            {
                "role": "tool",
                "tool_call_id": call_extra["id"],
                "name": call_extra["name"],
                "content": json.dumps({"status": "cancelado_por_barreira_hitl"}),
            }
        )

    # Limpa o estado de bloqueio HITL
    st.session_state.hitl_pendente = None
    st.session_state.messages.append({"role": "assistant", "content": aviso_ui})

    # Solicita ao LLM a resposta de fechamento pós-decisão HITL
    client, modelo_ativo, _ = obter_cliente_llm()
    resposta_pos_hitl = client.chat.completions.create(
        model=modelo_ativo,
        messages=st.session_state.llm_messages,
    )
    laudo_fechamento = (
        resposta_pos_hitl.choices[0].message.content
        or "Operação finalizada conforme decisão do DBA."
    )
    st.session_state.llm_messages.append(
        {"role": "assistant", "content": laudo_fechamento}
    )
    st.session_state.messages.append(
        {"role": "assistant", "content": laudo_fechamento}
    )


# ==============================================================================
# 4. INTERFACE GRÁFICA STREAMLIT (LAYOUT WIDE, SIDEBAR, MÉTRICAS E CHAT)
# ==============================================================================
st.set_page_config(
    page_title="Personal Agent DBA | Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inicialização de estados persistentes no st.session_state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Olá! Sou o **Agente Coordenador de TI e Banco de Dados**. "
                "Posso monitorar recursos da sua máquina Windows, analisar sessões e *Top SQL* no Oracle, "
                "escalar planos `DBMS_XPLAN` complexos para o Gemini em nuvem e executar intervenções "
                "protegidas por aprovação **HITL**."
            ),
        }
    ]

if "llm_messages" not in st.session_state:
    st.session_state.llm_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

if "hitl_pendente" not in st.session_state:
    st.session_state.hitl_pendente = None


# ------------------------------------------------------------------------------
# BARRA LATERAL (SIDEBAR): STATUS DOS MOTORES E BANCOS DE DADOS
# ------------------------------------------------------------------------------
with st.sidebar:
    st.title("🛡️ Agente DBA Local")
    st.caption("Arquitetura Híbrida: Local + Cloud + HITL")
    st.divider()

    st.subheader("📡 Status de Conectividade")

    # 1. Status do Ollama Local / Motor Coordenador
    _, modelo_coordenador, ollama_online = obter_cliente_llm()
    if ollama_online:
        st.success(f"**Ollama Local:** Online (`{modelo_coordenador}`)")
    else:
        st.warning(
            f"**Ollama Local (11434):** Offline\n\n"
            f"⚡ *Failover Ativo:* `{modelo_coordenador}`"
        )

    # 2. Status do Segundo Cérebro (Gemini Cloud API)
    gemini_key_cfg = os.getenv("GEMINI_API_KEY", "")
    if gemini_key_cfg and gemini_key_cfg not in ("sua_chave_aqui", "your_gemini_api_key_here"):
        st.success(
            f"**Gemini Cloud Router:** Ativo (`{os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview')}`)"
        )
    else:
        st.error("**Gemini Cloud Router:** Chave ausente no `.env`")

    # 3. Status do Banco de Dados Oracle (VPN / Listener Check)
    dsn_atual = os.getenv("ORACLE_DSN", "NAO_CONFIGURADO")
    check_oracle = verificar_acessibilidade_host(dsn_atual, timeout=2.0)
    if check_oracle["acessivel"]:
        st.success(
            f"**Oracle DB (`{dsn_atual}`):** Acessível\n\n"
            f"⏱️ Latência VPN: `{check_oracle['latencia_ms']} ms`"
        )
    else:
        st.error(
            f"**Oracle DB (`{dsn_atual}`):** Inacessível\n\n"
            f"🔒 Verifique a conexão VPN."
        )

    # 4. Status do Notificador SMTP
    email_dest = os.getenv("EMAIL_DESTINATARIO", "")
    if email_dest and "seu_email" not in email_dest:
        st.info(f"📧 **Alertas HITL:** `{email_dest}`")

    st.divider()

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Atualizar", use_container_width=True):
            st.rerun()
    with col_btn2:
        if st.button("🗑️ Limpar Chat", use_container_width=True):
            st.session_state.messages = [st.session_state.messages[0]]
            st.session_state.llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            st.session_state.hitl_pendente = None
            st.rerun()

    with st.expander("📜 Auditoria (`auditoria_oracle.log`)", expanded=False):
        if LOG_FILE_ROOT.exists():
            linhas_log = LOG_FILE_ROOT.read_text(encoding="utf-8", errors="replace").splitlines()
            st.code("\n".join(linhas_log[-12:]), language="text")
        else:
            st.caption("Nenhum registro de auditoria ainda.")


# ------------------------------------------------------------------------------
# ÁREA PRINCIPAL: DIVIDIDA ENTRE TELEMETRIA EM TEMPO REAL E CONSOLE DE CHAT
# ------------------------------------------------------------------------------
st.markdown("## 🖥️ Centro de Comando Autônomo - TI & Banco de Dados Oracle")

col_telemetria, col_chat = st.columns([1.05, 1.35], gap="large")

# === COLUNA ESQUERDA: MÉTRICAS E GRÁFICOS EM TEMPO REAL ===
with col_telemetria:
    st.subheader("📊 Telemetria em Tempo Real (Edge Filtering)")

    hw_raw = json.loads(coletar_metricas_hardware())
    disco_raw = json.loads(verificar_espaco_disco("C:\\"))
    oracle_sess_raw = (
        json.loads(coletar_sessoes_ativas())
        if check_oracle["acessivel"]
        else {"status": "erro", "sessoes_ativas": 0, "sessoes_identificadas": []}
    )

    dados_hw = hw_raw.get("dados", {})
    dados_disco = disco_raw.get("dados", {})

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("CPU Local", f"{dados_hw.get('cpu_percentual', 0.0)}%")
    kpi2.metric(
        "RAM Usada",
        f"{dados_hw.get('ram_usada_gb', 0.0)} GB",
        f"{dados_hw.get('ram_percentual', 0.0)}%",
        delta_color="inverse",
    )
    kpi3.metric(
        "Disco C:\\",
        f"{dados_disco.get('percentual_usado', 0.0)}%",
        f"{dados_disco.get('livre_gb', 0.0)} GB livres",
        delta_color="off",
    )
    kpi4.metric(
        "Sessões Oracle",
        str(oracle_sess_raw.get("sessoes_ativas", "Offline")),
        "Ativas" if check_oracle["acessivel"] else "VPN Off",
    )

    # Gráfico de Barras de Utilização de Hardware Local
    df_recursos = pd.DataFrame(
        {
            "Recurso": ["CPU (%)", "Memória RAM (%)", "Disco C:\\ (%)"],
            "Uso (%)": [
                dados_hw.get("cpu_percentual", 0.0),
                dados_hw.get("ram_percentual", 0.0),
                dados_disco.get("percentual_usado", 0.0),
            ],
        }
    ).set_index("Recurso")
    st.bar_chart(df_recursos, height=200)

    # Tabelas de Sessões e Top SQL do Oracle
    aba_sessoes, aba_top_sql = st.tabs(
        ["👥 Sessões de Usuário (GV$SESSION)", "🔥 Top SQL (GV$SQLAREA)"]
    )

    with aba_sessoes:
        sessoes_lista = oracle_sess_raw.get("sessoes_identificadas", [])
        if sessoes_lista:
            st.dataframe(pd.DataFrame(sessoes_lista), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma sessão de usuário adicional identificada no momento.")

    with aba_top_sql:
        if check_oracle["acessivel"]:
            top_sql_raw = json.loads(coletar_top_sql(limite=3))
            lista_sql = top_sql_raw.get("top_sql", [])
            if lista_sql:
                st.dataframe(pd.DataFrame(lista_sql), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma query de aplicação encontrada no cache.")
        else:
            st.warning("Conecte a VPN para visualizar o Top SQL da instância Oracle.")


# === COLUNA DIREITA: CHAT INTERATIVO E BARREIRA HITL ===
with col_chat:
    st.subheader("💬 Console do Agente Coordenador")

    # Botões de Diagnóstico Rápido
    atalho1, atalho2, atalho3 = st.columns(3)
    prompt_atalho = None
    if atalho1.button("🔍 Health Check Geral", use_container_width=True):
        prompt_atalho = "Verifique o consumo de hardware da minha máquina e quantas sessões ativas temos no Oracle."
    if atalho2.button("📈 Analisar Top SQL (Gemini)", use_container_width=True):
        prompt_atalho = "Descubra a query mais pesada do banco e me dê uma análise profunda do plano de execução."
    if atalho3.button("⚡ Testar Barreira HITL", use_container_width=True):
        prompt_atalho = "Preciso derrubar imediatamente a sessão travada de SID 9999 e SERIAL 12345 no banco Oracle."

    # Container rolável de mensagens do chat
    chat_container = st.container(height=430)
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # ----------------------------------------------------------------------
        # RENDERIZAÇÃO DO ALERTA HITL (SE HOUVER AÇÃO DESTRUTIVA PENDENTE)
        # ----------------------------------------------------------------------
        if st.session_state.hitl_pendente:
            pend = st.session_state.hitl_pendente
            st.error(
                f"🚨 **BARREIRA DE SEGURANÇA (HITL) - APROVAÇÃO OBRIGATÓRIA**\n\n"
                f"O Agente Coordenador solicitou a execução de um comando **destrutivo** na instância `{dsn_atual}`:\n"
                f"```sql\nALTER SYSTEM KILL SESSION '{pend['sid']},{pend['serial']}' IMMEDIATE;\n```\n"
                f"Ao aprovar, um alerta de governança também será disparado por e-mail para `{email_dest}`."
            )
            btn_col_aprovar, btn_col_abortar = st.columns(2)
            with btn_col_aprovar:
                if st.button(
                    "✅ Aprovar Execução",
                    type="primary",
                    use_container_width=True,
                    key="btn_hitl_approve",
                ):
                    with st.spinner("Disparando alerta SMTP e executando KILL SESSION no Oracle..."):
                        processar_decisao_hitl(aprovado=True)
                    st.rerun()
            with btn_col_abortar:
                if st.button(
                    "🛑 Abortar",
                    type="secondary",
                    use_container_width=True,
                    key="btn_hitl_abort",
                ):
                    with st.spinner("Registrando bloqueio na auditoria e notificando o Agente..."):
                        processar_decisao_hitl(aprovado=False)
                    st.rerun()

    # Entrada de texto do usuário (desabilitada enquanto houver decisão HITL pendente)
    prompt_digitado = st.chat_input(
        "Digite um comando ou diagnóstico para o Agente DBA...",
        disabled=st.session_state.hitl_pendente is not None,
    )

    prompt_final = prompt_atalho or prompt_digitado
    if prompt_final and st.session_state.hitl_pendente is None:
        st.session_state.messages.append({"role": "user", "content": prompt_final})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt_final)
            with st.status("Processando diagnóstico...", expanded=True) as status_box:
                for passo_msg in executar_agente_ui(prompt_final):
                    st.write(passo_msg)
                status_box.update(label="Processamento concluído!", state="complete", expanded=False)
        st.rerun()

```
