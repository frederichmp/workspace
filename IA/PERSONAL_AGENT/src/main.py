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
