"""
Módulo de conexão e diagnóstico Oracle Database em Modo Thin.
Aplica isolamento estrito de credenciais via variáveis de ambiente (.env),
papéis segregados (ORACLE_USER_DIAG para leitura/diagnóstico e ORACLE_USER_KILL para intervenção via PKG_OPS_KILL),
pré-validação rápida de rede/VPN (Socket TCP), Edge Filtering e trilha de auditoria HITL.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import socket
import threading
import time
import types
import uuid
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import oracledb

from .notificador import enviar_alerta_email

if os.name == "nt":
    import msvcrt
else:
    import fcntl

# Diretório do log de aprovações de kill: AGENTDBA_LOG_DIR ou o padrão local, fora de pasta sincronizada,
# resolvido em tempo de chamada (_diretorio_log_aprovacao; A3: nada é congelado no import, então as cópias
# tools.* e src.tools.* resolvem o mesmo destino). A pasta só é criada na primeira gravação (os.makedirs,
# exist_ok); falha na criação = falha de registro. Nada é criado no import nem na resolução.
DIRETORIO_LOG_PADRAO = r"C:\AgentDBA\logs"

# Gancho de teste: None = destino resolvido em tempo de chamada; um Path aqui (monkeypatch) fixa o destino.
CAMINHO_LOG_APROVACAO_PADRAO: Optional[Path] = None

# Gravação do JSONL (docs/entregas/1.11/item1/decisao.md, seção a): ponto único, fsync,
# lock de processo (threads da Web) + lock de arquivo (CLI e Web em processos distintos).
FASES_REGISTRO_KILL: Tuple[str, ...] = ("INTENCAO", "RESULTADO")
# Evento próprio da recusa local antes do prompt HITL (A10; decisao_c1.md ponto 5). Fica FORA de
# FASES_REGISTRO_KILL: não é INTENCAO nem RESULTADO, e o reconciliador o ignora.
FASE_RECUSA_PRE_HITL = "RECUSA_PRE_HITL"
_REGEX_ID_INTERVENCAO = re.compile(r"[0-9a-f]{32}")
_LOCK_LOG_APROVACAO = threading.Lock()
_FSYNC_DIRETORIO = os.name == "posix"  # Windows: sem chamada sobre o diretório (decisão a2)
LOCK_LOG_TIMEOUT_SEGUNDOS = 5.0
_LOCK_LOG_INTERVALO_SEGUNDOS = 0.05

# Texto exigido pelo responsável para ERRO_ORACLE a partir do execute do KILL_SESSION (2026-11-17)
MENSAGEM_RESULTADO_DESCONHECIDO = "resultado desconhecido: conferir sessão"

# Desfecho fora da lista fechada (correcao/decisao_c1.md, pontos 2 e 4): texto comum a e-mail, CLI e Web.
MENSAGEM_DESFECHO_NAO_CONFIRMADO = "desfecho no banco não confirmado"
# R1 ampliada V6 (docs/entregas/1.11/r1_ampliada/decisao_c1.md §2.6): nenhum texto ao LLM nomeia o pacote.
MENSAGEM_RECUSA_PKG = "Encerramento NÃO executado: recusado pelo procedimento de encerramento (status {status})."
STATUS_PKG_VAZIO = "DESCONHECIDO"

# Reconciliador na subida
RESULTADO_NAO_CONCLUIDA = "NAO_CONCLUIDA"
MOTIVO_RECONCILIADO = "RECONCILIADO_NA_SUBIDA"


class LockLogAprovacaoIndisponivel(TimeoutError):
    """O lock de arquivo do log de aprovações não foi obtido dentro de LOCK_LOG_TIMEOUT_SEGUNDOS."""


logger = logging.getLogger(__name__)

# Decisões humanas possíveis sobre uma intervenção de kill
DECISOES_KILL: Tuple[str, ...] = ("APROVADO", "REJEITADO", "TIMEOUT")

# Validade da aprovação humana, contada a partir da preparação (exibição dos dados do alvo).
# Verificação passiva no momento da decisão: APROVADO fora de [0, TTL) vira TIMEOUT.
APROVACAO_TTL_SEGUNDOS = 300

# Reconciliador na subida: só INTENCAO sem RESULTADO mais antiga que TTL + 300 s vira NAO_CONCLUIDA,
# para não marcar uma intervenção ainda em curso em outro processo (CLI x Web).
RECONCILIACAO_IDADE_MINIMA_SEGUNDOS = APROVACAO_TTL_SEGUNDOS + 300

# Resultados de PKG_OPS_KILL que significam execução efetiva do encerramento
RESULTADOS_KILL_EXECUTADO: Tuple[str, ...] = ("ENCERRADA", "MARCADA_PARA_KILL")

# p_status do PKG_OPS_KILL v2 que provam que nenhuma sessão foi encerrada (ops_kill.sql:128-176; o
# ALVO_NAO_ENCONTRADO também vem do ORA-00030 no comando de encerramento do PKG, :193-194). Lista FECHADA: qualquer outro
# p_status (ERRO_ORACLE, vazio, nulo, código novo) é resultado desconhecido (decisao_c1.md, ponto 1).
RECUSAS_PKG_SEM_KILL: Tuple[str, ...] = (
    "PARAM_INVALIDO", "PROPRIA_SESSAO", "ALVO_NAO_ENCONTRADO",
    "ALVO_DIVERGENTE", "NAO_USUARIO", "USUARIO_PROTEGIDO",
)

# Identidade esperada enviada ao PKG_OPS_KILL v2 (1.11-V2 item 6; docs/entregas/1.11/v2_refeito/decisao.md D1).
CAMPOS_IDENTIDADE_ESPERADA: Tuple[str, ...] = ("username", "program", "machine", "logon_time")

# Campos que identificam a sessão alvo; únicos campos cobertos pelo hash de aprovação.
# Todo campo enviado ao PKG como identidade esperada está no hash (invariante com teste, L23).
CAMPOS_IDENTIDADE_ALVO: Tuple[str, ...] = ("inst_id", "sid", "serial#") + CAMPOS_IDENTIDADE_ESPERADA

# Limite local de tamanho (caracteres) dos textos de identidade. O PKG é a autoridade (128 bytes, LENGTHB);
# o limite local só barra defeito e nunca recusa alvo legítimo (decisao.md D1).
LIMITE_TEXTO_IDENTIDADE = 128

MENSAGEM_ALVO_DIVERGENTE = (
    "A identidade da sessão no banco diverge da aprovada (verificação do procedimento de encerramento). "
    "Encerramento NÃO executado. Campos e valores só em OPS_KILL_AUDIT."
)

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


# ---- R1 ampliada (docs/entregas/1.11/r1_ampliada/decisao_c1.md §1): saída de dados ao LLM ----
# O resultado_tool vai ao coordenador, que pode ser o Gemini em nuvem. Nele não vão DSN, host:porta, texto cru de
# exceção, usuário protegido, aprovador, nome do pacote nem hashes (V1-V7); o detalhe fica no log local.
# Com o coordenador em nuvem, as ferramentas Oracle não são oferecidas nem executadas (V8, falha fechada).

_REGEX_CODIGO_ERRO = re.compile(r"\b(?:ORA|DPY|DPI|TNS)-\d{4,5}\b")

TEXTO_HOST_INACESSIVEL = "Host do banco inacessível."
TEXTO_HOST_INACESSIVEL_VPN = (
    "Host do banco inacessível. Verifique se a VPN está conectada ou se há bloqueio de firewall."
)

RESULTADO_ORACLE_SO_LOCAL = json.dumps(
    {
        "status": "recusado",
        "motivo": "COORDENADOR_NUVEM",
        "mensagem": "Dados do banco só com o coordenador local. Nenhuma consulta foi feita.",
    },
    ensure_ascii=False,
)

TEXTO_HISTORICO_COM_DADO_DO_BANCO = (
    "O histórico desta conversa tem dados do banco e o coordenador ativo é em nuvem. "
    "Use 'Limpar Chat' ou religue o Ollama."
)

# Lista de permissão para o coordenador em nuvem (R1 ampliada fase 2, K2; fase2/decisao_c1.md §1 e plano 9.8.1):
# só LIBERADA_NUVEM libera. Toda ferramenta registrada (*_tools_schema de src/tools/*.py) tem entrada explícita; um
# teste AST falha se faltar ou sobrar nome. Na execução, nome ausente vale SO_LOCAL. Imutável (MappingProxyType) e
# sem importar rag_search nem gemini_router (langchain, chave do Gemini).
LIBERADA_NUVEM = "LIBERADA_NUVEM"
SO_LOCAL = "SO_LOCAL"
CLASSIFICACAO_FERRAMENTAS = types.MappingProxyType(
    {
        "coletar_metricas_hardware": LIBERADA_NUVEM,
        "verificar_espaco_disco": LIBERADA_NUVEM,
        "coletar_sessoes_ativas": SO_LOCAL,
        "coletar_top_sql": SO_LOCAL,
        "coletar_plano_execucao": SO_LOCAL,
        "matar_sessao_oracle": SO_LOCAL,
        "buscar_script_interno": SO_LOCAL,
        "analisar_log_complexo": SO_LOCAL,
    }
)


def ferramenta_liberada_nuvem(nome: Any) -> bool:
    """
    True só para nome (str) classificado LIBERADA_NUVEM em CLASSIFICACAO_FERRAMENTAS, lida em tempo de chamada.
    Ausente, outro valor (inclusive erro de digitação), outro tipo ou exceção: False (falha fechada). Nunca levanta.
    """
    try:
        return isinstance(nome, str) and CLASSIFICACAO_FERRAMENTAS.get(nome) == LIBERADA_NUVEM
    except Exception:
        return False

# R1 ampliada fase 2, K5 (fase2/decisao_c1.md §8.4; A3 e A4 da revisão adversarial): o coordenador local é um só
# destino, em IP literal (sem resolução de nome), o mesmo da sonda. "localhost" deixa de ser aceito.
HOST_COORDENADOR_LOCAL = "127.0.0.1"
PORTA_COORDENADOR_LOCAL = 11434
URL_COORDENADOR_LOCAL = f"http://{HOST_COORDENADOR_LOCAL}:{PORTA_COORDENADOR_LOCAL}/v1"
_HOSTS_COORDENADOR_LOCAL = frozenset({"127.0.0.1", "::1"})
_CAMINHOS_COORDENADOR_LOCAL = frozenset({"/v1", "/v1/"})


def criar_cliente_coordenador_local() -> Any:
    """
    Fábrica única do cliente do coordenador local (K5), usada por app.py e src/main.py: base_url em
    URL_COORDENADOR_LOCAL e cliente HTTP sem proxy de ambiente ou do sistema (trust_env=False) e sem seguir
    redirecionamento (follow_redirects=False). O openai é importado aqui (o módulo não depende dele no import, e o
    monkeypatch de openai.OpenAI dos testes continua valendo).
    """
    import openai

    return openai.OpenAI(
        base_url=URL_COORDENADOR_LOCAL,
        api_key="local",
        http_client=openai.DefaultHttpxClient(trust_env=False, follow_redirects=False),
    )


def _codigo_erro(exc: BaseException) -> str:
    """
    Só o código do erro para o LLM (V3): o 1º ORA-/DPY-/DPI-/TNS-NNNNN de um oracledb.Error; senão, ou para
    outra exceção, o nome do tipo. Nunca ecoa o texto do erro e nunca levanta (A3).
    """
    try:
        if isinstance(exc, oracledb.Error):
            achado = _REGEX_CODIGO_ERRO.search(_descrever_erro(exc))
            if achado:
                return achado.group(0)
        return type(exc).__name__
    except Exception:
        return "Exception"


def _registrar_erro_local(
    ferramenta: str,
    motivo: str,
    exc: Optional[BaseException] = None,
    rede: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Detalhe cru de um erro só no log local (auditoria_oracle.log), nunca no resultado_tool: o texto do erro
    e, quando há, host:porta e erro_rede da sonda. O DSN não é gravado. Nunca levanta.
    """
    try:
        partes = [f"DETALHE LOCAL (fora do LLM) | ferramenta={ferramenta} | motivo={motivo}"]
        if exc is not None:
            partes.append(f"erro={_descrever_erro(exc)}")
        if rede is not None:
            partes.append(f"host={rede.get('host')}:{rede.get('porta')} | erro_rede={rede.get('erro_rede')}")
        logger.warning(" | ".join(partes))
    except Exception:
        pass


def coordenador_e_local(client: Any) -> bool:
    """
    V8 (decisao_c1.md §3.1), estrito desde o K5 (fase2/decisao_c1.md §8.4): o coordenador é local só se o base_url
    do próprio cliente que envia é http, host 127.0.0.1 ou ::1 (hostname exato; "localhost" não), porta 11434, sem
    usuário nem senha, caminho /v1 e sem query nem fragmento. Não lê atributo privado do openai nem do httpx2 (o
    transporte sem proxy e sem redirect vem da fábrica). Sem atributo, exceção ou qualquer outra forma: False.
    """
    try:
        from urllib.parse import urlsplit

        partes = urlsplit(str(client.base_url))
        return (
            partes.scheme == "http"
            and partes.hostname in _HOSTS_COORDENADOR_LOCAL
            and partes.port == PORTA_COORDENADOR_LOCAL
            and "@" not in partes.netloc  # sem userinfo (usuário e/ou senha), inclusive "@" vazio
            and partes.path in _CAMINHOS_COORDENADOR_LOCAL
            and not partes.query
            and not partes.fragment
        )
    except Exception:
        return False


def historico_tem_dado_do_banco(mensagens: Any) -> bool:
    """
    V8, trava de histórico (decisao_c1.md §3.4; fase 2, K2): True se alguma mensagem role "tool" (fora a recusa fixa
    RESULTADO_ORACLE_SO_LOCAL) veio de ferramenta não liberada para a nuvem (ferramenta_liberada_nuvem). Lista de
    permissão: nome ausente ou desconhecido, RAG e recusa do kill contam como dado local. Entrada que não é lista: True.
    """
    try:
        if not isinstance(mensagens, (list, tuple)):
            return True
        for mensagem in mensagens:
            if not isinstance(mensagem, dict) or mensagem.get("role") != "tool":
                continue
            if mensagem.get("content") == RESULTADO_ORACLE_SO_LOCAL:
                continue
            if not ferramenta_liberada_nuvem(mensagem.get("name")):
                return True
        return False
    except Exception:
        return True


# ---- R1 ampliada, fase 2 (docs/entregas/1.11/r1_ampliada/fase2/decisao_c1.md §2): gate de produção do kill ----
NOME_FERRAMENTA_KILL = "matar_sessao_oracle"

RESULTADO_KILL_DESABILITADO = json.dumps(
    {
        "status": "recusado",
        "motivo": "KILL_DESABILITADO",
        "status_banco": "KILL_DESABILITADO",
        "resultado_desconhecido": False,
        "mensagem": "Encerramento de sessão indisponível nesta instalação. Nenhuma consulta nem conexão foi feita.",
    },
    ensure_ascii=False,
)


def kill_habilitado() -> bool:
    """
    Gate de produção do kill (decisao_c1.md §2.1): só o valor exato "2" de OPS_KILL_PKG_VERSAO (PKG_OPS_KILL v2
    instalado) habilita o encerramento. Lido a cada chamada, sem strip, sem cache e sem reler o .env; qualquer
    outro valor, ou a ausência, deixa o kill indisponível (falha fechada).
    """
    return os.environ.get("OPS_KILL_PKG_VERSAO") == "2"


def ferramentas_do_coordenador(schemas: Any, local: bool) -> List[Dict[str, Any]]:
    """
    Catálogo entregue ao LLM a cada chamada (decisao_c1.md §1.1 e §2.2-i). Pula a entrada malformada (falha
    fechada). Sem o gate, matar_sessao_oracle sai do catálogo, também com o coordenador local. Com o coordenador em
    nuvem, só ficam as ferramentas liberadas (ferramenta_liberada_nuvem; fase 2, K2): Oracle, RAG e nome sem
    classificação saem.
    """
    catalogo: List[Dict[str, Any]] = []
    for schema in schemas or []:
        try:
            nome = schema["function"]["name"]
        except Exception:
            continue
        if not isinstance(nome, str):
            continue
        if nome == NOME_FERRAMENTA_KILL and not kill_habilitado():
            continue
        if not local and not ferramenta_liberada_nuvem(nome):
            continue
        catalogo.append(schema)
    return catalogo


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
            # R1 ampliada (A2): só tipo e errno; o texto do erro de socket pode trazer o host.
            "erro_rede": f"{type(net_err).__name__} errno={getattr(net_err, 'errno', None)}",
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
        _registrar_erro_local("coletar_sessoes_ativas", "HostInacessivelVPN", rede=check_rede)
        return json.dumps(
            {
                "status": "erro",
                "motivo": "HostInacessivelVPN",
                "host_acessivel": False,
                "tipo_erro": "HostInacessivelVPN",
                "mensagem": TEXTO_HOST_INACESSIVEL_VPN,
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
                "host_acessivel": True,
                "latencia_rede_ms": check_rede["latencia_ms"],
                "sessoes_ativas": total_ativas,
                "sessoes_identificadas": sessoes_detalhe,
            },
            ensure_ascii=False,
        )

    except oracledb.Error as db_err:
        _registrar_erro_local("coletar_sessoes_ativas", "OracleError", exc=db_err)
        return json.dumps(
            {
                "status": "erro",
                "motivo": "OracleError",
                "host_acessivel": True,
                "tipo_erro": "OracleError",
                "codigo_erro": _codigo_erro(db_err),
                "mensagem": f"Erro do Oracle {_codigo_erro(db_err)}.",
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        _registrar_erro_local("coletar_sessoes_ativas", type(exc).__name__, exc=exc)
        return json.dumps(
            {
                "status": "erro",
                "motivo": type(exc).__name__,
                "host_acessivel": True,
                "tipo_erro": type(exc).__name__,
                "codigo_erro": _codigo_erro(exc),
                "mensagem": (
                    f"Erro do Oracle {_codigo_erro(exc)}." if isinstance(exc, oracledb.Error)
                    else f"Erro {type(exc).__name__}."
                ),
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
        _registrar_erro_local("coletar_top_sql", "HostInacessivelVPN", rede=check_rede)
        return json.dumps(
            {
                "status": "erro",
                "motivo": "HostInacessivelVPN",
                "host_acessivel": False,
                "tipo_erro": "HostInacessivelVPN",
                "mensagem": TEXTO_HOST_INACESSIVEL_VPN,
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
                "host_acessivel": True,
                "top_sql": top_sqls,
            },
            ensure_ascii=False,
        )

    except Exception as exc:
        _registrar_erro_local("coletar_top_sql", type(exc).__name__, exc=exc)
        return json.dumps(
            {
                "status": "erro",
                "motivo": type(exc).__name__,
                "codigo_erro": _codigo_erro(exc),
                "mensagem": (
                    f"Erro do Oracle {_codigo_erro(exc)}." if isinstance(exc, oracledb.Error)
                    else f"Erro {type(exc).__name__}."
                ),
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
        _registrar_erro_local("coletar_plano_execucao", "HostInacessivelVPN", rede=check_rede)
        return json.dumps(
            {
                "status": "erro",
                "motivo": "HostInacessivelVPN",
                "host_acessivel": False,
                "tipo_erro": "HostInacessivelVPN",
                "mensagem": TEXTO_HOST_INACESSIVEL_VPN,
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
        _registrar_erro_local("coletar_plano_execucao", type(exc).__name__, exc=exc)
        return json.dumps(
            {
                "status": "erro",
                "motivo": type(exc).__name__,
                "sql_id": sql_id_str,
                "codigo_erro": _codigo_erro(exc),
                "mensagem": (
                    f"Erro do Oracle {_codigo_erro(exc)}." if isinstance(exc, oracledb.Error)
                    else f"Erro {type(exc).__name__}."
                ),
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
        _registrar_erro_local("consultar_alvo_sessao_diag", "HostInacessivelVPN", rede=check_rede)
        return {
            "encontrado": False,
            "motivo": "HostInacessivelVPN",
            "mensagem": TEXTO_HOST_INACESSIVEL,
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
                   type,
                   logon_time
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
                # V4 (decisao_c1.md §2.4): o nome do usuário protegido não vai ao LLM; fica no log local.
                "mensagem": (
                    f"Sessão inst_id={inst_id_int}, sid={sid_int}, serial={serial_int} "
                    "pertence a usuário protegido. Encerramento não permitido."
                ),
            }

        return {
            "encontrado": True,
            "elegivel": True,
            "alvo": dados_alvo,
        }
    except oracledb.Error as db_err:
        _registrar_erro_local("consultar_alvo_sessao_diag", "ERRO_ORACLE", exc=db_err)
        return {
            "encontrado": False,
            "motivo": "ERRO_ORACLE",
            "codigo_erro": _codigo_erro(db_err),
            "mensagem": f"Erro do Oracle {_codigo_erro(db_err)}.",
        }
    except Exception as exc:
        _registrar_erro_local("consultar_alvo_sessao_diag", type(exc).__name__, exc=exc)
        return {
            "encontrado": False,
            "motivo": type(exc).__name__,
            "codigo_erro": _codigo_erro(exc),
            "mensagem": f"Erro {type(exc).__name__}.",
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


def _descrever_erro(exc: BaseException) -> str:
    """Texto do erro para mensagem; nunca levanta (A3): str(exc), senão o nome do tipo, senão texto fixo."""
    try:
        return str(exc)
    except Exception:
        pass
    try:
        return type(exc).__name__
    except Exception:
        return "Exception"


def _texto_identidade_invalido(valor: Any, aceita_none: bool) -> bool:
    """
    Texto de identidade: str de 1 a LIMITE_TEXTO_IDENTIDADE caracteres (ou None, se aceito). Nunca levanta.
    A10: "" é sempre inválido, também onde None é aceito (no Oracle '' é NULL; a GV$SESSION nunca traz '').
    """
    if valor is None:
        return not aceita_none
    if not isinstance(valor, str):
        return True
    return len(valor) > LIMITE_TEXTO_IDENTIDADE or len(valor) < 1


def campos_invalidos_identidade(identidade_esperada: Any) -> List[str]:
    """
    Validação local da identidade (sem o ref): NOMES dos campos inválidos, nunca valores. Total: nunca levanta
    (decisao.md D1). Usada no kill (com o ref) e antes do prompt HITL (A10, decisao_c1.md ponto 5).
    """
    invalidos: List[str] = []
    if not isinstance(identidade_esperada, dict) or set(identidade_esperada.keys()) != set(CAMPOS_IDENTIDADE_ESPERADA):
        invalidos.append("identidade_esperada")
    else:
        if _texto_identidade_invalido(identidade_esperada["username"], aceita_none=False):
            invalidos.append("username")
        for campo in ("program", "machine"):
            if _texto_identidade_invalido(identidade_esperada[campo], aceita_none=True):
                invalidos.append(campo)
        logon = identidade_esperada["logon_time"]
        if not (isinstance(logon, datetime) and logon.tzinfo is None and logon.microsecond == 0):
            invalidos.append("logon_time")
    return invalidos


def campos_invalidos_identidade_e_ref(identidade_esperada: Any, ref_aprovacao: Any) -> List[str]:
    """
    Validação local (camada adicional; o PKG_OPS_KILL v2 é a autoridade e revalida tudo): devolve os NOMES dos
    campos inválidos, nunca valores. Total: nunca levanta, para qualquer tipo de entrada (decisao.md D1).
    Os valores não são transformados (nem strip/upper/str): o PKG compara bytes.
    """
    invalidos = campos_invalidos_identidade(identidade_esperada)
    if not (isinstance(ref_aprovacao, str) and _REGEX_ID_INTERVENCAO.fullmatch(ref_aprovacao)):
        invalidos.append("ref_aprovacao")
    return invalidos


def matar_sessao_oracle(
    sid: int,
    serial: int,
    inst_id: Optional[int],
    *,
    identidade_esperada: Dict[str, Any],
    ref_aprovacao: str,
) -> str:
    """
    Executa o procedimento homologado de encerramento de sessão via conta segregada ORACLE_USER_KILL.
    Chama OPS_OWNER.PKG_OPS_KILL.KILL_SESSION (v2) num único bloco com os 9 formais nomeados, sem fallback
    para a assinatura v1 e sem retentativa. NÃO executa comando de sessão direto no Python.
    inst_id é obrigatório: não há instância padrão. Ausente (None) ou não inteiro positivo
    retorna PARAM_INVALIDO antes de qualquer consulta ou conexão.
    identidade_esperada e ref_aprovacao: keyword-only, sem default (decisao.md D4). A identidade vem da
    reconsulta DIAG cujo hash bateu; o PKG a compara com a GV$SESSION na mesma chamada do kill (D2).
    """
    # 1. Validação local antes de qualquer conexão: inteiros positivos, todos obrigatórios
    validados = validar_parametros_kill(inst_id, sid, serial)
    if validados is None:
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "PARAM_INVALIDO",
                "status_banco": "PARAM_INVALIDO",
                "resultado_desconhecido": False,
                "mensagem": (
                    f"Parâmetros inválidos para encerramento de sessão: inst_id={inst_id}, sid={sid}, serial={serial}. "
                    "inst_id, sid e serial são obrigatórios e devem ser inteiros estritamente positivos (> 0)."
                ),
            },
            ensure_ascii=False,
        )
    inst_id_int, sid_int, serial_int = validados

    # 1b. Identidade esperada e ref de aprovação, ainda antes do getenv (a mensagem só nomeia campos).
    invalidos = campos_invalidos_identidade_e_ref(identidade_esperada, ref_aprovacao)
    if invalidos:
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "PARAM_INVALIDO",
                "status_banco": "PARAM_INVALIDO",
                "resultado_desconhecido": False,
                "mensagem": (
                    "Identidade esperada ou referência de aprovação inválida; encerramento NÃO executado. "
                    f"Campos inválidos: {', '.join(invalidos)}."
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
                "resultado_desconhecido": False,
                "mensagem": (
                    "Configuração incompleta no cofre (.env). "
                    "Variáveis ORACLE_USER_KILL, ORACLE_PASSWORD_KILL e ORACLE_DSN são obrigatórias."
                ),
            },
            ensure_ascii=False,
        )

    # Gate de produção (decisao_c1.md §2.2-iv): sem OPS_KILL_PKG_VERSAO=2, nenhuma sonda nem conexão.
    if not kill_habilitado():
        logger.warning(
            f"KILL BLOQUEADO: KILL_DESABILITADO (OPS_KILL_PKG_VERSAO) | inst_id={inst_id_int}, sid={sid_int}, "
            f"serial={serial_int}"
        )
        return RESULTADO_KILL_DESABILITADO

    # 3. Pré-validação rápida de rede / VPN
    check_rede = verificar_acessibilidade_host(dsn, timeout=3.0)
    if not check_rede["acessivel"]:
        _registrar_erro_local("matar_sessao_oracle", "HostInacessivelVPN", rede=check_rede)
        return json.dumps(
            {
                "status": "erro",
                "motivo": "HostInacessivelVPN",
                "resultado_desconhecido": False,
                "host_acessivel": False,
                "mensagem": TEXTO_HOST_INACESSIVEL_VPN,
            },
            ensure_ascii=False,
        )

    connection: Optional[oracledb.Connection] = None
    cursor: Optional[oracledb.Cursor] = None
    # A partir do execute, um erro do Oracle não prova que o kill deixou de acontecer:
    # resultado desconhecido (decisão do responsável, 2026-11-17). Antes dele (connect/cursor/var),
    # o PKG certamente não rodou.
    execute_iniciado = False

    try:
        connection = oracledb.connect(
            user=user,
            password=password,
            dsn=dsn,
        )
        cursor = connection.cursor()

        # Execução com os 9 formais nomeados do PKG_OPS_KILL v2. As duas var são criadas antes de
        # execute_iniciado: erro ali prova que o PKG não rodou. logon_time vai como DATE pela própria var,
        # sem str nem TO_DATE (decisao.md D2). Valores de identidade crus, sem transformação (D1).
        status_var = cursor.var(oracledb.DB_TYPE_VARCHAR, size=128)
        logon_var = cursor.var(oracledb.DB_TYPE_DATE)
        logon_var.setvalue(0, identidade_esperada["logon_time"])
        execute_iniciado = True
        cursor.execute(
            """
            BEGIN
                OPS_OWNER.PKG_OPS_KILL.KILL_SESSION(
                    p_inst_id             => :p_inst_id,
                    p_sid                 => :p_sid,
                    p_serial              => :p_serial,
                    p_username_esperado   => :p_username_esperado,
                    p_program_esperado    => :p_program_esperado,
                    p_machine_esperado    => :p_machine_esperado,
                    p_logon_time_esperado => :p_logon_time_esperado,
                    p_ref_aprovacao       => :p_ref_aprovacao,
                    p_status              => :p_status
                );
            END;
            """,
            p_inst_id=inst_id_int,
            p_sid=sid_int,
            p_serial=serial_int,
            p_username_esperado=identidade_esperada["username"],
            p_program_esperado=identidade_esperada["program"],
            p_machine_esperado=identidade_esperada["machine"],
            p_logon_time_esperado=logon_var,
            p_ref_aprovacao=ref_aprovacao,
            p_status=status_var,
        )
        status_banco = str(status_var.getvalue() or "").strip()

        # Classificação pela lista fechada (decisao_c1.md, pontos 1 e 2a). "executado para" só para
        # RESULTADOS_KILL_EXECUTADO; fora das duas listas o desfecho é desconhecido.
        desconhecido = False
        if status_banco in RESULTADOS_KILL_EXECUTADO:
            mensagem = (
                f"Encerramento executado para "
                f"inst_id={inst_id_int}, sid={sid_int}, serial={serial_int}. "
                f"Status retornado pelo banco: {status_banco}."
            )
        elif status_banco == "ALVO_DIVERGENTE":
            # O Python só recebe o código; a mensagem não usa o texto genérico "executado" (decisao.md D5).
            mensagem = MENSAGEM_ALVO_DIVERGENTE
        elif status_banco in RECUSAS_PKG_SEM_KILL:
            mensagem = MENSAGEM_RECUSA_PKG.format(status=status_banco)
        else:
            desconhecido = True
            status_banco = status_banco or STATUS_PKG_VAZIO
            mensagem = (
                f"{MENSAGEM_RESULTADO_DESCONHECIDO}. Status retornado pelo procedimento de encerramento: {status_banco}; "
                f"{MENSAGEM_DESFECHO_NAO_CONFIRMADO}. Consulte OPS_KILL_AUDIT."
            )

        return json.dumps(
            {
                "status": status_banco,
                "motivo": status_banco,
                "status_banco": status_banco,
                "resultado_desconhecido": desconhecido,
                "inst_id": inst_id_int,
                "sid": sid_int,
                "serial": serial_int,
                "mensagem": mensagem,
            },
            ensure_ascii=False,
        )

    except oracledb.Error as db_err:
        # A3: _codigo_erro e _registrar_erro_local nunca levantam; nenhuma exceção sai daqui.
        # R1 ampliada V3 (decisao_c1.md §2.3): ao LLM só o código; o texto cru vai ao log local.
        _registrar_erro_local("matar_sessao_oracle", "ERRO_ORACLE", exc=db_err)
        if execute_iniciado:
            mensagem = (
                f"{MENSAGEM_RESULTADO_DESCONHECIDO}. Erro do Oracle a partir da chamada de encerramento: "
                f"{_codigo_erro(db_err)}"
            )
        else:
            mensagem = _codigo_erro(db_err)
        return json.dumps(
            {
                "status": "erro",
                "motivo": "ERRO_ORACLE",
                "status_banco": "ERRO_ORACLE",
                "resultado_desconhecido": execute_iniciado,
                "sid": sid_int,
                "serial": serial_int,
                "tipo_erro": "OracleError",
                "codigo_erro": _codigo_erro(db_err),
                "mensagem": mensagem,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        # D8 (decisao.md): exceção que não é do Oracle depois do execute também não prova que o kill deixou
        # de acontecer. Sem retentativa automática: o resultado é devolvido como desconhecido.
        _registrar_erro_local("matar_sessao_oracle", type(exc).__name__, exc=exc)
        if execute_iniciado:
            # R1 ampliada (conferencia_c7.md §6.1): o mesmo texto do ramo Oracle, sem nomear o pacote.
            mensagem = (
                f"{MENSAGEM_RESULTADO_DESCONHECIDO}. Erro a partir da chamada de encerramento: {type(exc).__name__}"
            )
        else:
            mensagem = _codigo_erro(exc)
        return json.dumps(
            {
                "status": "erro",
                "motivo": type(exc).__name__,
                "resultado_desconhecido": execute_iniciado,
                # R1 ampliada V1: nenhum ramo leva "instancia" (o DSN) ao LLM.
                "sid": sid_int,
                "serial": serial_int,
                "tipo_erro": type(exc).__name__,
                "mensagem": mensagem,
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
    """Normaliza tipos numéricos vindos do driver para que o hash não dependa do tipo Python.
    datetime (logon_time) vira isoformat(sep=" "), idêntico a str(dt) e ao que o JSONL grava: o hash pode ser
    recalculado a partir da linha INTENCAO (decisao.md D3)."""
    if valor is None or isinstance(valor, (bool, str)):
        return valor
    if isinstance(valor, datetime):
        return valor.isoformat(sep=" ")
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
    inst_id, sid, serial#, username, program, machine, logon_time.
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


def executar_kill_verificado(
    inst_id: Any,
    sid: Any,
    serial: Any,
    hash_aprovado: str,
    *,
    aprovacao_expirada: Callable[[], bool],
    ref_aprovacao: str,
) -> str:
    """
    Verificação de integridade imediatamente antes do encerramento:
      1. reconsulta o alvo pela conta DIAG (consultar_alvo_sessao_diag);
      2. recalcula o hash de identidade e compara com o hash aprovado;
      3. confere a elegibilidade na reconsulta;
      4. segundo recheck de TTL (aprovacao_expirada(), última checagem antes da conta KILL);
      5. só então chama matar_sessao_oracle (conta KILL).
    Hash divergente -> ALVO_ALTERADO, sem chamada à conta KILL, com registro no log.
    Falha na reconsulta (alvo sumiu, erro de rede/config) -> o motivo da reconsulta, sem chamada à conta KILL.
    TTL vencido no recheck -> APROVACAO_EXPIRADA, sem chamada à conta KILL.
    aprovacao_expirada: keyword-only, sem default. É um callable (e não preparado_em/agora) para que o
    item 7 troque a base do TTL num único ponto (desvio do plano registrado em docs/plans/1.11.md).
    ref_aprovacao: keyword-only, sem default; é o id_intervencao da INTENCAO (decisao.md D4).
    A identidade esperada enviada ao PKG vem da reconsulta cujo hash bateu, montada depois do hash, da
    elegibilidade e do TTL, só com as chaves presentes (a falta de chave fica para a validação local).
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
                "resultado_desconhecido": False,
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
                "resultado_desconhecido": False,
                # R1 ampliada V7 (R2; decisao_c1.md §2.7): os hashes ficam só no log acima e no JSONL.
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
            f"KILL BLOQUEADO NA RECONSULTA: {motivo} | inst_id={inst_id}, sid={sid}, serial={serial} | "
            f"username={(reconsulta.get('alvo') or {}).get('username')}"
        )
        return json.dumps(
            {
                "status": "recusado",
                "motivo": motivo,
                "status_banco": motivo,
                "resultado_desconhecido": False,
                "mensagem": reconsulta.get("mensagem", "Alvo não elegível na reconsulta."),
            },
            ensure_ascii=False,
        )

    if aprovacao_expirada():
        logger.warning(
            f"KILL BLOQUEADO NO RECHECK DE TTL: APROVACAO_EXPIRADA | inst_id={inst_id}, sid={sid}, "
            f"serial={serial} | TTL={APROVACAO_TTL_SEGUNDOS}s"
        )
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "APROVACAO_EXPIRADA",
                "status_banco": "APROVACAO_EXPIRADA",
                "resultado_desconhecido": False,
                "mensagem": (
                    f"A aprovação venceu ({APROVACAO_TTL_SEGUNDOS} s desde a preparação) antes da execução. "
                    "Nenhuma chamada à conta KILL."
                ),
            },
            ensure_ascii=False,
        )

    alvo_reconsulta = reconsulta.get("alvo") or {}
    identidade_esperada = {c: alvo_reconsulta[c] for c in CAMPOS_IDENTIDADE_ESPERADA if c in alvo_reconsulta}
    return matar_sessao_oracle(
        sid=sid,
        serial=serial,
        inst_id=inst_id,
        identidade_esperada=identidade_esperada,
        ref_aprovacao=ref_aprovacao,
    )


def _diretorio_log_aprovacao() -> Path:
    """AGENTDBA_LOG_DIR (ou o padrão) lido no momento da chamada (A3). Não cria nada."""
    return Path(os.getenv("AGENTDBA_LOG_DIR") or DIRETORIO_LOG_PADRAO)


def _caminho_log_efetivo(caminho_log: Optional[Path]) -> Path:
    """Destino do JSONL: o caminho dado, o gancho do módulo (testes) ou o padrão resolvido agora."""
    if caminho_log is not None:
        return Path(caminho_log)
    if CAMINHO_LOG_APROVACAO_PADRAO is not None:
        return Path(CAMINHO_LOG_APROVACAO_PADRAO)
    return _diretorio_log_aprovacao() / "kill_approval.log"


if os.name == "nt":

    def _travar_arquivo(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _destravar_arquivo(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:

    def _travar_arquivo(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _destravar_arquivo(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def _lock_arquivo_log(caminho_log: Path, timeout: Optional[float] = None) -> Iterator[None]:
    """
    Lock de SO entre processos (CLI e Web) num arquivo `<log>.lock` ao lado do log.
    Tenta sem bloquear, com novas tentativas até `timeout` (padrão LOCK_LOG_TIMEOUT_SEGUNDOS);
    esgotado o prazo, LockLogAprovacaoIndisponivel. O diretório já deve existir.
    """
    prazo_s = LOCK_LOG_TIMEOUT_SEGUNDOS if timeout is None else timeout
    caminho_lock = caminho_log.with_name(caminho_log.name + ".lock")
    fd = os.open(str(caminho_lock), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        limite = time.monotonic() + prazo_s
        while True:
            try:
                _travar_arquivo(fd)
                break
            except OSError:
                if time.monotonic() >= limite:
                    raise LockLogAprovacaoIndisponivel(
                        f"lock do log de aprovações não obtido em {prazo_s} s"
                    ) from None
                time.sleep(_LOCK_LOG_INTERVALO_SEGUNDOS)
        try:
            yield
        finally:
            _destravar_arquivo(fd)
    finally:
        os.close(fd)


def _fsync_diretorio(diretorio: Path) -> None:
    """fsync da entrada de diretório (só POSIX; ver _FSYNC_DIRETORIO)."""
    fd = os.open(str(diretorio), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _anexar_linha_sem_lock(caminho_log: Path, dados: bytes) -> bool:
    """
    Anexa `dados` (uma linha JSONL já codificada) com flush + fsync. Chamar só com os dois locks.
    Se a última linha existente ficou parcial (sem newline), a nova começa em linha própria.
    Retorna True se o arquivo era novo (vazio).
    """
    with open(caminho_log, "a+b") as f:
        fim = f.seek(0, os.SEEK_END)
        if fim > 0:
            f.seek(fim - 1)
            if f.read(1) != b"\n":
                dados = b"\n" + dados
        f.write(dados)
        f.flush()
        os.fsync(f.fileno())
    return fim == 0


def _codificar_linha(registro: Dict[str, Any]) -> bytes:
    """Serializa e codifica (UTF-8 estrito) ANTES de tocar o disco: erro de encoding não toca o arquivo."""
    return (json.dumps(registro, ensure_ascii=False, default=str) + "\n").encode("utf-8", errors="strict")


def _gravar_linha_jsonl_duravel(caminho_log: Path, registro: Dict[str, Any]) -> None:
    """
    ÚNICO ponto de escrita do kill_approval.log (INTENCAO e RESULTADO, inclusive REJEITADO/TIMEOUT, e o
    evento RECUSA_PRE_HITL).
    Ordem: serializa e codifica; lock de processo; os.makedirs(exist_ok); lock de arquivo (5 s);
    open "a+b"; write; flush; os.fsync; close; fsync do diretório só em POSIX e só para arquivo novo.
    Qualquer falha levanta exceção.
    """
    dados = _codificar_linha(registro)
    with _LOCK_LOG_APROVACAO:
        os.makedirs(caminho_log.parent, exist_ok=True)
        with _lock_arquivo_log(caminho_log):
            arquivo_novo = _anexar_linha_sem_lock(caminho_log, dados)
        if arquivo_novo and _FSYNC_DIRETORIO:
            _fsync_diretorio(caminho_log.parent)


def _montar_registro_aprovacao_kill(
    aprovador: str,
    decisao: str,
    hash_payload: str,
    parametros: Dict[str, Any],
    alvo: Optional[Dict[str, Any]],
    resultado_banco: Optional[str],
    motivo: Optional[str],
    *,
    fase: str,
    id_intervencao: str,
    resultado_desconhecido: Optional[bool],
) -> Dict[str, Any]:
    """
    Monta e valida uma linha do JSONL, sem tocar o disco. Entrada inválida -> ValueError.

    R-a (correcao/k6/decisao_ra.md): toda RESULTADO leva resultado_desconhecido bool (True ou False, nunca
    None/0/1); a INTENCAO não leva a chave e exige None. Sem default: quem grava diz o valor.
    """
    if decisao not in DECISOES_KILL:
        raise ValueError(f"Decisão inválida: {decisao!r}. Esperado um de {DECISOES_KILL}.")
    if fase not in FASES_REGISTRO_KILL:
        raise ValueError(f"Fase inválida: {fase!r}. Esperado um de {FASES_REGISTRO_KILL}.")
    if not isinstance(id_intervencao, str) or not _REGEX_ID_INTERVENCAO.fullmatch(id_intervencao):
        raise ValueError("id_intervencao fora do formato de 32 hexadecimais minúsculos.")
    if fase == "INTENCAO" and (decisao != "APROVADO" or resultado_banco is not None):
        raise ValueError("INTENCAO exige decisao=APROVADO e resultado_banco=None.")
    if fase == "RESULTADO":
        if not isinstance(resultado_desconhecido, bool):
            raise ValueError("RESULTADO exige resultado_desconhecido booleano (True ou False).")
    elif resultado_desconhecido is not None:
        raise ValueError("INTENCAO não leva resultado_desconhecido (passe None).")
    registro: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fase": fase,
        "id_intervencao": id_intervencao,
        "aprovador": aprovador,
        "decisao": decisao,
        "resultado_banco": resultado_banco,
    }
    if fase == "RESULTADO":
        registro["resultado_desconhecido"] = resultado_desconhecido
    registro.update(
        {
            "motivo": motivo,
            "hash_payload": hash_payload,
            "parametros": parametros,
            "alvo": alvo or {},
        }
    )
    return registro


def _montar_registro_recusa_pre_hitl(
    parametros: Dict[str, Any], campos_invalidos: List[str], id_evento: str
) -> Dict[str, Any]:
    """
    Linha RECUSA_PRE_HITL (A10; decisao_c1.md ponto 5): só nomes de campo, nunca valores de identidade.
    Sem alvo, aprovador, decisao, hash_payload nem resultado_banco. O id é só deste evento (não vai ao PKG,
    ao LLM nem a uma INTENCAO) e existe para o reconciliador não contar a linha como inválida.
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fase": FASE_RECUSA_PRE_HITL,
        "id_intervencao": id_evento,
        "motivo": "PARAM_INVALIDO",
        "campos_invalidos": list(campos_invalidos),
        "parametros": parametros,
    }


def registrar_log_aprovacao_kill(
    aprovador: str,
    decisao: str,
    hash_payload: str,
    parametros: Dict[str, Any],
    alvo: Optional[Dict[str, Any]] = None,
    resultado_banco: Optional[str] = None,
    motivo: Optional[str] = None,
    caminho_log: Optional[Path] = None,
    *,
    fase: str,
    id_intervencao: str,
    resultado_desconhecido: Optional[bool],
) -> Dict[str, Any]:
    """
    Registra uma linha no JSONL de aprovações (append-only), com durabilidade (fsync).

    Campos separados:
      - fase: INTENCAO (antes de qualquer conexão posterior à decisão) | RESULTADO; obrigatório;
      - id_intervencao: 32 hex minúsculos, mesmo valor na INTENCAO e na RESULTADO; obrigatório;
      - decisao: decisão humana (APROVADO | REJEITADO | TIMEOUT);
      - resultado_banco: status devolvido pela execução (p_status de PKG_OPS_KILL ou
        recusa local anterior à chamada); None quando nada foi executado;
      - motivo: justificativa de decisões não aprovadas (ex.: SEM_IDENTIFICACAO);
      - resultado_desconhecido: keyword-only, sem default (R-a). Na RESULTADO, bool obrigatório (True: desfecho
        no banco não confirmado, conferir OPS_KILL_AUDIT); na INTENCAO, None (a chave não é gravada).
    NUNCA armazena senhas, tokens ou dados sensíveis. Qualquer falha levanta exceção.
    """
    registro = _montar_registro_aprovacao_kill(
        aprovador, decisao, hash_payload, parametros, alvo, resultado_banco, motivo,
        fase=fase, id_intervencao=id_intervencao, resultado_desconhecido=resultado_desconhecido,
    )
    _gravar_linha_jsonl_duravel(_caminho_log_efetivo(caminho_log), registro)
    return registro


def reconciliar_intencoes_orfas(
    caminho_log: Optional[Path] = None,
    agora: Optional[Callable[[], datetime]] = None,
) -> Dict[str, Any]:
    """
    Reconciliador chamado na subida da CLI e da Web.

    Sob os dois locks, lê o JSONL e, para cada INTENCAO sem RESULTADO com o mesmo id_intervencao e
    mais antiga que RECONCILIACAO_IDADE_MINIMA_SEGUNDOS, anexa uma RESULTADO com
    resultado_banco=NAO_CONCLUIDA e motivo=RECONCILIADO_NA_SUBIDA (mesmo id, aprovador, hash, parametros
    e alvo da INTENCAO). Para o auditor, NAO_CONCLUIDA é "a conferir em OPS_KILL_AUDIT"; uma RESULTADO
    real que chegue depois prevalece. INTENCAO mais recente que a idade mínima, ou com timestamp
    ilegível ou sem fuso, não é tocada (pode estar em curso em outro processo).

    Linhas que não são JSON e linhas sem `fase` (formato anterior à 1.11) são ignoradas.
    Arquivo inexistente: nada a fazer, nada é criado. Falha de E/S ou de lock levanta exceção.

    Retorna {"reconciliadas": [ids], "recentes": [ids], "timestamp_invalido": [ids], "linhas_invalidas": n}.
    """
    destino = _caminho_log_efetivo(caminho_log)
    resumo: Dict[str, Any] = {"reconciliadas": [], "recentes": [], "timestamp_invalido": [], "linhas_invalidas": 0}
    if not destino.exists():
        return resumo

    with _LOCK_LOG_APROVACAO:
        with _lock_arquivo_log(destino):
            instante = (agora or _agora_utc)()
            intencoes: Dict[str, Dict[str, Any]] = {}
            com_resultado = set()
            with open(destino, "rb") as f:
                for linha in f.read().splitlines():
                    if not linha.strip():
                        continue
                    try:
                        reg = json.loads(linha.decode("utf-8"))
                    except (UnicodeDecodeError, ValueError):
                        resumo["linhas_invalidas"] += 1
                        continue
                    if not isinstance(reg, dict) or "fase" not in reg:
                        continue
                    id_reg = reg.get("id_intervencao")
                    if not isinstance(id_reg, str) or not _REGEX_ID_INTERVENCAO.fullmatch(id_reg):
                        resumo["linhas_invalidas"] += 1
                        continue
                    if reg.get("fase") == "INTENCAO":
                        intencoes.setdefault(id_reg, reg)
                    elif reg.get("fase") == "RESULTADO":
                        com_resultado.add(id_reg)

            for id_reg, intencao in intencoes.items():
                if id_reg in com_resultado:
                    continue
                try:
                    inicio = datetime.fromisoformat(intencao.get("timestamp"))
                    if inicio.tzinfo is None:
                        raise ValueError("timestamp sem fuso")
                    idade = instante - inicio
                except (TypeError, ValueError):
                    resumo["timestamp_invalido"].append(id_reg)
                    continue
                if idade < timedelta(seconds=RECONCILIACAO_IDADE_MINIMA_SEGUNDOS):
                    resumo["recentes"].append(id_reg)
                    continue
                registro = _montar_registro_aprovacao_kill(
                    intencao.get("aprovador"),
                    "APROVADO",
                    intencao.get("hash_payload"),
                    intencao.get("parametros"),
                    intencao.get("alvo"),
                    RESULTADO_NAO_CONCLUIDA,
                    MOTIVO_RECONCILIADO,
                    fase="RESULTADO",
                    id_intervencao=id_reg,
                    resultado_desconhecido=True,
                )
                _anexar_linha_sem_lock(destino, _codificar_linha(registro))
                resumo["reconciliadas"].append(id_reg)

    for id_reg in resumo["reconciliadas"]:
        logger.warning(
            f"AUDITORIA HITL: INTENCAO sem RESULTADO reconciliada como {RESULTADO_NAO_CONCLUIDA} | "
            f"id_intervencao={id_reg} | conferir OPS_KILL_AUDIT"
        )
    if resumo["timestamp_invalido"]:
        logger.warning(
            f"AUDITORIA HITL: INTENCAO sem RESULTADO com timestamp ilegível (não reconciliada): "
            f"{resumo['timestamp_invalido']}"
        )
    if resumo["linhas_invalidas"]:
        logger.warning(f"AUDITORIA HITL: {resumo['linhas_invalidas']} linha(s) inválida(s) no log de aprovações")
    return resumo


def montar_notificacao_kill(
    aprovador: str,
    inst_id: int,
    sid: int,
    serial: int,
    resultado_banco: str,
    hash_payload: str,
    canal: str,
    *,
    resultado_desconhecido: bool,
) -> Tuple[str, str]:
    """
    Monta assunto e corpo do e-mail de uma intervenção aprovada.
    O assunto "Intervenção Aprovada" só é usado quando resultado_banco indica execução
    efetiva (ENCERRADA ou MARCADA_PARA_KILL). resultado_desconhecido (qualquer desfecho fora da
    lista fechada) gera MENSAGEM_RESULTADO_DESCONHECIDO. Qualquer outro resultado gera
    "Intervenção NÃO executada", informando o status. resultado_desconhecido é keyword-only e sem
    default: o chamador sempre o informa (decisao_c1.md, ponto 2e).
    """
    if resultado_desconhecido:
        assunto = (
            f"[AGENTE DBA] Intervenção com {MENSAGEM_RESULTADO_DESCONHECIDO}: Kill Session {sid},{serial} "
            f"(status {resultado_banco})"
        )
        corpo = (
            f"O encerramento da sessão SID={sid}, SERIAL={serial}, INST_ID={inst_id} "
            f"foi aprovado por {aprovador} ({canal}); {MENSAGEM_DESFECHO_NAO_CONFIRMADO}.\n"
            f"{MENSAGEM_RESULTADO_DESCONHECIDO[0].upper()}{MENSAGEM_RESULTADO_DESCONHECIDO[1:]} "
            f"(GV$SESSION e OPS_KILL_AUDIT).\n"
            f"Status retornado: {resultado_banco}\n"
            f"Hash SHA-256 de identidade do alvo: {hash_payload}"
        )
    elif resultado_banco in RESULTADOS_KILL_EXECUTADO:
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


def _agora_utc() -> datetime:
    """Relógio padrão (UTC, com fuso) usado na verificação de expiração da aprovação."""
    return datetime.now(timezone.utc)


def _aprovacao_expirada(preparado_em: Optional[str], instante: datetime) -> bool:
    """
    True se a aprovação está fora da janela válida [0, APROVACAO_TTL_SEGUNDOS) desde a preparação.
    Fail-closed: preparado_em ausente, inválido, sem fuso ou no futuro conta como expirado.
    """
    try:
        inicio = datetime.fromisoformat(preparado_em)
        if inicio.tzinfo is None or instante.tzinfo is None:
            return True
        decorrido = instante - inicio
    except (TypeError, ValueError):
        return True
    return decorrido < timedelta(0) or decorrido >= timedelta(seconds=APROVACAO_TTL_SEGUNDOS)


def _serializar_para_log(registro: Dict[str, Any]) -> str:
    """Serialização tolerante do registro para logger (nunca levanta)."""
    try:
        return json.dumps(registro, ensure_ascii=False, default=str)
    except Exception:
        return repr(registro)


def registrar_decisao_kill(
    decisao: str,
    aprovador: str,
    inst_id: int,
    sid: int,
    serial: int,
    alvo: Dict[str, Any],
    hash_aprovado: str,
    canal: str,
    preparado_em: Optional[str],
    motivo: Optional[str] = None,
    caminho_log: Optional[Path] = None,
    agora: Optional[Callable[[], datetime]] = None,
) -> Dict[str, Any]:
    """
    Aplica a decisão humana sobre uma intervenção já preparada (alvo elegível e hash exibido).
    Ordem fail-closed (item 1, docs/entregas/1.11/item1/decisao.md):

    - APROVADO com aprovador identificado e dentro do TTL:
        1. grava a INTENCAO (fsync) ANTES de qualquer conexão posterior à decisão;
           falha -> FALHA_LOG_APROVACAO: sem reconsulta DIAG, sem conta KILL, sem e-mail;
        2. executar_kill_verificado (reconsulta, hash, elegibilidade, recheck de TTL, conta KILL);
           Exception -> ERRO_INTERNO (segue o fluxo); BaseException -> RESULTADO INTERROMPIDO e re-raise;
        3. grava a RESULTADO (mesmo id_intervencao); falha -> logger.critical com o registro e
           e-mail com o marcador [REGISTRO DE RESULTADO FALHOU];
        4. e-mail conforme o resultado efetivo.
    - APROVADO sem aprovador: convertido em REJEITADO (motivo SEM_IDENTIFICACAO), sem execução.
    - APROVADO fora da validade (preparado_em + APROVACAO_TTL_SEGUNDOS, fail-closed): convertido
      em TIMEOUT (motivo APROVACAO_EXPIRADA), sem reconsulta, sem execução e sem e-mail.
    - REJEITADO / TIMEOUT: uma linha RESULTADO, sem execução e sem e-mail; falha de gravação ->
      logger.error com o registro, desfecho normal com falha_registro="RESULTADO".

    preparado_em: timestamp ISO-8601 com fuso devolvido por preparar_intervencao_kill.
    agora: relógio injetável (padrão: UTC atual); o relógio é lido duas vezes: na decisão e de novo
    no recheck de TTL, imediatamente antes da conta KILL (via aprovacao_expirada).

    Retorna dict com decisao, resultado_banco, executado, motivo, resultado_tool (JSON para o LLM,
    sem id_intervencao), registro gravado (ou None), falha_registro (None | "INTENCAO" | "RESULTADO"),
    id_intervencao, resultado_desconhecido e dados da notificação.
    """
    if decisao not in DECISOES_KILL:
        raise ValueError(f"Decisão inválida: {decisao!r}. Esperado um de {DECISOES_KILL}.")

    relogio = agora or _agora_utc
    instante_decisao = relogio()
    parametros = {"inst_id": inst_id, "sid": sid, "serial": serial}
    aprovador_limpo = (aprovador or "").strip()
    destino_log = _caminho_log_efetivo(caminho_log)
    # Gerado antes de qualquer ramo: todo registro (inclusive REJEITADO/TIMEOUT) leva o id.
    id_intervencao = uuid.uuid4().hex

    if decisao == "APROVADO" and not aprovador_limpo:
        decisao = "REJEITADO"
        motivo = "SEM_IDENTIFICACAO"

    if decisao == "APROVADO" and _aprovacao_expirada(preparado_em, instante_decisao):
        logger.warning(
            f"AUDITORIA HITL: aprovação expirada ({canal}) | preparado_em={preparado_em!r} | "
            f"decidido_em={instante_decisao.isoformat()} | TTL={APROVACAO_TTL_SEGUNDOS}s"
        )
        decisao = "TIMEOUT"
        motivo = "APROVACAO_EXPIRADA"

    if decisao != "APROVADO":
        if motivo is None:
            motivo = "TIMEOUT_APROVACAO" if decisao == "TIMEOUT" else "REJEITADO_PELO_APROVADOR"
        aprovador_registro = aprovador_limpo or "NAO_INFORMADO"
        falha_registro: Optional[str] = None
        try:
            registro = registrar_log_aprovacao_kill(
                aprovador=aprovador_registro,
                decisao=decisao,
                hash_payload=hash_aprovado,
                parametros=parametros,
                alvo=alvo,
                resultado_banco=None,
                motivo=motivo,
                caminho_log=destino_log,
                fase="RESULTADO",
                id_intervencao=id_intervencao,
                resultado_desconhecido=False,
            )
        except Exception as exc:
            registro = None
            falha_registro = "RESULTADO"
            logger.error(
                f"AUDITORIA HITL: FALHA AO GRAVAR RESULTADO ({decisao}/{motivo}, {canal}) | "
                f"id_intervencao={id_intervencao} | erro={type(exc).__name__} "
                f"errno={getattr(exc, 'errno', None)} | registro="
                + _serializar_para_log(
                    {
                        "fase": "RESULTADO",
                        "id_intervencao": id_intervencao,
                        "aprovador": aprovador_registro,
                        "decisao": decisao,
                        "resultado_banco": None,
                        "resultado_desconhecido": False,
                        "motivo": motivo,
                        "hash_payload": hash_aprovado,
                        "parametros": parametros,
                    }
                )
            )
        logger.warning(
            f"AUDITORIA HITL: {decisao} ({motivo}) por {aprovador_registro} ({canal}) | "
            f"inst_id={inst_id}, sid={sid}, serial={serial} | Hash={hash_aprovado}"
        )
        if motivo == "APROVACAO_EXPIRADA":
            mensagem = (
                f"Aprovação expirada: decisão registrada após o prazo de {APROVACAO_TTL_SEGUNDOS} s "
                "desde a preparação; os dados exibidos podem estar vencidos. "
                "Nenhuma chamada à conta KILL foi feita. "
                "Para prosseguir, reconsulte a sessão e solicite nova aprovação."
            )
        else:
            # R1 ampliada V5 (decisao_c1.md §2.5): o aprovador fica no JSONL, no log e na tela, não no LLM.
            mensagem = (
                f"Intervenção não aprovada ({decisao}/{motivo}). "
                "Nenhuma chamada à conta KILL foi feita."
            )
        resultado_tool = json.dumps(
            {
                "status": "abortado",
                "decisao": decisao,
                "motivo": motivo,
                "resultado_banco": None,
                "executado": False,
                "mensagem": mensagem,
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
            "falha_registro": falha_registro,
            "id_intervencao": id_intervencao,
            "resultado_desconhecido": False,
            "assunto_email": None,
            "email_enviado": None,
            "email_detalhe": None,
        }

    # Gate de produção (decisao_c1.md §2.2-iii-b): APROVADO, mas sem OPS_KILL_PKG_VERSAO=2 (ex.: HITL pendente com a
    # variável retirada antes do clique). Uma RESULTADO sem INTENCAO; sem reconsulta, sem conta KILL e sem e-mail.
    if not kill_habilitado():
        falha_registro_gate: Optional[str] = None
        try:
            registro = registrar_log_aprovacao_kill(
                aprovador=aprovador_limpo,
                decisao="APROVADO",
                hash_payload=hash_aprovado,
                parametros=parametros,
                alvo=alvo,
                resultado_banco="KILL_DESABILITADO",
                motivo="KILL_DESABILITADO",
                caminho_log=destino_log,
                fase="RESULTADO",
                id_intervencao=id_intervencao,
                resultado_desconhecido=False,
            )
        except Exception as exc:
            registro = None
            falha_registro_gate = "RESULTADO"
            logger.error(
                f"AUDITORIA HITL: FALHA AO GRAVAR RESULTADO (APROVADO/KILL_DESABILITADO, {canal}) | "
                f"id_intervencao={id_intervencao} | erro={type(exc).__name__} "
                f"errno={getattr(exc, 'errno', None)} | registro="
                + _serializar_para_log(
                    {
                        "fase": "RESULTADO",
                        "id_intervencao": id_intervencao,
                        "aprovador": aprovador_limpo,
                        "decisao": "APROVADO",
                        "resultado_banco": "KILL_DESABILITADO",
                        "resultado_desconhecido": False,
                        "motivo": "KILL_DESABILITADO",
                        "hash_payload": hash_aprovado,
                        "parametros": parametros,
                    }
                )
            )
        logger.warning(
            f"AUDITORIA HITL: APROVADO por {aprovador_limpo} ({canal}), mas KILL_DESABILITADO "
            f"(OPS_KILL_PKG_VERSAO) | inst_id={inst_id}, sid={sid}, serial={serial} | Hash={hash_aprovado} | "
            f"id_intervencao={id_intervencao}"
        )
        resultado_tool = json.dumps(
            {
                "status": "abortado",
                "decisao": "APROVADO",
                "motivo": "KILL_DESABILITADO",
                "resultado_banco": "KILL_DESABILITADO",
                "executado": False,
                "mensagem": (
                    "Encerramento de sessão indisponível nesta instalação; intervenção NÃO executada. "
                    "Nenhuma consulta nem chamada à conta KILL foi feita."
                ),
            },
            ensure_ascii=False,
        )
        return {
            "decisao": "APROVADO",
            "resultado_banco": "KILL_DESABILITADO",
            "executado": False,
            "motivo": "KILL_DESABILITADO",
            "resultado_tool": resultado_tool,
            "registro": registro,
            "falha_registro": falha_registro_gate,
            "id_intervencao": id_intervencao,
            "resultado_desconhecido": False,
            "assunto_email": None,
            "email_enviado": None,
            "email_detalhe": None,
        }

    # 1. INTENCAO durável ANTES de qualquer conexão posterior à decisão (reconsulta DIAG, sonda, KILL).
    try:
        registrar_log_aprovacao_kill(
            aprovador=aprovador_limpo,
            decisao="APROVADO",
            hash_payload=hash_aprovado,
            parametros=parametros,
            alvo=alvo,
            resultado_banco=None,
            motivo=None,
            caminho_log=destino_log,
            fase="INTENCAO",
            id_intervencao=id_intervencao,
            resultado_desconhecido=None,
        )
    except Exception as exc:
        # Sem a INTENCAO não há prova de que a aprovação foi registrada antes da ação: recusa.
        # A mensagem da exceção fica fora do log (pode trazer caminho); só tipo e errno.
        logger.error(
            f"AUDITORIA HITL: FALHA_LOG_APROVACAO ({canal}) | id_intervencao={id_intervencao} | "
            f"inst_id={inst_id}, sid={sid}, serial={serial} | Hash={hash_aprovado} | "
            f"aprovador={aprovador_limpo} | erro={type(exc).__name__} errno={getattr(exc, 'errno', None)} | "
            "KILL NAO EXECUTADO"
        )
        resultado_tool = json.dumps(
            {
                "status": "abortado",
                "decisao": "APROVADO",
                "motivo": "FALHA_LOG_APROVACAO",
                "resultado_banco": None,
                "executado": False,
                "mensagem": (
                    "Falha ao gravar o registro de aprovação; intervenção NÃO executada. "
                    "Nenhuma chamada à conta KILL foi feita."
                ),
            },
            ensure_ascii=False,
        )
        return {
            "decisao": "APROVADO",
            "resultado_banco": None,
            "executado": False,
            "motivo": "FALHA_LOG_APROVACAO",
            "resultado_tool": resultado_tool,
            "registro": None,
            "falha_registro": "INTENCAO",
            "id_intervencao": id_intervencao,
            "resultado_desconhecido": False,
            "assunto_email": None,
            "email_enviado": None,
            "email_detalhe": None,
        }

    # 2. Reconsulta + hash + elegibilidade + recheck de TTL antes da conta KILL.
    motivo_resultado: Optional[str] = None
    try:
        resultado_exec = executar_kill_verificado(
            inst_id=inst_id,
            sid=sid,
            serial=serial,
            hash_aprovado=hash_aprovado,
            aprovacao_expirada=lambda: _aprovacao_expirada(preparado_em, relogio()),
            ref_aprovacao=id_intervencao,
        )
    except Exception as exc:
        motivo_resultado = type(exc).__name__
        logger.error(
            f"AUDITORIA HITL: ERRO_INTERNO no fluxo de kill ({canal}) | id_intervencao={id_intervencao} | "
            f"inst_id={inst_id}, sid={sid}, serial={serial} | erro={motivo_resultado}"
        )
        resultado_exec = json.dumps(
            {
                "status": "erro",
                "motivo": "ERRO_INTERNO",
                "status_banco": "ERRO_INTERNO",
                "resultado_desconhecido": True,
                "tipo_erro": motivo_resultado,
                "mensagem": (
                    f"{MENSAGEM_RESULTADO_DESCONHECIDO}. Erro interno no fluxo de kill; "
                    "estado no banco não confirmado. Consulte OPS_KILL_AUDIT."
                ),
            },
            ensure_ascii=False,
        )
    except BaseException as exc:
        registro_interrompido = {
            "fase": "RESULTADO",
            "id_intervencao": id_intervencao,
            "aprovador": aprovador_limpo,
            "decisao": "APROVADO",
            "resultado_banco": "INTERROMPIDO",
            "resultado_desconhecido": True,
            "motivo": type(exc).__name__,
            "hash_payload": hash_aprovado,
            "parametros": parametros,
        }
        gravado = False
        try:
            registrar_log_aprovacao_kill(
                aprovador=aprovador_limpo,
                decisao="APROVADO",
                hash_payload=hash_aprovado,
                parametros=parametros,
                alvo=alvo,
                resultado_banco="INTERROMPIDO",
                motivo=type(exc).__name__,
                caminho_log=destino_log,
                fase="RESULTADO",
                id_intervencao=id_intervencao,
                resultado_desconhecido=True,
            )
            gravado = True
        except Exception:
            gravado = False
        logger.critical(
            f"AUDITORIA HITL: INTERROMPIDO ({canal}) | id_intervencao={id_intervencao} | "
            f"inst_id={inst_id}, sid={sid}, serial={serial} | erro={type(exc).__name__} | "
            "desfecho desconhecido; consulte OPS_KILL_AUDIT"
            + ("" if gravado else " | RESULTADO NAO GRAVADA | registro=" + _serializar_para_log(registro_interrompido))
        )
        raise

    # Falha fechada (decisao_c1.md, ponto 2d): só um bool False explícito, num JSON dict legível, tira o
    # desconhecido. Retorno ilegível não é ecoado ao LLM.
    try:
        dados_exec = json.loads(resultado_exec)
        parse_ok = isinstance(dados_exec, dict)
    except (TypeError, ValueError):
        parse_ok = False
    if not parse_ok:
        dados_exec = {
            "status": "erro",
            "status_banco": STATUS_PKG_VAZIO,
            "resultado_desconhecido": True,
            "mensagem": (
                f"{MENSAGEM_RESULTADO_DESCONHECIDO}. Retorno do fluxo de kill ilegível; "
                "estado no banco não confirmado. Consulte OPS_KILL_AUDIT."
            ),
        }
    resultado_banco = str(dados_exec.get("status_banco") or dados_exec.get("motivo") or "DESCONHECIDO")
    resultado_desconhecido = not (parse_ok and dados_exec.get("resultado_desconhecido") is False)
    executado = resultado_banco in RESULTADOS_KILL_EXECUTADO and not resultado_desconhecido

    # 3. RESULTADO com o mesmo id_intervencao.
    falha_registro = None
    try:
        registro = registrar_log_aprovacao_kill(
            aprovador=aprovador_limpo,
            decisao="APROVADO",
            hash_payload=hash_aprovado,
            parametros=parametros,
            alvo=alvo,
            resultado_banco=resultado_banco,
            motivo=motivo_resultado,
            caminho_log=destino_log,
            fase="RESULTADO",
            id_intervencao=id_intervencao,
            resultado_desconhecido=resultado_desconhecido,
        )
    except Exception as exc:
        registro = None
        falha_registro = "RESULTADO"
        logger.critical(
            f"AUDITORIA HITL: FALHA AO GRAVAR RESULTADO ({canal}) | id_intervencao={id_intervencao} | "
            f"erro={type(exc).__name__} errno={getattr(exc, 'errno', None)} | registro="
            + _serializar_para_log(
                {
                    "fase": "RESULTADO",
                    "id_intervencao": id_intervencao,
                    "aprovador": aprovador_limpo,
                    "decisao": "APROVADO",
                    "resultado_banco": resultado_banco,
                    "resultado_desconhecido": resultado_desconhecido,
                    "motivo": motivo_resultado,
                    "hash_payload": hash_aprovado,
                    "parametros": parametros,
                    "alvo": alvo or {},
                }
            )
        )

    nivel_log = logging.INFO if executado else logging.WARNING
    logger.log(
        nivel_log,
        f"AUDITORIA HITL: APROVADO por {aprovador_limpo} ({canal}) | "
        f"inst_id={inst_id}, sid={sid}, serial={serial} | Hash={hash_aprovado} | "
        f"resultado_banco={resultado_banco} | executado={executado} | "
        f"resultado_desconhecido={resultado_desconhecido} | id_intervencao={id_intervencao}",
    )

    # 4. E-mail conforme o resultado efetivo.
    assunto, corpo = montar_notificacao_kill(
        aprovador=aprovador_limpo,
        inst_id=inst_id,
        sid=sid,
        serial=serial,
        resultado_banco=resultado_banco,
        hash_payload=hash_aprovado,
        canal=canal,
        resultado_desconhecido=resultado_desconhecido,
    )
    if falha_registro == "RESULTADO":
        assunto = "[REGISTRO DE RESULTADO FALHOU] " + assunto
        corpo += (
            "\nATENÇÃO: a linha RESULTADO não foi gravada em kill_approval.log; registro completo no log "
            f"da aplicação (CRITICAL), id_intervencao={id_intervencao}."
        )
    email_enviado, email_detalhe = enviar_alerta_email(assunto, corpo)
    logger.info(f"NOTIFICAÇÃO SMTP: Sucesso={email_enviado} | Assunto={assunto} | Detalhe: {email_detalhe}")

    dados_exec["decisao"] = "APROVADO"
    dados_exec["resultado_banco"] = resultado_banco
    dados_exec["executado"] = executado
    dados_exec["resultado_desconhecido"] = resultado_desconhecido
    resultado_tool = json.dumps(dados_exec, ensure_ascii=False, default=str)

    return {
        "decisao": "APROVADO",
        "resultado_banco": resultado_banco,
        "executado": executado,
        "motivo": motivo_resultado,
        "resultado_tool": resultado_tool,
        "registro": registro,
        "falha_registro": falha_registro,
        "id_intervencao": id_intervencao,
        "resultado_desconhecido": resultado_desconhecido,
        "assunto_email": assunto,
        "email_enviado": email_enviado,
        "email_detalhe": email_detalhe,
    }


def preparar_intervencao_kill(
    argumentos: Dict[str, Any],
    ferramenta: str = "matar_sessao_oracle",
    caminho_log: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Etapa anterior à aprovação humana, comum à CLI (main.py) e à Web UI (app.py):
      1. valida inst_id, sid e serial (obrigatórios) sem consulta nem conexão;
      2. pré-consulta o alvo pela conta DIAG (existência, TYPE e usuário protegido);
      3. para alvo elegível, gera o payload e o hash de identidade a exibir ao aprovador.

    Retorna requer_aprovacao=False com motivo e resultado_tool (JSON para o LLM) quando o alvo
    deve ser recusado sem prompt; ou requer_aprovacao=True com inst_id, sid, serial, alvo,
    hash_identidade, payload e timestamp.
    """
    inst_id = argumentos.get("inst_id")
    sid = argumentos.get("sid")
    serial = argumentos.get("serial")

    validados = validar_parametros_kill(inst_id, sid, serial)
    if validados is None:
        logger.warning(f"HITL RECUSADO LOCALMENTE: PARAM_INVALIDO | inst_id={inst_id}, sid={sid}, serial={serial}")
        return {
            "requer_aprovacao": False,
            "motivo": "PARAM_INVALIDO",
            "resultado_tool": json.dumps(
                {
                    "status": "recusado",
                    "motivo": "PARAM_INVALIDO",
                    "status_banco": "PARAM_INVALIDO",
                    "mensagem": (
                        f"Parâmetros inválidos: inst_id={inst_id}, sid={sid}, serial={serial}. "
                        "inst_id, sid e serial são obrigatórios e devem ser inteiros estritamente positivos (> 0)."
                    ),
                },
                ensure_ascii=False,
            ),
        }
    inst_id_int, sid_int, serial_int = validados

    # Gate de produção (decisao_c1.md §2.2-iii-a): sem OPS_KILL_PKG_VERSAO=2, sem pré-consulta e sem prompt.
    if not kill_habilitado():
        logger.warning(
            f"HITL RECUSADO LOCALMENTE: KILL_DESABILITADO (OPS_KILL_PKG_VERSAO) | inst_id={inst_id_int}, "
            f"sid={sid_int}, serial={serial_int}"
        )
        return {
            "requer_aprovacao": False,
            "motivo": "KILL_DESABILITADO",
            "resultado_tool": RESULTADO_KILL_DESABILITADO,
        }

    check_alvo = consultar_alvo_sessao_diag(inst_id=inst_id_int, sid=sid_int, serial=serial_int)
    if not check_alvo.get("elegivel"):
        motivo = check_alvo.get("motivo", "ALVO_NAO_ENCONTRADO")
        logger.warning(
            f"HITL CANCELADO: alvo recusado na pré-consulta GV$SESSION | "
            f"inst_id={inst_id_int}, sid={sid_int}, serial={serial_int} | Motivo={motivo} | "
            f"username={(check_alvo.get('alvo') or {}).get('username')}"
        )
        return {
            "requer_aprovacao": False,
            "motivo": motivo,
            "alvo": check_alvo.get("alvo"),
            "mensagem": check_alvo.get("mensagem", "Alvo não elegível na GV$SESSION."),
            "resultado_tool": json.dumps(
                {
                    "status": "recusado",
                    "motivo": motivo,
                    "status_banco": motivo,
                    "mensagem": check_alvo.get("mensagem", "Alvo não elegível na GV$SESSION."),
                },
                ensure_ascii=False,
                default=str,
            ),
        }

    alvo = check_alvo["alvo"]

    # A10, parte 2 (decisao_c1.md ponto 5): identidade do alvo fora do formato -> recusa antes do prompt,
    # sem INTENCAO; evento próprio no JSONL (só nomes de campo). Montagem igual à de executar_kill_verificado.
    fonte = alvo if isinstance(alvo, dict) else {}
    identidade = {c: fonte[c] for c in CAMPOS_IDENTIDADE_ESPERADA if c in fonte}
    campos_invalidos = campos_invalidos_identidade(identidade)
    if campos_invalidos:
        parametros = {"inst_id": inst_id_int, "sid": sid_int, "serial": serial_int}
        id_evento = uuid.uuid4().hex
        registro = _montar_registro_recusa_pre_hitl(parametros, campos_invalidos, id_evento)
        try:
            _gravar_linha_jsonl_duravel(_caminho_log_efetivo(caminho_log), registro)
        except Exception as exc:
            logger.error(
                f"AUDITORIA HITL: FALHA AO GRAVAR {FASE_RECUSA_PRE_HITL} | id_intervencao={id_evento} | "
                f"erro={type(exc).__name__} errno={getattr(exc, 'errno', None)} | registro="
                + _serializar_para_log(registro)
            )
        logger.warning(
            f"HITL RECUSADO LOCALMENTE: PARAM_INVALIDO (identidade do alvo) | inst_id={inst_id_int}, "
            f"sid={sid_int}, serial={serial_int} | campos={campos_invalidos} | id_intervencao={id_evento}"
        )
        mensagem = (
            "Identidade do alvo lida na GV$SESSION fora do formato esperado; aprovação não solicitada e "
            f"encerramento NÃO executado. Campos inválidos: {', '.join(campos_invalidos)}."
        )
        return {
            "requer_aprovacao": False,
            "motivo": "PARAM_INVALIDO",
            "mensagem": mensagem,
            "resultado_tool": json.dumps(
                {
                    "status": "recusado",
                    "motivo": "PARAM_INVALIDO",
                    "status_banco": "PARAM_INVALIDO",
                    "mensagem": mensagem,
                },
                ensure_ascii=False,
            ),
        }

    timestamp = datetime.now(timezone.utc).isoformat()
    payload, hash_identidade = gerar_payload_e_hash_aprovacao(
        ferramenta=ferramenta,
        parametros={"inst_id": inst_id_int, "sid": sid_int, "serial": serial_int},
        alvo=alvo,
        timestamp=timestamp,
    )
    return {
        "requer_aprovacao": True,
        "motivo": None,
        "inst_id": inst_id_int,
        "sid": sid_int,
        "serial": serial_int,
        "alvo": alvo,
        "hash_identidade": hash_identidade,
        "payload": payload,
        "timestamp": timestamp,
    }


def conduzir_kill_hitl(
    argumentos: Dict[str, Any],
    solicitar_aprovacao: Callable[[Dict[str, Any]], Tuple[str, str, Optional[str]]],
    canal: str,
    caminho_log: Optional[Path] = None,
    agora: Optional[Callable[[], datetime]] = None,
) -> Dict[str, Any]:
    """
    Fluxo síncrono completo (usado pela CLI): preparar -> solicitar aprovação -> registrar decisão.
    A validade da aprovação é medida em registrar_decisao_kill, logo após o retorno de
    solicitar_aprovacao (relógio injetável via agora).

    solicitar_aprovacao recebe o resultado de preparar_intervencao_kill e devolve
    (decisao, aprovador, motivo). Só é chamado quando o alvo é elegível; recusas da
    pré-consulta (PARAM_INVALIDO, ALVO_NAO_ENCONTRADO, NAO_USUARIO, USUARIO_PROTEGIDO, ...)
    retornam sem prompt e sem chamada à conta KILL.
    """
    prep = preparar_intervencao_kill(argumentos, caminho_log=caminho_log)
    if not prep["requer_aprovacao"]:
        return {
            "prompt_exibido": False,
            "decisao": None,
            "resultado_banco": None,
            "executado": False,
            "motivo": prep["motivo"],
            "resultado_tool": prep["resultado_tool"],
            "registro": None,
            "falha_registro": None,
            "id_intervencao": None,
            "resultado_desconhecido": False,
            "assunto_email": None,
            "email_enviado": None,
            "email_detalhe": None,
        }

    decisao, aprovador, motivo = solicitar_aprovacao(prep)
    desfecho = registrar_decisao_kill(
        decisao=decisao,
        aprovador=aprovador,
        inst_id=prep["inst_id"],
        sid=prep["sid"],
        serial=prep["serial"],
        alvo=prep["alvo"],
        hash_aprovado=prep["hash_identidade"],
        canal=canal,
        preparado_em=prep["timestamp"],
        motivo=motivo,
        caminho_log=caminho_log,
        agora=agora,
    )
    desfecho["prompt_exibido"] = True
    desfecho["aprovador"] = (aprovador or "").strip()
    return desfecho


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
                "Encerra uma sessão de usuário no banco de dados através do procedimento homologado "
                "de encerramento. Requer aprovação humana prévia (HITL)."
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

# R1 ampliada V8 (decisao_c1.md §1 e §3.3): nomes das ferramentas Oracle. Desde a fase 2 (K2) o catálogo, o despacho
# e o histórico derivam de CLASSIFICACAO_FERRAMENTAS; esta constante fica para os testes (nenhuma Oracle liberada).
NOMES_FERRAMENTAS_ORACLE = frozenset(f["function"]["name"] for f in oracle_tools_schema)
