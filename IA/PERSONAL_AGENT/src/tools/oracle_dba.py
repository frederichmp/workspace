"""
Módulo de conexão e diagnóstico Oracle Database em Modo Thin.
Aplica isolamento estrito de credenciais via variáveis de ambiente (.env),
papéis segregados (ORACLE_USER_DIAG para leitura/diagnóstico e ORACLE_USER_KILL para intervenção via PKG_OPS_KILL),
pré-validação rápida de rede/VPN (Socket TCP), Edge Filtering e trilha de auditoria HITL.
"""
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import socket
import time
from typing import Any, Dict, List, Optional, Tuple

import oracledb
from dotenv import load_dotenv

from .notificador import enviar_alerta_email

# Carrega as variáveis de ambiente do arquivo .env na raiz de IA/PERSONAL_AGENT
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")

logger = logging.getLogger(__name__)

# Decisões humanas possíveis sobre uma intervenção de kill
DECISOES_KILL: Tuple[str, ...] = ("APROVADO", "REJEITADO", "TIMEOUT")

# Resultados de PKG_OPS_KILL que significam execução efetiva do encerramento
RESULTADOS_KILL_EXECUTADO: Tuple[str, ...] = ("ENCERRADA", "MARCADA_PARA_KILL")

# Campos que identificam a sessão alvo; únicos campos cobertos pelo hash de aprovação
CAMPOS_IDENTIDADE_ALVO: Tuple[str, ...] = ("inst_id", "sid", "serial#", "username", "program", "machine")

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


def _inteiro_positivo(valor: Any) -> Optional[int]:
    """
    Converte valor em inteiro estritamente positivo, ou None se inválido.
    Aceita apenas int (bool excluído) ou string só de dígitos; ausente (None), float,
    texto e valores <= 0 são inválidos. Nunca assume valor padrão.
    """
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        numero = valor
    elif isinstance(valor, str) and re.fullmatch(r"\s*\d+\s*", valor):
        numero = int(valor)
    else:
        return None
    return numero if numero > 0 else None


def validar_parametros_kill(
    inst_id: Any, sid: Any, serial: Any
) -> Optional[Tuple[int, int, int]]:
    """
    Valida inst_id, sid e serial (todos obrigatórios, inteiros positivos) antes de qualquer
    consulta ou conexão. Retorna (inst_id, sid, serial) ou None -> PARAM_INVALIDO.
    """
    valores = (_inteiro_positivo(inst_id), _inteiro_positivo(sid), _inteiro_positivo(serial))
    if any(v is None for v in valores):
        return None
    return valores  # type: ignore[return-value]


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
    # 1. Validação local antes de qualquer conexão: inteiros positivos, todos obrigatórios
    validados = validar_parametros_kill(inst_id, sid, serial)
    if validados is None:
        return {
            "encontrado": False,
            "elegivel": False,
            "motivo": "PARAM_INVALIDO",
            "mensagem": (
                f"Parâmetros inválidos: inst_id={inst_id}, sid={sid}, serial={serial}. "
                "Todos são obrigatórios e devem ser inteiros positivos."
            ),
        }
    inst_id_int, sid_int, serial_int = validados

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


def matar_sessao_oracle(sid: int, serial: int, inst_id: Optional[int] = None) -> str:
    """
    Executa o procedimento homologado de encerramento de sessão via conta segregada ORACLE_USER_KILL.
    Chama OPS_OWNER.PKG_OPS_KILL.KILL_SESSION com binds nomeados (p_inst_id, p_sid, p_serial, p_status).
    NÃO executa comando de sessão direto no Python.
    inst_id é obrigatório: não há instância padrão. Ausente (None) ou não inteiro positivo
    retorna PARAM_INVALIDO antes de qualquer consulta ou conexão.
    """
    # 1. Validação local antes de qualquer conexão: inteiros positivos, todos obrigatórios
    validados = validar_parametros_kill(inst_id, sid, serial)
    if validados is None:
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "PARAM_INVALIDO",
                "status_banco": "PARAM_INVALIDO",
                "mensagem": (
                    f"Parâmetros inválidos para encerramento de sessão: inst_id={inst_id}, sid={sid}, serial={serial}. "
                    "inst_id, sid e serial são obrigatórios e devem ser inteiros estritamente positivos (> 0)."
                ),
            },
            ensure_ascii=False,
        )
    inst_id_int, sid_int, serial_int = validados

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

def _normalizar_valor_identidade(valor: Any) -> Any:
    """Normaliza tipos numéricos vindos do driver para que o hash não dependa do tipo Python."""
    if valor is None or isinstance(valor, (bool, str)):
        return valor
    if isinstance(valor, int):
        return valor
    try:
        numero = float(valor)
        if numero.is_integer():
            return int(numero)
    except (TypeError, ValueError):
        pass
    return str(valor)


def extrair_identidade_alvo(alvo: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Retorna somente os campos de identidade da sessão (CAMPOS_IDENTIDADE_ALVO)."""
    alvo = alvo or {}
    return {campo: _normalizar_valor_identidade(alvo.get(campo)) for campo in CAMPOS_IDENTIDADE_ALVO}


def calcular_hash_identidade(alvo: Optional[Dict[str, Any]]) -> str:
    """
    Hash SHA-256 canônico calculado apenas sobre os campos de identidade:
    inst_id, sid, serial#, username, program, machine.
    timestamp, status, event e sql_id ficam de fora, pois variam sem que o alvo mude.
    """
    identidade = extrair_identidade_alvo(alvo)
    canonico = json.dumps(identidade, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def gerar_payload_e_hash_aprovacao(
    ferramenta: str,
    parametros: Dict[str, Any],
    alvo: Dict[str, Any],
    timestamp: str,
) -> Tuple[Dict[str, Any], str]:
    """
    Gera o payload exibido ao aprovador e o hash SHA-256 de identidade do alvo.
    O hash cobre apenas CAMPOS_IDENTIDADE_ALVO (ver calcular_hash_identidade);
    ferramenta, parametros e timestamp acompanham o payload para registro, mas não entram no hash.
    O mesmo hash é recalculado por executar_kill_verificado antes da chamada à conta KILL.
    """
    payload: Dict[str, Any] = {
        "ferramenta": ferramenta,
        "parametros": {k: parametros[k] for k in sorted(parametros.keys())},
        "identidade_alvo": extrair_identidade_alvo(alvo),
        "timestamp": timestamp,
    }
    return payload, calcular_hash_identidade(alvo)


def executar_kill_verificado(inst_id: Any, sid: Any, serial: Any, hash_aprovado: str) -> str:
    """
    Verificação de integridade imediatamente antes do encerramento:
      1. reconsulta o alvo pela conta DIAG (consultar_alvo_sessao_diag);
      2. recalcula o hash de identidade e compara com o hash aprovado;
      3. só então chama matar_sessao_oracle (conta KILL).
    Hash divergente -> ALVO_ALTERADO, sem chamada à conta KILL, com registro no log.
    Falha na reconsulta (alvo sumiu, erro de rede/config) -> o motivo da reconsulta, sem chamada à conta KILL.
    """
    reconsulta = consultar_alvo_sessao_diag(inst_id=inst_id, sid=sid, serial=serial)

    if not reconsulta.get("encontrado"):
        motivo = reconsulta.get("motivo", "ALVO_NAO_ENCONTRADO")
        logger.warning(
            f"KILL BLOQUEADO NA RECONSULTA: {motivo} | inst_id={inst_id}, sid={sid}, serial={serial} | "
            f"hash_aprovado={hash_aprovado}"
        )
        return json.dumps(
            {
                "status": "recusado",
                "motivo": motivo,
                "status_banco": motivo,
                "mensagem": (
                    "Reconsulta do alvo antes da execução falhou; nenhuma chamada à conta KILL. "
                    f"{reconsulta.get('mensagem', '')}"
                ).strip(),
            },
            ensure_ascii=False,
        )

    hash_atual = calcular_hash_identidade(reconsulta.get("alvo"))
    if hash_atual != hash_aprovado:
        logger.warning(
            f"KILL BLOQUEADO: ALVO_ALTERADO | inst_id={inst_id}, sid={sid}, serial={serial} | "
            f"hash_aprovado={hash_aprovado} | hash_atual={hash_atual}"
        )
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "ALVO_ALTERADO",
                "status_banco": "ALVO_ALTERADO",
                "hash_aprovado": hash_aprovado,
                "hash_atual": hash_atual,
                "mensagem": (
                    "A identidade da sessão mudou entre a aprovação e a execução. "
                    "Encerramento cancelado sem chamada à conta KILL."
                ),
            },
            ensure_ascii=False,
        )

    if not reconsulta.get("elegivel"):
        motivo = reconsulta.get("motivo", "NAO_ELEGIVEL")
        logger.warning(
            f"KILL BLOQUEADO NA RECONSULTA: {motivo} | inst_id={inst_id}, sid={sid}, serial={serial}"
        )
        return json.dumps(
            {
                "status": "recusado",
                "motivo": motivo,
                "status_banco": motivo,
                "mensagem": reconsulta.get("mensagem", "Alvo não elegível na reconsulta."),
            },
            ensure_ascii=False,
        )

    return matar_sessao_oracle(sid=sid, serial=serial, inst_id=inst_id)


def registrar_log_aprovacao_kill(
    aprovador: str,
    decisao: str,
    hash_payload: str,
    parametros: Dict[str, Any],
    alvo: Optional[Dict[str, Any]] = None,
    resultado_banco: Optional[str] = None,
    motivo: Optional[str] = None,
    caminho_log: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Registra formalmente a decisão de aprovação no arquivo de log da aplicação.

    Campos separados:
      - decisao: decisão humana (APROVADO | REJEITADO | TIMEOUT);
      - resultado_banco: status devolvido pela execução (p_status de PKG_OPS_KILL ou
        recusa local anterior à chamada); None quando nada foi executado;
      - motivo: justificativa de decisões não aprovadas (ex.: SEM_IDENTIFICACAO).
    NUNCA armazena senhas, tokens ou dados sensíveis.
    """
    if decisao not in DECISOES_KILL:
        raise ValueError(f"Decisão inválida: {decisao!r}. Esperado um de {DECISOES_KILL}.")

    if caminho_log is None:
        caminho_log = ROOT_DIR / "data" / "logs" / "kill_approval.log"

    caminho_log.parent.mkdir(parents=True, exist_ok=True)

    registro = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aprovador": aprovador,
        "decisao": decisao,
        "resultado_banco": resultado_banco,
        "motivo": motivo,
        "hash_payload": hash_payload,
        "parametros": parametros,
        "alvo": alvo or {},
    }

    with open(caminho_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")

    return registro


def montar_notificacao_kill(
    aprovador: str,
    inst_id: int,
    sid: int,
    serial: int,
    resultado_banco: str,
    hash_payload: str,
    canal: str,
) -> Tuple[str, str]:
    """
    Monta assunto e corpo do e-mail de uma intervenção aprovada.
    O assunto "Intervenção Aprovada" só é usado quando resultado_banco indica execução
    efetiva (ENCERRADA ou MARCADA_PARA_KILL); qualquer outro resultado gera
    "Intervenção NÃO executada", informando o status.
    """
    if resultado_banco in RESULTADOS_KILL_EXECUTADO:
        assunto = (
            f"[AGENTE DBA] Intervenção Aprovada por {aprovador}: "
            f"Kill Session {sid},{serial}"
        )
        corpo = (
            f"O encerramento da sessão SID={sid}, SERIAL={serial}, INST_ID={inst_id} "
            f"foi aprovado por {aprovador} ({canal}) e executado.\n"
            f"Resultado do banco: {resultado_banco}\n"
            f"Hash SHA-256 de identidade do alvo: {hash_payload}"
        )
    else:
        assunto = (
            f"[AGENTE DBA] Intervenção NÃO executada: Kill Session {sid},{serial} "
            f"(status {resultado_banco})"
        )
        corpo = (
            f"O encerramento da sessão SID={sid}, SERIAL={serial}, INST_ID={inst_id} "
            f"foi aprovado por {aprovador} ({canal}), mas NÃO foi executado.\n"
            f"Status retornado: {resultado_banco}\n"
            f"Hash SHA-256 de identidade do alvo: {hash_payload}"
        )
    return assunto, corpo


def registrar_decisao_kill(
    decisao: str,
    aprovador: str,
    inst_id: int,
    sid: int,
    serial: int,
    alvo: Dict[str, Any],
    hash_aprovado: str,
    canal: str,
    motivo: Optional[str] = None,
    caminho_log: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Aplica a decisão humana sobre uma intervenção já preparada (alvo elegível e hash exibido).

    - APROVADO com aprovador identificado: executa o encerramento, grava decisao e
      resultado_banco separados e envia e-mail conforme o resultado efetivo.
    - APROVADO sem aprovador: convertido em REJEITADO (motivo SEM_IDENTIFICACAO), sem execução.
    - REJEITADO / TIMEOUT: grava a decisão sem execução e sem e-mail.

    Retorna dict com decisao, resultado_banco, executado, motivo, resultado_tool (JSON para o LLM),
    registro gravado e dados da notificação.
    """
    if decisao not in DECISOES_KILL:
        raise ValueError(f"Decisão inválida: {decisao!r}. Esperado um de {DECISOES_KILL}.")

    parametros = {"inst_id": inst_id, "sid": sid, "serial": serial}
    aprovador_limpo = (aprovador or "").strip()

    if decisao == "APROVADO" and not aprovador_limpo:
        decisao = "REJEITADO"
        motivo = "SEM_IDENTIFICACAO"

    if decisao != "APROVADO":
        if motivo is None:
            motivo = "TIMEOUT_APROVACAO" if decisao == "TIMEOUT" else "REJEITADO_PELO_APROVADOR"
        aprovador_registro = aprovador_limpo or "NAO_INFORMADO"
        registro = registrar_log_aprovacao_kill(
            aprovador=aprovador_registro,
            decisao=decisao,
            hash_payload=hash_aprovado,
            parametros=parametros,
            alvo=alvo,
            resultado_banco=None,
            motivo=motivo,
            caminho_log=caminho_log,
        )
        logger.warning(
            f"AUDITORIA HITL: {decisao} ({motivo}) por {aprovador_registro} ({canal}) | "
            f"inst_id={inst_id}, sid={sid}, serial={serial} | Hash={hash_aprovado}"
        )
        resultado_tool = json.dumps(
            {
                "status": "abortado",
                "decisao": decisao,
                "motivo": motivo,
                "resultado_banco": None,
                "executado": False,
                "mensagem": (
                    f"Intervenção não aprovada ({decisao}/{motivo}) por '{aprovador_registro}'. "
                    "Nenhuma chamada à conta KILL foi feita."
                ),
            },
            ensure_ascii=False,
        )
        return {
            "decisao": decisao,
            "resultado_banco": None,
            "executado": False,
            "motivo": motivo,
            "resultado_tool": resultado_tool,
            "registro": registro,
            "assunto_email": None,
            "email_enviado": None,
            "email_detalhe": None,
        }

    # Decisão APROVADO com aprovador identificado: reconsulta + verificação de hash antes da conta KILL
    resultado_exec = executar_kill_verificado(
        inst_id=inst_id, sid=sid, serial=serial, hash_aprovado=hash_aprovado
    )
    try:
        dados_exec = json.loads(resultado_exec)
    except (TypeError, ValueError):
        dados_exec = {"status": "erro", "mensagem": str(resultado_exec)}
    resultado_banco = str(dados_exec.get("status_banco") or dados_exec.get("motivo") or "DESCONHECIDO")
    executado = resultado_banco in RESULTADOS_KILL_EXECUTADO

    registro = registrar_log_aprovacao_kill(
        aprovador=aprovador_limpo,
        decisao="APROVADO",
        hash_payload=hash_aprovado,
        parametros=parametros,
        alvo=alvo,
        resultado_banco=resultado_banco,
        motivo=None,
        caminho_log=caminho_log,
    )
    nivel_log = logging.INFO if executado else logging.WARNING
    logger.log(
        nivel_log,
        f"AUDITORIA HITL: APROVADO por {aprovador_limpo} ({canal}) | "
        f"inst_id={inst_id}, sid={sid}, serial={serial} | Hash={hash_aprovado} | "
        f"resultado_banco={resultado_banco} | executado={executado}",
    )

    assunto, corpo = montar_notificacao_kill(
        aprovador=aprovador_limpo,
        inst_id=inst_id,
        sid=sid,
        serial=serial,
        resultado_banco=resultado_banco,
        hash_payload=hash_aprovado,
        canal=canal,
    )
    email_enviado, email_detalhe = enviar_alerta_email(assunto, corpo)
    logger.info(f"NOTIFICAÇÃO SMTP: Sucesso={email_enviado} | Assunto={assunto} | Detalhe: {email_detalhe}")

    dados_exec["decisao"] = "APROVADO"
    dados_exec["resultado_banco"] = resultado_banco
    dados_exec["executado"] = executado
    resultado_tool = json.dumps(dados_exec, ensure_ascii=False, default=str)

    return {
        "decisao": "APROVADO",
        "resultado_banco": resultado_banco,
        "executado": executado,
        "motivo": None,
        "resultado_tool": resultado_tool,
        "registro": registro,
        "assunto_email": assunto,
        "email_enviado": email_enviado,
        "email_detalhe": email_detalhe,
    }


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
                        "description": (
                            "O INST_ID da instância Oracle onde a sessão está (obrigatório, sem valor padrão). "
                            "Use o inst_id retornado por coletar_sessoes_ativas."
                        ),
                    },
                },
                "required": ["inst_id", "sid", "serial"],
            },
        },
    },
]
