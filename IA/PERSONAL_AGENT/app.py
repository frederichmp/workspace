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

# Carga única do .env (isolamento do .env, D1/D2), antes de qualquer import do projeto; roda a cada rerun.
# override=False: variável definida no shell vence o arquivo (decisão 2a). Nenhum módulo recarrega o .env;
# alterar o .env exige reiniciar a Web (decisão 2b).
# ORACLE_SANDBOX só vale se definida pelo operador no shell (incidente 01:27): se vier do arquivo, é
# descartada aqui; o WARNING sai depois do logging.basicConfig (antes dele, a configuração seria implícita).
_ORACLE_SANDBOX_DO_SHELL = "ORACLE_SANDBOX" in os.environ
load_dotenv(ROOT_DIR / ".env", override=False)
_ORACLE_SANDBOX_DESCARTADA = False
if not _ORACLE_SANDBOX_DO_SHELL and "ORACLE_SANDBOX" in os.environ:
    del os.environ["ORACLE_SANDBOX"]
    _ORACLE_SANDBOX_DESCARTADA = True

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
if _ORACLE_SANDBOX_DESCARTADA:
    logging.getLogger(__name__).warning(
        "ORACLE_SANDBOX encontrada no .env foi DESCARTADA: só vale quando definida pelo operador no shell."
    )

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
    preparar_intervencao_kill,
    registrar_decisao_kill,
    reconciliar_intencoes_orfas,
    APROVACAO_TTL_SEGUNDOS,
    MENSAGEM_RESULTADO_DESCONHECIDO,
)
from tools.gemini_router import (
    gemini_tools_schema,
    analisar_log_complexo,
)
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
            # BARREIRA HITL BASEADA EM ESTADO COM PRÉ-CONSULTA DIAG E TRILHA
            # ------------------------------------------------------------------
            if nome_funcao == "matar_sessao_oracle":
                # Validação (sem conexão), pré-consulta DIAG (existência, TYPE, usuário
                # protegido) e hash de identidade: tools.oracle_dba.preparar_intervencao_kill
                yield (
                    f"🔍 Validando parâmetros e consultando sessão `inst_id={argumentos.get('inst_id')}, "
                    f"sid={argumentos.get('sid')}, serial={argumentos.get('serial')}` via DIAG..."
                )
                prep = preparar_intervencao_kill(argumentos, ferramenta=nome_funcao)

                if not prep["requer_aprovacao"]:
                    st.session_state.llm_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": nome_funcao,
                            "content": prep["resultado_tool"],
                        }
                    )
                    detalhe = json.loads(prep["resultado_tool"]).get("mensagem", "")
                    yield (
                        f"⚠️ **Alvo Recusado ({prep['motivo']}):** {detalhe} "
                        "Ação cancelada sem solicitação de aprovação."
                    )
                    continue

                inst_id_int, sid_int, serial_int = prep["inst_id"], prep["sid"], prep["serial"]
                dados_alvo = prep["alvo"]
                hash_sha256 = prep["hash_identidade"]
                ts_aprovacao = prep["timestamp"]

                calls_restantes = mensagem_resposta.tool_calls[idx + 1 :]
                st.session_state.hitl_pendente = {
                    "tool_call_id": tool_call.id,
                    "nome_funcao": nome_funcao,
                    "inst_id": inst_id_int,
                    "sid": sid_int,
                    "serial": serial_int,
                    "dados_alvo": dados_alvo,
                    "hash_payload": hash_sha256,
                    "timestamp": ts_aprovacao,
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
                    f"🛑 **BARREIRA HITL ATIVADA:** Sessão identificada na GV$SESSION "
                    f"(Usuário: `{dados_alvo.get('username')}`, Programa: `{dados_alvo.get('program')}`). "
                    f"Aguardando autorização formal no painel abaixo..."
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


def processar_decisao_hitl(aprovado: bool, id_aprovador: str = "") -> bool:
    """
    Processa a decisão formal de aprovação ou rejeição da intervenção HITL.
    Exige identificação do aprovador para aprovação, gera log formal sem senhas,
    executa matar_sessao_oracle via PKG_OPS_KILL e retoma o orquestrador.
    """
    if not st.session_state.hitl_pendente:
        return True
    pendencia = dict(st.session_state.hitl_pendente)

    sid = pendencia["sid"]
    serial = pendencia["serial"]
    inst_id = pendencia["inst_id"]  # sempre gravado na pendência; sem valor padrão
    tool_call_id = pendencia["tool_call_id"]
    nome_funcao = pendencia["nome_funcao"]
    dados_alvo = pendencia.get("dados_alvo", {})
    hash_payload = pendencia.get("hash_payload", "")

    id_aprovador_limpo = id_aprovador.strip()

    if aprovado and not id_aprovador_limpo:
        st.error("Identificação do aprovador é obrigatória (não pode ser vazia).")
        return False

    # Item 1 (1c): a pendência já foi copiada; limpa antes da chamada para que um novo clique
    # (ou um rerun) nunca reaproveite a mesma aprovação.
    st.session_state.hitl_pendente = None

    # Decisão (humana) e resultado_banco (execução) são registrados separadamente
    try:
        desfecho = registrar_decisao_kill(
            decisao="APROVADO" if aprovado else "REJEITADO",
            aprovador=id_aprovador_limpo,
            inst_id=inst_id,
            sid=sid,
            serial=serial,
            alvo=dados_alvo,
            hash_aprovado=hash_payload,
            canal="Web UI",
            preparado_em=pendencia.get("timestamp"),  # validade medida no clique; ausente -> TIMEOUT
        )
    except Exception as exc:
        logging.error(f"ERRO interno no fluxo de kill (Web UI): {type(exc).__name__}")
        texto_erro = (
            f"❌ **Erro interno no fluxo de kill da sessão `{sid},{serial}`: estado desconhecido.** "
            "Consulte OPS_KILL_AUDIT antes de qualquer nova tentativa."
        )
        st.error(texto_erro)
        st.session_state.llm_messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": nome_funcao,
                "content": json.dumps(
                    {
                        "status": "erro",
                        "executado": None,
                        "mensagem": "Erro interno no fluxo de kill; estado desconhecido; consulte OPS_KILL_AUDIT.",
                    },
                    ensure_ascii=False,
                ),
            }
        )
        for call_extra in pendencia.get("calls_restantes", []):
            st.session_state.llm_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_extra["id"],
                    "name": call_extra["name"],
                    "content": json.dumps({"status": "cancelado_por_barreira_hitl"}),
                }
            )
        st.session_state.messages.append({"role": "assistant", "content": texto_erro})
        return True
    resultado_tool = desfecho["resultado_tool"]

    if desfecho["decisao"] == "TIMEOUT":
        aviso_ui = (
            f"⏱️ **Aprovação expirada (`{id_aprovador_limpo}`):** a pendência da sessão `{sid},{serial}` "
            f"passou do prazo de {APROVACAO_TTL_SEGUNDOS} s. Nenhuma execução no banco. "
            "Peça ao agente para reconsultar a sessão."
        )
    elif desfecho["decisao"] != "APROVADO":
        aprovador_registro = id_aprovador_limpo or "NAO_INFORMADO"
        aviso_ui = (
            f"🛑 **Ação Abortada pelo Aprovador (`{aprovador_registro}`):** "
            f"O encerramento da sessão `{sid},{serial}` foi negado. Nenhuma execução no banco."
        )
    elif desfecho.get("motivo") == "FALHA_LOG_APROVACAO":
        aviso_ui = (
            f"❌ **Intervenção APROVADA por `{id_aprovador_limpo}`, mas NÃO EXECUTADA:** falha ao gravar o "
            "registro de aprovação (FALHA_LOG_APROVACAO). Nenhuma chamada à conta KILL foi feita. "
            f"Incidente registrado no log da aplicação (id_intervencao=`{desfecho.get('id_intervencao')}`)."
        )
        st.error(aviso_ui)
    elif desfecho.get("resultado_desconhecido"):
        aviso_ui = (
            f"❌ **Intervenção aprovada por `{id_aprovador_limpo}`: {MENSAGEM_RESULTADO_DESCONHECIDO}** "
            f"(erro do Oracle a partir da chamada ao PKG; resultado: `{desfecho['resultado_banco']}`). "
            f"*(Notificação SMTP: {desfecho['email_detalhe']})*"
        )
        st.error(aviso_ui)
    elif desfecho["executado"]:
        aviso_ui = (
            f"✅ **Intervenção aprovada por `{id_aprovador_limpo}` e executada com sucesso** via PKG_OPS_KILL "
            f"(resultado do banco: `{desfecho['resultado_banco']}`). "
            f"*(Notificação SMTP: {desfecho['email_detalhe']})*"
        )
    else:
        aviso_ui = (
            f"⚠️ **Intervenção aprovada por `{id_aprovador_limpo}`, mas NÃO executada** "
            f"(resultado: `{desfecho['resultado_banco']}`). "
            f"*(Notificação SMTP: {desfecho['email_detalhe']})*"
        )

    if desfecho.get("falha_registro") == "RESULTADO":
        alerta_registro = (
            "❌ **ATENÇÃO: a linha RESULTADO não foi gravada em kill_approval.log;** registro completo no "
            f"log da aplicação (CRITICAL), id_intervencao=`{desfecho.get('id_intervencao')}`."
        )
        st.error(alerta_registro)
        aviso_ui = f"{aviso_ui}\n\n{alerta_registro}"

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
    return True


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

# Reconciliador na subida (uma vez por sessão do navegador; idempotente): INTENCAO sem RESULTADO
# mais antiga que o TTL + margem vira NAO_CONCLUIDA. Falha não derruba a interface.
if "reconciliacao_kill" not in st.session_state:
    try:
        st.session_state.reconciliacao_kill = reconciliar_intencoes_orfas()
    except Exception as exc:
        logging.error(f"Reconciliação do log de aprovações não executada: {type(exc).__name__}")
        st.session_state.reconciliacao_kill = {"erro": type(exc).__name__, "reconciliadas": []}

if st.session_state.reconciliacao_kill.get("erro"):
    st.warning(
        "⚠️ Reconciliação do log de aprovações NÃO executada "
        f"({st.session_state.reconciliacao_kill['erro']})."
    )
for _id_reconciliado in st.session_state.reconciliacao_kill.get("reconciliadas", []):
    st.warning(
        f"⚠️ Intervenção não concluída (INTENCAO sem RESULTADO), id_intervencao=`{_id_reconciliado}`. "
        "Conferir OPS_KILL_AUDIT."
    )


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
            alvo = pend.get("dados_alvo", {})
            st.error(
                f"🚨 **BARREIRA DE SEGURANÇA (HITL) — APROVAÇÃO OBRIGATÓRIA**\n\n"
                f"⚠️ **ATENÇÃO: A SESSÃO SERÁ ENCERRADA IMEDIATAMENTE (KILL SESSION IMMEDIATE).**\n\n"
                f"**Ação Solicitada:** `{pend['nome_funcao']}` via procedure `OPS_OWNER.PKG_OPS_KILL.KILL_SESSION` na instância `{dsn_atual}`.\n\n"
                f"**Dados da Sessão Alvo (GV$SESSION):**\n"
                f"- **Instância / SID / Serial#:** `inst_id={alvo.get('inst_id')}`, `sid={alvo.get('sid')}`, `serial#={alvo.get('serial#')}`\n"
                f"- **Usuário Oracle:** `{alvo.get('username')}`\n"
                f"- **Programa / Máquina:** `{alvo.get('program')}` / `{alvo.get('machine')}`\n"
                f"- **Status Atual:** `{alvo.get('status')}`\n"
                f"- **SQL ID:** `{alvo.get('sql_id')}`\n"
                f"- **Evento de Espera:** `{alvo.get('event')}`\n\n"
                f"🔒 **Hash SHA-256 de identidade do alvo** (inst_id, sid, serial#, username, program, machine; "
                f"reconferido antes da execução): `{pend.get('hash_payload')}`\n\n"
                f"Ao aprovar, um alerta de governança será disparado por e-mail para `{email_dest}`."
            )
            id_aprovador_input = st.text_input(
                "Identificação do Aprovador (obrigatório, ex: dba_nome):",
                key="input_hitl_aprovador",
            )
            btn_col_aprovar, btn_col_abortar = st.columns(2)
            with btn_col_aprovar:
                if st.button(
                    "✅ Aprovar Execução",
                    type="primary",
                    use_container_width=True,
                    key="btn_hitl_approve",
                ):
                    if not id_aprovador_input.strip():
                        st.warning("Informe a identificação do aprovador antes de confirmar a execução.")
                    else:
                        with st.spinner("Registrando aprovação e executando PKG_OPS_KILL no Oracle..."):
                            if processar_decisao_hitl(aprovado=True, id_aprovador=id_aprovador_input):
                                st.rerun()
            with btn_col_abortar:
                if st.button(
                    "🛑 Abortar",
                    type="secondary",
                    use_container_width=True,
                    key="btn_hitl_abort",
                ):
                    with st.spinner("Registrando bloqueio na auditoria e notificando o Agente..."):
                        processar_decisao_hitl(aprovado=False, id_aprovador=id_aprovador_input)
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
