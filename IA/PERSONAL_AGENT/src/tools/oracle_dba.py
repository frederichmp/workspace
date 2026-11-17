"""
Módulo de conexão e diagnóstico Oracle Database em Modo Thin.
Aplica isolamento estrito de credenciais via variáveis de ambiente (.env),
papéis segregados (ORACLE_USER_DIAG para leitura/diagnóstico e ORACLE_USER_KILL para intervenção via PKG_OPS_KILL),
pré-validação rápida de rede/VPN (Socket TCP), Edge Filtering e trilha de auditoria HITL.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import time
from typing import Any, Dict, List, Optional, Tuple

import oracledb
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env na raiz de IA/PERSONAL_AGENT
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

# Usuários que nunca podem ser alvo de encerramento.
# Fonte única no Python; deve permanecer idêntica a c_protegidos em
# OPS_OWNER.PKG_OPS_KILL (db/ops_kill.sql): ',SYS,SYSTEM,DBSNMP,SYSMAN,OUTLN,STARTUPADMIN,OPS_OWNER,'
USUARIOS_PROTEGIDOS: Tuple[str, ...] = (
    "SYS",
    "SYSTEM",
    "DBSNMP",
    "SYSMAN",
    "OUTLN",
    "STARTUPADMIN",
    "OPS_OWNER",
)


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
    2. Conecta ao banco de dados Oracle em modo Thin utilizando as credenciais segregadas de diagnóstico (ORACLE_USER_DIAG).
    3. Contabiliza o total de sessões ativas e lista detalhes com campos completos:
       inst_id, sid, serial#, username, program, machine, status, sql_id, event.
    """
    user = os.getenv("ORACLE_USER_DIAG")
    password = os.getenv("ORACLE_PASSWORD_DIAG")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user, password, dsn]):
        return json.dumps(
            {
                "status": "erro",
                "motivo": "ERRO_CONFIG",
                "instancia": dsn or "NAO_CONFIGURADO",
                "mensagem": (
                    "Configuração incompleta no cofre (.env). "
                    "Variáveis ORACLE_USER_DIAG, ORACLE_PASSWORD_DIAG e ORACLE_DSN são obrigatórias."
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
                "motivo": "HostInacessivelVPN",
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
        # 2. Conexão em modo Thin nativo do python-oracledb via conta de diagnóstico
        connection = oracledb.connect(
            user=user,
            password=password,
            dsn=dsn,
        )
        cursor = connection.cursor()

        query_count = """
            SELECT COUNT(*)
            FROM GV$SESSION
            WHERE status = 'ACTIVE'
              AND type = 'USER'
        """
        cursor.execute(query_count)
        row = cursor.fetchone()
        total_ativas = int(row[0]) if row else 0

        # Busca sessões de usuário com todos os campos especificados
        query_top_sessoes = """
            SELECT inst_id,
                   sid,
                   serial# AS "serial#",
                   serial# AS serial,
                   NVL(username, 'BACKGROUND') AS username,
                   program,
                   machine,
                   status,
                   sql_id,
                   event
            FROM GV$SESSION
            WHERE type = 'USER'
              AND sid <> SYS_CONTEXT('USERENV', 'SID')
            ORDER BY CASE WHEN status = 'ACTIVE' THEN 0 ELSE 1 END,
                     seconds_in_wait DESC
            FETCH FIRST 10 ROWS ONLY
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
                "motivo": "OracleError",
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
                "motivo": type(exc).__name__,
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
    Utiliza exclusivamente a conta segregada ORACLE_USER_DIAG.
    """
    user = os.getenv("ORACLE_USER_DIAG")
    password = os.getenv("ORACLE_PASSWORD_DIAG")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user, password, dsn]):
        return json.dumps(
            {
                "status": "erro",
                "motivo": "ERRO_CONFIG",
                "instancia": dsn or "NAO_CONFIGURADO",
                "mensagem": (
                    "Configuração incompleta no cofre (.env). "
                    "Variáveis ORACLE_USER_DIAG, ORACLE_PASSWORD_DIAG e ORACLE_DSN são obrigatórias."
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
                "motivo": "HostInacessivelVPN",
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
                "motivo": type(exc).__name__,
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
    """
    Extrai o plano de execução real de um SQL_ID via DBMS_XPLAN.
    Valida rigorosamente o formato de sql_id com ^[a-z0-9]{13}$ antes de qualquer conexão.
    Utiliza exclusivamente a conta segregada ORACLE_USER_DIAG.
    """
    # Validação estrita de sql_id antes de qualquer conexão de rede ou banco
    sql_id_str = str(sql_id).strip() if sql_id is not None else ""
    if not re.match(r"^[a-z0-9]{13}$", sql_id_str):
        return json.dumps(
            {
                "status": "erro",
                "motivo": "SQL_ID_INVALIDO",
                "sql_id": sql_id,
                "mensagem": (
                    f"Formato inválido de sql_id: '{sql_id}'. "
                    "O sql_id deve conter exatamente 13 caracteres alfanuméricos minúsculos (^[a-z0-9]{13}$)."
                ),
            },
            ensure_ascii=False,
        )

    user = os.getenv("ORACLE_USER_DIAG")
    password = os.getenv("ORACLE_PASSWORD_DIAG")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user, password, dsn]):
        return json.dumps(
            {
                "status": "erro",
                "motivo": "ERRO_CONFIG",
                "instancia": dsn or "NAO_CONFIGURADO",
                "mensagem": (
                    "Configuração incompleta no cofre (.env). "
                    "Variáveis ORACLE_USER_DIAG, ORACLE_PASSWORD_DIAG e ORACLE_DSN são obrigatórias."
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
                "motivo": "HostInacessivelVPN",
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
        cursor.execute(query, sql_id=sql_id_str)

        linhas_plano = []
        for row in cursor.fetchall():
            linha = row[0].strip() if row[0] else ""
            if linha:
                linhas_plano.append(linha)

        # Filtro na Borda: Proteção contra planos gigantes
        plano_truncado = False
        if len(linhas_plano) > 40:
            linhas_plano = linhas_plano[:40]
            linhas_plano.append("... [PLANO TRUNCADO PARA PROTEGER CONTEXTO DA IA] ...")
            plano_truncado = True

        return json.dumps(
            {
                "status": "sucesso",
                "sql_id": sql_id_str,
                "plano_execucao": "\n".join(linhas_plano),
                "truncado": plano_truncado,
            },
            ensure_ascii=False,
        )

    except Exception as exc:
        return json.dumps(
            {
                "status": "erro",
                "motivo": type(exc).__name__,
                "sql_id": sql_id_str,
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


def consultar_alvo_sessao_diag(
    inst_id: int, sid: int, serial: int
) -> Dict[str, Any]:
    """
    Consulta os metadados da sessão na GV$SESSION utilizando a conta ORACLE_USER_DIAG.
    Retorna os campos: inst_id, sid, serial#, username, program, machine, status, sql_id, event, type.

    Elegibilidade (mesma ordem de checagem de PKG_OPS_KILL):
      - sessão inexistente            -> encontrado=False, motivo ALVO_NAO_ENCONTRADO;
      - TYPE <> 'USER'                -> encontrado=True, elegivel=False, motivo NAO_USUARIO;
      - username nulo ou protegido    -> encontrado=True, elegivel=False, motivo USUARIO_PROTEGIDO;
      - caso contrário                -> encontrado=True, elegivel=True.
    Somente alvos elegíveis podem seguir para a solicitação de aprovação.
    """
    # 1. Validação local antes de qualquer conexão: inteiros positivos
    try:
        inst_id_int = int(inst_id)
        sid_int = int(sid)
        serial_int = int(serial)
        if inst_id_int <= 0 or sid_int <= 0 or serial_int <= 0:
            return {
                "encontrado": False,
                "motivo": "PARAM_INVALIDO",
                "mensagem": (
                    f"Parâmetros inválidos: inst_id={inst_id}, sid={sid}, serial={serial}. "
                    "Devem ser inteiros positivos."
                ),
            }
    except (ValueError, TypeError):
        return {
            "encontrado": False,
            "motivo": "PARAM_INVALIDO",
            "mensagem": (
                f"Parâmetros inválidos: inst_id={inst_id}, sid={sid}, serial={serial}. "
                "Devem ser números inteiros."
            ),
        }

    # 2. Credenciais de diagnóstico
    user = os.getenv("ORACLE_USER_DIAG")
    password = os.getenv("ORACLE_PASSWORD_DIAG")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user, password, dsn]):
        return {
            "encontrado": False,
            "motivo": "ERRO_CONFIG",
            "mensagem": (
                "Configuração incompleta no cofre (.env). "
                "Variáveis ORACLE_USER_DIAG, ORACLE_PASSWORD_DIAG e ORACLE_DSN são obrigatórias."
            ),
        }

    # 3. Pré-validação rápida de rede
    check_rede = verificar_acessibilidade_host(dsn, timeout=3.0)
    if not check_rede["acessivel"]:
        return {
            "encontrado": False,
            "motivo": "HostInacessivelVPN",
            "mensagem": f"Host {check_rede['host']}:{check_rede['porta']} inacessível.",
        }

    connection: Optional[oracledb.Connection] = None
    cursor: Optional[oracledb.Cursor] = None

    try:
        connection = oracledb.connect(user=user, password=password, dsn=dsn)
        cursor = connection.cursor()

        query = """
            SELECT inst_id,
                   sid,
                   serial# AS "serial#",
                   username,
                   program,
                   machine,
                   status,
                   sql_id,
                   event,
                   type
            FROM GV$SESSION
            WHERE inst_id = :p_inst_id
              AND sid = :p_sid
              AND serial# = :p_serial
        """
        cursor.execute(
            query,
            p_inst_id=inst_id_int,
            p_sid=sid_int,
            p_serial=serial_int,
        )
        row = cursor.fetchone()

        if not row:
            return {
                "encontrado": False,
                "motivo": "ALVO_NAO_ENCONTRADO",
                "mensagem": (
                    f"Sessão inst_id={inst_id_int}, sid={sid_int}, serial={serial_int} "
                    "não encontrada na GV$SESSION."
                ),
            }

        colunas = [col[0].lower() for col in cursor.description]
        dados_alvo: Dict[str, Any] = {}
        for col, val in zip(colunas, row):
            dados_alvo[col] = val
        dados_alvo["serial#"] = row[2]  # preserva chave explícita serial#

        tipo_sessao = str(dados_alvo.get("type") or "").upper()
        username = dados_alvo.get("username")

        if tipo_sessao != "USER":
            return {
                "encontrado": True,
                "elegivel": False,
                "motivo": "NAO_USUARIO",
                "alvo": dados_alvo,
                "mensagem": (
                    f"Sessão inst_id={inst_id_int}, sid={sid_int}, serial={serial_int} "
                    f"não é de usuário (TYPE={tipo_sessao or 'NULO'}). Encerramento não permitido."
                ),
            }

        if not username or str(username).upper() in USUARIOS_PROTEGIDOS:
            return {
                "encontrado": True,
                "elegivel": False,
                "motivo": "USUARIO_PROTEGIDO",
                "alvo": dados_alvo,
                "mensagem": (
                    f"Sessão inst_id={inst_id_int}, sid={sid_int}, serial={serial_int} "
                    f"pertence a usuário protegido ({username or 'NULO'}). Encerramento não permitido."
                ),
            }

        return {
            "encontrado": True,
            "elegivel": True,
            "alvo": dados_alvo,
        }
    except oracledb.Error as db_err:
        return {
            "encontrado": False,
            "motivo": "ERRO_ORACLE",
            "mensagem": str(db_err),
        }
    except Exception as exc:
        return {
            "encontrado": False,
            "motivo": type(exc).__name__,
            "mensagem": str(exc),
        }
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


def matar_sessao_oracle(sid: int, serial: int, inst_id: int = 1) -> str:
    """
    Executa o procedimento homologado de encerramento de sessão via conta segregada ORACLE_USER_KILL.
    Chama OPS_OWNER.PKG_OPS_KILL.KILL_SESSION com binds nomeados (p_inst_id, p_sid, p_serial, p_status).
    NÃO executa comando de sessão direto no Python.
    Aplica validação local de inteiros positivos antes de qualquer conexão.
    """
    # 1. Validação local antes de qualquer conexão: inteiros positivos
    try:
        inst_id_int = int(inst_id)
        sid_int = int(sid)
        serial_int = int(serial)
        if inst_id_int <= 0 or sid_int <= 0 or serial_int <= 0:
            return json.dumps(
                {
                    "status": "recusado",
                    "motivo": "PARAM_INVALIDO",
                    "status_banco": "PARAM_INVALIDO",
                    "mensagem": (
                        f"Parâmetros inválidos para encerramento de sessão: inst_id={inst_id}, sid={sid}, serial={serial}. "
                        "Devem ser números inteiros estritamente positivos (> 0)."
                    ),
                },
                ensure_ascii=False,
            )
    except (ValueError, TypeError):
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "PARAM_INVALIDO",
                "status_banco": "PARAM_INVALIDO",
                "mensagem": (
                    f"Parâmetros inválidos para encerramento de sessão: inst_id={inst_id}, sid={sid}, serial={serial}. "
                    "Devem ser números inteiros."
                ),
            },
            ensure_ascii=False,
        )

    # 2. Verificação de credenciais segregadas da conta KILL
    user = os.getenv("ORACLE_USER_KILL")
    password = os.getenv("ORACLE_PASSWORD_KILL")
    dsn = os.getenv("ORACLE_DSN")

    if not all([user, password, dsn]):
        return json.dumps(
            {
                "status": "erro",
                "motivo": "ERRO_CONFIG",
                "instancia": dsn or "NAO_CONFIGURADO",
                "mensagem": (
                    "Configuração incompleta no cofre (.env). "
                    "Variáveis ORACLE_USER_KILL, ORACLE_PASSWORD_KILL e ORACLE_DSN são obrigatórias."
                ),
            },
            ensure_ascii=False,
        )

    # 3. Pré-validação rápida de rede / VPN
    check_rede = verificar_acessibilidade_host(dsn, timeout=3.0)
    if not check_rede["acessivel"]:
        return json.dumps(
            {
                "status": "erro",
                "motivo": "HostInacessivelVPN",
                "instancia": dsn,
                "host_acessivel": False,
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

        # Execução com binds nomeados conforme contrato de segurança da PKG_OPS_KILL
        status_var = cursor.var(oracledb.DB_TYPE_VARCHAR, size=128)
        cursor.execute(
            """
            BEGIN
                OPS_OWNER.PKG_OPS_KILL.KILL_SESSION(
                    p_inst_id => :p_inst_id,
                    p_sid     => :p_sid,
                    p_serial  => :p_serial,
                    p_status  => :p_status
                );
            END;
            """,
            p_inst_id=inst_id_int,
            p_sid=sid_int,
            p_serial=serial_int,
            p_status=status_var,
        )
        status_banco = str(status_var.getvalue() or "").strip()

        return json.dumps(
            {
                "status": status_banco,
                "motivo": status_banco,
                "status_banco": status_banco,
                "inst_id": inst_id_int,
                "sid": sid_int,
                "serial": serial_int,
                "mensagem": (
                    f"Procedimento OPS_OWNER.PKG_OPS_KILL.KILL_SESSION executado para "
                    f"inst_id={inst_id_int}, sid={sid_int}, serial={serial_int}. "
                    f"Status retornado pelo banco: {status_banco}."
                ),
            },
            ensure_ascii=False,
        )

    except oracledb.Error as db_err:
        return json.dumps(
            {
                "status": "erro",
                "motivo": "ERRO_ORACLE",
                "status_banco": "ERRO_ORACLE",
                "instancia": dsn,
                "sid": sid_int,
                "serial": serial_int,
                "tipo_erro": "OracleError",
                "mensagem": str(db_err),
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps(
            {
                "status": "erro",
                "motivo": type(exc).__name__,
                "instancia": dsn,
                "sid": sid_int,
                "serial": serial_int,
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


# ------------------------------------------------------------------------------
# TRILHA DE AUDITORIA HITL E GERAÇÃO DE HASH CANÔNICO
# ------------------------------------------------------------------------------

def gerar_payload_e_hash_aprovacao(
    ferramenta: str,
    parametros: Dict[str, Any],
    alvo: Dict[str, Any],
    timestamp: str,
) -> Tuple[Dict[str, Any], str]:
    """
    Gera o payload canônico em JSON com chaves ordenadas e calcula o hash SHA-256
    exibido ao aprovador antes da intervenção.
    """
    payload: Dict[str, Any] = {
        "ferramenta": ferramenta,
        "parametros": {k: parametros[k] for k in sorted(parametros.keys())},
        "dados_alvo": {k: alvo[k] for k in sorted(alvo.keys())} if alvo else {},
        "timestamp": timestamp,
    }
    payload_canonico = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    hash_sha256 = hashlib.sha256(payload_canonico.encode("utf-8")).hexdigest()
    return payload, hash_sha256


def registrar_log_aprovacao_kill(
    aprovador: str,
    decisao: str,  # APROVADO | REJEITADO | TIMEOUT
    hash_payload: str,
    parametros: Dict[str, Any],
    alvo: Optional[Dict[str, Any]] = None,
    status_banco: Optional[str] = None,
    caminho_log: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Registra formalmente a decisão de aprovação no arquivo de log da aplicação.
    NUNCA armazena senhas, tokens ou dados sensíveis.
    """
    if caminho_log is None:
        caminho_log = ROOT_DIR / "data" / "logs" / "kill_approval.log"

    caminho_log.parent.mkdir(parents=True, exist_ok=True)

    registro = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aprovador": aprovador,
        "decisao": decisao,
        "hash_payload": hash_payload,
        "parametros": parametros,
        "alvo": alvo or {},
        "status_banco": status_banco,
    }

    with open(caminho_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    return registro


# Schema no padrão OpenAI Tool Calling para exportação ao Orquestrador
oracle_tools_schema: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "coletar_sessoes_ativas",
            "description": (
                "Valida a conectividade de rede/VPN com o servidor Oracle e, se acessível, "
                "conecta em modo Thin via ORACLE_USER_DIAG retornando as sessões de usuários ativas "
                "na GV$SESSION com campos inst_id, sid, serial#, username, program, machine, status, sql_id, event."
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
                "Obtém as instruções SQL (Top SQL) mais pesadas em execução no banco de dados Oracle via ORACLE_USER_DIAG, "
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
                "Obtém o plano de execução (DBMS_XPLAN) de um SQL_ID no banco Oracle via ORACLE_USER_DIAG. "
                "Requer sql_id válido contendo 13 caracteres alfanuméricos minúsculos."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql_id": {
                        "type": "string",
                        "description": "O identificador alfanumérico exato do SQL (ex: '2z0udr4rc402m').",
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
                "Encerra uma sessão de usuário no banco de dados através da procedure homologada "
                "OPS_OWNER.PKG_OPS_KILL.KILL_SESSION. Requer aprovação humana prévia (HITL)."
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
                    "inst_id": {
                        "type": "integer",
                        "description": "O ID da instância Oracle RAC (padrão: 1).",
                        "default": 1,
                    },
                },
                "required": ["sid", "serial"],
            },
        },
    },
]
