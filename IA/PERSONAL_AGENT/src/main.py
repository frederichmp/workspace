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
from datetime import datetime, timezone
from tools.oracle_dba import (
    oracle_tools_schema,
    coletar_sessoes_ativas,
    coletar_top_sql,
    coletar_plano_execucao,
    consultar_alvo_sessao_diag,
    gerar_payload_e_hash_aprovacao,
    registrar_decisao_kill,
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
                    inst_id = argumentos.get("inst_id", 1)

                    # 1. Validação local antes de qualquer consulta ou conexão: inteiros positivos
                    try:
                        inst_id_val = int(inst_id)
                        sid_val = int(sid)
                        serial_val = int(serial)
                        if inst_id_val <= 0 or sid_val <= 0 or serial_val <= 0:
                            raise ValueError()
                    except (ValueError, TypeError):
                        resultado_tool = json.dumps(
                            {
                                "status": "recusado",
                                "motivo": "PARAM_INVALIDO",
                                "status_banco": "PARAM_INVALIDO",
                                "mensagem": (
                                    f"Parâmetros inválidos: inst_id={inst_id}, sid={sid}, serial={serial}. "
                                    "Devem ser inteiros estritamente positivos (> 0)."
                                ),
                            },
                            ensure_ascii=False,
                        )
                        print(f"[Sistema]: Parâmetros inválidos recusados localmente (PARAM_INVALIDO).")
                        logging.warning(f"HITL RECUSADO LOCALMENTE: PARAM_INVALIDO | inst_id={inst_id}, sid={sid}, serial={serial}")
                        # Devolve o resultado diretamente sem prosseguir para aprovação
                        st_p = None
                    else:
                        # 2. Consulta prévia do alvo pela conta DIAG na GV$SESSION
                        print(f"[Sistema]: Consultando alvo inst_id={inst_id_val}, sid={sid_val}, serial={serial_val} via DIAG...")
                        check_alvo = consultar_alvo_sessao_diag(
                            inst_id=inst_id_val, sid=sid_val, serial=serial_val
                        )

                        if not check_alvo.get("elegivel"):
                            motivo_falha = check_alvo.get("motivo", "ALVO_NAO_ENCONTRADO")
                            resultado_tool = json.dumps(
                                {
                                    "status": "recusado",
                                    "motivo": motivo_falha,
                                    "status_banco": motivo_falha,
                                    "mensagem": check_alvo.get(
                                        "mensagem",
                                        "Sessão alvo não encontrada na GV$SESSION.",
                                    ),
                                },
                                ensure_ascii=False,
                            )
                            print(f"[Sistema]: Alvo recusado ({motivo_falha}). Ação cancelada sem solicitação de aprovação.")
                            logging.warning(
                                f"HITL CANCELADO: Alvo recusado na pré-consulta GV$SESSION | "
                                f"inst_id={inst_id_val}, sid={sid_val}, serial={serial_val} | Motivo={motivo_falha}"
                            )
                        else:
                            alvo_dados = check_alvo["alvo"]
                            timestamp_str = datetime.now(timezone.utc).isoformat()
                            payload_dict, hash_sha256 = gerar_payload_e_hash_aprovacao(
                                ferramenta=nome_funcao,
                                parametros={"inst_id": inst_id_val, "sid": sid_val, "serial": serial_val},
                                alvo=alvo_dados,
                                timestamp=timestamp_str,
                            )

                            # Exibe detalhes do alvo e aviso explícito de encerramento imediato
                            print("\n" + "=" * 70)
                            print("\033[91m[ALERTA CRÍTICO DE SEGURANÇA - INTERVENÇÃO HITL]\033[0m")
                            print("A SESSÃO SERÁ ENCERRADA IMEDIATAMENTE (KILL SESSION IMMEDIATE).")
                            print("=" * 70)
                            print(f"Ação Solicitada : {nome_funcao}")
                            print(f"Alvo Identificado: inst_id={alvo_dados.get('inst_id')}, sid={alvo_dados.get('sid')}, serial#={alvo_dados.get('serial#')}")
                            print(f"Usuário Oracle  : {alvo_dados.get('username')}")
                            print(f"Programa/Máquina: {alvo_dados.get('program')} / {alvo_dados.get('machine')}")
                            print(f"Status Atual    : {alvo_dados.get('status')}")
                            print(f"SQL ID          : {alvo_dados.get('sql_id')}")
                            print(f"Evento Espera   : {alvo_dados.get('event')}")
                            print(f"Hash SHA-256    : {hash_sha256}")
                            print("=" * 70)

                            # Exige identificação do aprovador
                            id_aprovador = input("Informe sua identificação de aprovador (obrigatório, ex: dba_nome): ").strip()

                            if not id_aprovador:
                                decisao_humana, motivo_decisao = "REJEITADO", "SEM_IDENTIFICACAO"
                                print("\033[93m[Recusa]: Identificação do aprovador é obrigatória. Intervenção cancelada.\033[0m")
                            else:
                                confirmacao = input(
                                    f"Confirma o encerramento imediato da sessão pelo aprovador '{id_aprovador}'? [S/N]: "
                                ).strip().upper()
                                if confirmacao == "S":
                                    decisao_humana, motivo_decisao = "APROVADO", None
                                else:
                                    decisao_humana, motivo_decisao = "REJEITADO", "REJEITADO_PELO_APROVADOR"

                            # Decisão (humana) e resultado_banco (execução) são registrados separadamente
                            desfecho = registrar_decisao_kill(
                                decisao=decisao_humana,
                                aprovador=id_aprovador,
                                inst_id=inst_id_val,
                                sid=sid_val,
                                serial=serial_val,
                                alvo=alvo_dados,
                                hash_aprovado=hash_sha256,
                                canal="CLI",
                                motivo=motivo_decisao,
                            )
                            resultado_tool = desfecho["resultado_tool"]

                            if desfecho["decisao"] != "APROVADO":
                                print(f"[Sistema]: Intervenção NÃO aprovada ({desfecho['motivo']}). Nenhuma execução no banco.")
                            elif desfecho["executado"]:
                                print(
                                    f"[Sistema]: Intervenção APROVADA por '{id_aprovador}' e EXECUTADA COM SUCESSO "
                                    f"(resultado do banco: {desfecho['resultado_banco']})."
                                )
                            else:
                                print(
                                    f"\033[93m[Sistema]: Intervenção APROVADA por '{id_aprovador}', mas NÃO EXECUTADA "
                                    f"(resultado: {desfecho['resultado_banco']}).\033[0m"
                                )
                            if desfecho["assunto_email"]:
                                print(f"[Sistema]: Notificação por e-mail ({desfecho['assunto_email']}): {desfecho['email_detalhe']}")

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
