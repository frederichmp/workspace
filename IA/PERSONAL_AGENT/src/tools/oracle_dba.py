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
