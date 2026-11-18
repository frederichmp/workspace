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

# Carga única do .env (isolamento do .env, D1/D2), antes de qualquer import do projeto.
# override=False: variável definida no shell vence o arquivo (decisão 2a). Nenhum módulo recarrega o .env;
# alterar o .env exige reiniciar a CLI (decisão 2b).
# ORACLE_SANDBOX só vale se definida pelo operador no shell (incidente 01:27): se vier do arquivo, é
# descartada aqui; o WARNING sai depois do logging.basicConfig (antes dele, a configuração seria implícita).
_ORACLE_SANDBOX_DO_SHELL = "ORACLE_SANDBOX" in os.environ
load_dotenv(ROOT_DIR / ".env", override=False)
_ORACLE_SANDBOX_DESCARTADA = False
if not _ORACLE_SANDBOX_DO_SHELL and "ORACLE_SANDBOX" in os.environ:
    del os.environ["ORACLE_SANDBOX"]
    _ORACLE_SANDBOX_DESCARTADA = True

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
if _ORACLE_SANDBOX_DESCARTADA:
    logging.getLogger(__name__).warning(
        "ORACLE_SANDBOX encontrada no .env foi DESCARTADA: só vale quando definida pelo operador no shell."
    )

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
    conduzir_kill_hitl,
    reconciliar_intencoes_orfas,
    APROVACAO_TTL_SEGUNDOS,
    MENSAGEM_RESULTADO_DESCONHECIDO,
)

# 3. Importando a Ferramenta de Nuvem (Gemini), o Notificador SMTP e a Busca RAG Local
from tools.gemini_router import (
    gemini_tools_schema,
    analisar_log_complexo,
)
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


def _solicitar_aprovacao_cli(prep: dict) -> tuple[str, str, str | None]:
    """
    Prompt HITL da CLI. Chamado por conduzir_kill_hitl apenas para alvo elegível.
    Retorna (decisao, aprovador, motivo).
    """
    alvo_dados = prep["alvo"]
    print("\n" + "=" * 70)
    print("\033[91m[ALERTA CRÍTICO DE SEGURANÇA - INTERVENÇÃO HITL]\033[0m")
    print("A SESSÃO SERÁ ENCERRADA IMEDIATAMENTE (KILL SESSION IMMEDIATE).")
    print("=" * 70)
    print("Ação Solicitada : matar_sessao_oracle")
    print(f"Alvo Identificado: inst_id={alvo_dados.get('inst_id')}, sid={alvo_dados.get('sid')}, serial#={alvo_dados.get('serial#')}")
    print(f"Usuário Oracle  : {alvo_dados.get('username')}")
    print(f"Programa/Máquina: {alvo_dados.get('program')} / {alvo_dados.get('machine')}")
    print(f"Status Atual    : {alvo_dados.get('status')}")
    print(f"SQL ID          : {alvo_dados.get('sql_id')}")
    print(f"Evento Espera   : {alvo_dados.get('event')}")
    print(f"Hash identidade : {prep['hash_identidade']}  (reconferido antes da execução)")
    print("=" * 70)

    id_aprovador = input("Informe sua identificação de aprovador (obrigatório, ex: dba_nome): ").strip()
    if not id_aprovador:
        print("\033[93m[Recusa]: Identificação do aprovador é obrigatória. Intervenção cancelada.\033[0m")
        return "REJEITADO", "", "SEM_IDENTIFICACAO"

    confirmacao = input(
        f"Confirma o encerramento imediato da sessão pelo aprovador '{id_aprovador}'? [S/N]: "
    ).strip().upper()
    if confirmacao == "S":
        return "APROVADO", id_aprovador, None
    return "REJEITADO", id_aprovador, "REJEITADO_PELO_APROVADOR"


def _exibir_desfecho_kill_cli(desfecho: dict) -> None:
    """Mensagens de tela que diferenciam recusa, aprovado-e-executado e aprovado-sem-execução."""
    if not desfecho.get("prompt_exibido"):
        print(f"[Sistema]: Alvo recusado ({desfecho['motivo']}). Ação cancelada sem solicitação de aprovação.")
    elif desfecho["decisao"] == "TIMEOUT":
        print(
            f"[Sistema]: Aprovação EXPIRADA (mais de {APROVACAO_TTL_SEGUNDOS} s desde a preparação). "
            "Nenhuma execução no banco. Solicite novamente."
        )
    elif desfecho["decisao"] != "APROVADO":
        print(f"[Sistema]: Intervenção NÃO aprovada ({desfecho['motivo']}). Nenhuma execução no banco.")
    elif desfecho.get("motivo") == "FALHA_LOG_APROVACAO":
        print(
            f"\033[91m[Sistema]: Intervenção APROVADA por '{desfecho['aprovador']}', mas NÃO EXECUTADA: "
            "falha ao gravar o registro de aprovação (FALHA_LOG_APROVACAO). "
            "Nenhuma chamada à conta KILL foi feita. Incidente registrado no log da aplicação "
            f"(id_intervencao={desfecho.get('id_intervencao')}).\033[0m"
        )
    elif desfecho.get("resultado_desconhecido"):
        print(
            f"\033[91m[Sistema]: Intervenção APROVADA por '{desfecho['aprovador']}': "
            f"{MENSAGEM_RESULTADO_DESCONHECIDO} (erro do Oracle a partir da chamada ao PKG; "
            f"resultado: {desfecho['resultado_banco']}).\033[0m"
        )
    elif desfecho["executado"]:
        print(
            f"[Sistema]: Intervenção APROVADA por '{desfecho['aprovador']}' e EXECUTADA COM SUCESSO "
            f"(resultado do banco: {desfecho['resultado_banco']})."
        )
    else:
        print(
            f"\033[93m[Sistema]: Intervenção APROVADA por '{desfecho['aprovador']}', mas NÃO EXECUTADA "
            f"(resultado: {desfecho['resultado_banco']}).\033[0m"
        )
    if desfecho.get("falha_registro") == "RESULTADO":
        print(
            "\033[91m[Sistema]: ATENÇÃO: a linha RESULTADO não foi gravada em kill_approval.log; "
            "registro completo no log da aplicação (CRITICAL), "
            f"id_intervencao={desfecho.get('id_intervencao')}.\033[0m"
        )
    if desfecho.get("assunto_email"):
        print(f"[Sistema]: Notificação por e-mail ({desfecho['assunto_email']}): {desfecho['email_detalhe']}")


MENSAGEM_ERRO_INTERNO_KILL = "ERRO interno no fluxo de kill; estado desconhecido"


def _reconciliar_na_subida_cli() -> None:
    """Reconciliador na subida: INTENCAO sem RESULTADO antiga vira NAO_CONCLUIDA. Nunca levanta exceção."""
    try:
        resumo = reconciliar_intencoes_orfas()
    except Exception as exc:
        logging.error(f"Reconciliação do log de aprovações não executada: {type(exc).__name__}")
        print(
            "\033[93m[Sistema]: Reconciliação do log de aprovações NÃO executada "
            f"({type(exc).__name__}).\033[0m"
        )
        return
    for id_reg in resumo["reconciliadas"]:
        print(
            f"\033[93m[Sistema]: Intervenção não concluída (INTENCAO sem RESULTADO), id_intervencao={id_reg}. "
            "Conferir OPS_KILL_AUDIT.\033[0m"
        )


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
                    # Validação, pré-consulta DIAG, prompt (só para alvo elegível), reconsulta + hash
                    # antes da conta KILL e registro de decisao/resultado_banco: tools.oracle_dba
                    desfecho = conduzir_kill_hitl(
                        argumentos,
                        solicitar_aprovacao=_solicitar_aprovacao_cli,
                        canal="CLI",
                    )
                    resultado_tool = desfecho["resultado_tool"]
                    _exibir_desfecho_kill_cli(desfecho)

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
                if nome_funcao == "matar_sessao_oracle":
                    # Achado 9.3: erro no fluxo de kill não pode ser silencioso
                    logging.error(f"{MENSAGEM_ERRO_INTERNO_KILL}: {type(e).__name__}")
                    print(f"[Sistema]: {MENSAGEM_ERRO_INTERNO_KILL}")
                    resultado_tool = json.dumps(
                        {
                            "status": "erro",
                            "executado": None,
                            "mensagem": f"{MENSAGEM_ERRO_INTERNO_KILL}; consulte OPS_KILL_AUDIT.",
                        },
                        ensure_ascii=False,
                    )
                else:
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
    _reconciliar_na_subida_cli()

    # Teste 5: Busca RAG Local na Base de Scripts Homologados do DBA
    executar_agente(
        "Busque na nossa base de conhecimento interna um script SQL homologado para identificar bloqueios de linha (locks) mostrando o ROWID bloqueado."
    )
