"""Orquestrador Central do Personal Agent (Windows + Oracle DBA + Gemini Cloud Router + Barreira HITL & Notificador) com Auditoria Completa."""
import io
import json
import logging
import os
import socket
import stat
import sys
import threading
from pathlib import Path
from dotenv import dotenv_values, load_dotenv
from dotenv.parser import parse_stream
from openai import OpenAI

# Garante que os pacotes em src/ sejam resolvidos independentemente do diretório de execução
SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
for path_str in (str(ROOT_DIR), str(SRC_DIR)):
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

# >>> carga-env (texto idêntico em app.py e src/main.py; isolamento do .env, decisões em
# docs/entregas/isolamento_env/decisao_fase3.md, P1, e docs/entregas/isolamento_env/fase4/decisao_fase4.md)
# - Uma carga por processo, antes de qualquer import do projeto. O estado fica em sys (um por processo; sobrevive
#   aos reruns do Streamlit); toda transição e a leitura da decisão rodam sob o lock. Alterar o .env exige
#   reiniciar a CLI ou a Web.
# - Uma leitura do arquivo (os.stat + open), sob o lock; texto e valores só dentro de _carregar_env.
# - override=False: o ambiente (shell ou perfil) vence o arquivo.
# - ORACLE_SANDBOX só vale se já estava no ambiente antes da carga (incidente 01:27). Se vier do arquivo, o finally
#   a remove, inclusive quando a carga falha (C1); "ok" só é gravado depois disso.
# - OSError antes de qualquer escrita em os.environ (inclusive .env ausente): nada entrou, nova tentativa na
#   próxima subida. Qualquer outra falha (escrita parcial, .env que não é arquivo regular, decodificação, NUL,
#   interrupção): fail-closed até reiniciar o processo. Mensagens fixas, sem valores.
_AVISO_SANDBOX_DESCARTADA = (
    "ORACLE_SANDBOX encontrada no .env foi DESCARTADA: só vale quando definida pelo operador no shell. "
    "Remova a chave do .env."
)
_AVISO_SOMBREADAS = "Variáveis do .env ignoradas porque o ambiente já as define com outro valor: "
_AVISO_MALFORMADAS = "Linhas do .env com erro de sintaxe foram ignoradas. Quantidade: "


def _carregar_env(caminho):
    """Uma leitura do .env (sob o lock de quem chama). Texto e valores só aqui dentro.

    Devolve (estado, falha, sombreadas, malformadas). estado None: nada foi escrito em os.environ e a próxima
    subida tenta de novo. Escrita parcial seguida de OSError: a exceção sobe e quem chama marca "falhou"."""
    retrato = dict(os.environ)  # antes de qualquer escrita
    try:
        if not stat.S_ISREG(os.stat(caminho).st_mode):  # só os.stat: no Windows isfile/isdir usam atalhos fora dele
            return "falhou", "NaoEArquivoRegular", (), 0  # Achado 3: diretório, FIFO, dispositivo
        with open(caminho, encoding="utf-8") as arquivo:  # a única abertura do .env
            texto = arquivo.read()
        sombreadas = tuple(sorted(  # B3: só nomes, calculados antes da carga (ambiente ainda intacto)
            nome for nome, valor in dotenv_values(stream=io.StringIO(texto)).items()
            if valor is not None and nome in os.environ and os.environ[nome] != valor
        ))
        malformadas = sum(1 for linha in parse_stream(io.StringIO(texto)) if linha.error)  # só a contagem
        load_dotenv(stream=io.StringIO(texto), override=False)
    except OSError as exc:
        if dict(os.environ) != retrato:
            raise  # escrita parcial: fail-closed
        return None, type(exc).__name__, (), 0
    return "ok", None, sombreadas, malformadas


_ESTADO_ENV = vars(sys).setdefault(
    "_personal_agent_estado_env",
    {"lock": threading.Lock(), "estado": None, "falha": None, "sandbox_descartada": False, "sombreadas": (),
     "malformadas": 0},
)
_CARREGOU_AGORA = False
with _ESTADO_ENV["lock"]:
    if _ESTADO_ENV["estado"] is None:
        _ESTADO_ENV.update(estado="falhou", falha=None, sandbox_descartada=False, sombreadas=(), malformadas=0)
        _sandbox_do_shell = "ORACLE_SANDBOX" in os.environ
        _proximo = "falhou"
        try:
            _proximo, _ESTADO_ENV["falha"], _ESTADO_ENV["sombreadas"], _ESTADO_ENV["malformadas"] = (
                _carregar_env(ROOT_DIR / ".env")
            )
        except Exception as exc:
            _ESTADO_ENV["falha"] = type(exc).__name__
        finally:
            if not _sandbox_do_shell and os.environ.pop("ORACLE_SANDBOX", None) is not None:
                _ESTADO_ENV["sandbox_descartada"] = True
        _ESTADO_ENV["estado"] = _proximo  # só depois do descarte de ORACLE_SANDBOX
        _CARREGOU_AGORA = _proximo == "ok"
    _ESTADO_DESTA_SUBIDA, _FALHA_DESTA_SUBIDA = _ESTADO_ENV["estado"], _ESTADO_ENV["falha"]  # lidos sob o lock
if _ESTADO_DESTA_SUBIDA is None:
    raise RuntimeError(
        f"Carga do .env falhou nesta subida ({_FALHA_DESTA_SUBIDA}); nada do agente foi carregado e nada do .env "
        "entrou no ambiente. Nova tentativa na próxima subida (Web: recarregue a página; CLI: rode de novo)."
    )
if _ESTADO_DESTA_SUBIDA != "ok":
    raise RuntimeError(
        f"Carga do .env falhou nesta subida ({_FALHA_DESTA_SUBIDA or 'interrompida'}); "
        "nada do agente foi carregado. Corrija o .env e reinicie o processo."
    )
# <<< carga-env

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
if _CARREGOU_AGORA:  # avisos da carga: uma vez por processo, depois do basicConfig
    _log_carga = logging.getLogger(__name__)
    if _ESTADO_ENV["sandbox_descartada"]:
        _log_carga.warning(_AVISO_SANDBOX_DESCARTADA)
        # C3: visível ao operador mesmo com o logging suprimido (texto fixo, sem valores)
        print(f"[Sistema]: AVISO: {_AVISO_SANDBOX_DESCARTADA}", file=sys.stderr)
    if _ESTADO_ENV["sombreadas"]:  # B3: só nomes
        _log_carga.warning(_AVISO_SOMBREADAS + ", ".join(_ESTADO_ENV["sombreadas"]))
        print(f"[Sistema]: AVISO: {_AVISO_SOMBREADAS}{', '.join(_ESTADO_ENV['sombreadas'])}", file=sys.stderr)
    if _ESTADO_ENV["malformadas"]:  # Achado 3: só a contagem
        _log_carga.warning(_AVISO_MALFORMADAS + str(_ESTADO_ENV["malformadas"]))
        print(f"[Sistema]: AVISO: {_AVISO_MALFORMADAS}{_ESTADO_ENV['malformadas']}", file=sys.stderr)

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
    MENSAGEM_DESFECHO_NAO_CONFIRMADO,
    NOME_FERRAMENTA_KILL,
    NOMES_FERRAMENTAS_ORACLE,
    RESULTADO_KILL_DESABILITADO,
    RESULTADO_ORACLE_SO_LOCAL,
    TEXTO_HISTORICO_COM_DADO_DO_BANCO,
    _registrar_erro_local,
    ferramentas_do_coordenador,
    kill_habilitado,
    coordenador_e_local,
    historico_tem_dado_do_banco,
)

# 3. Gemini e Busca RAG Local
# R1 ampliada V9 (docs/plans/1.11-R1-ampliada.md §5.2.2; decisão do responsável de 2026-11-24, opção a): o
# analisar_log_complexo não é oferecido nem despachado ao coordenador. O import fica, sem uso, porque o
# tools.gemini_router lê GEMINI_API_KEY no import e é a sonda do test_d63 (carga do .env antes de tools.*).
import tools.gemini_router  # noqa: F401  (sonda da carga do .env; nenhuma função é usada)
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

# 4. Registro de Ferramentas da interface. O catálogo entregue ao LLM a cada chamada é
# ferramentas_do_coordenador(todas_ferramentas, local): sem OPS_KILL_PKG_VERSAO=2 o kill sai, e com o coordenador
# em nuvem saem as ferramentas Oracle (R1 ampliada V8; fase 2, decisao_c1.md §1.2 e §2.2-i).
todas_ferramentas = os_tools_schema + oracle_tools_schema + rag_tools_schema

# 5. System Prompt do Coordenador
SYSTEM_PROMPT = """Você é o Agente Coordenador, o cérebro central de um sistema autônomo local de administração de TI e Banco de Dados.
Seus princípios absolutos são:
1. Precisão acima de velocidade.
2. Evidência acima de opinião.

DIRETRIZES DE COMPORTAMENTO E DELEGAÇÃO:
- Nunca invente métricas, queries, logs ou estados do sistema. Chame as ferramentas.
- Para problemas simples, responda no formato: Diagnóstico, Evidências, Possíveis Causas e Próximo Passo.
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
    print(f"Logon (DATE)    : {alvo_dados.get('logon_time')}")
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
    elif desfecho.get("motivo") == "KILL_DESABILITADO":
        # Fase 2, decisao_c1.md §2.2-iii-b (tela): gate desligado depois do prompt.
        print(
            f"\033[91m[Sistema]: Intervenção aprovada por '{desfecho['aprovador']}', mas NÃO EXECUTADA: "
            "encerramento desabilitado nesta instalação (OPS_KILL_PKG_VERSAO); nenhuma consulta nem chamada "
            "à conta KILL.\033[0m"
        )
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
            f"{MENSAGEM_RESULTADO_DESCONHECIDO} ({MENSAGEM_DESFECHO_NAO_CONFIRMADO}; "
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

    # R1 ampliada V8 (decisao_c1.md §3.1): o sinal é o base_url do próprio cliente que envia.
    local = coordenador_e_local(client)

    # Loop de Tool Calling
    max_passos = 6
    passo = 0

    while passo < max_passos:
        passo += 1
        # V8, trava de histórico (decisao_c1.md §3.4): dado do banco nunca vai à nuvem.
        if not local and historico_tem_dado_do_banco(messages):
            print(f"\n[Sistema]: {TEXTO_HISTORICO_COM_DADO_DO_BANCO}")
            return
        response = client.chat.completions.create(
            model=MODELO,
            messages=messages,
            tools=ferramentas_do_coordenador(todas_ferramentas, local),
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
                or nome_funcao == "matar_sessao_oracle"
                or nome_funcao == "buscar_script_interno"
            ):
                logging.info(f"AGENTE ACIONOU: {nome_funcao} | PARÂMETROS: {argumentos}")

            # 3. Roteamento Dinâmico (Switch Case / If-Elif) com Barreira HITL + Notificador SMTP
            try:
                # V8, despacho (decisao_c1.md §3.3): o LLM pode chamar ferramenta que não foi oferecida; com o
                # coordenador em nuvem, ferramenta Oracle devolve a recusa fixa, sem consultar nada.
                if not local and nome_funcao in NOMES_FERRAMENTAS_ORACLE:
                    resultado_tool = RESULTADO_ORACLE_SO_LOCAL

                # Gate de produção do kill (fase 2, decisao_c1.md §2.2-ii): sem OPS_KILL_PKG_VERSAO=2, recusa fixa;
                # conduzir_kill_hitl não é chamado (sem pré-consulta e sem prompt).
                elif nome_funcao == NOME_FERRAMENTA_KILL and not kill_habilitado():
                    logging.warning("KILL BLOQUEADO NO DESPACHO (CLI): KILL_DESABILITADO (OPS_KILL_PKG_VERSAO)")
                    print("[Sistema]: Encerramento de sessão indisponível nesta instalação (OPS_KILL_PKG_VERSAO).")
                    resultado_tool = RESULTADO_KILL_DESABILITADO

                # Rotas do Windows
                elif nome_funcao == "coletar_metricas_hardware":
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
                    # R1 ampliada V3 (decisao_c1.md §2.3): ao LLM só o tipo; o texto cru vai ao log local.
                    _registrar_erro_local(nome_funcao, "erro_execucao", exc=e)
                    resultado_tool = json.dumps(
                        {"erro_execucao": type(e).__name__}, ensure_ascii=False
                    )

            # 4. Auditoria: Registra a evidência/resultado retornado pelo banco ou pelo bloqueio HITL
            if (
                nome_funcao.startswith("coletar_")
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
    if not local and historico_tem_dado_do_banco(messages):
        print(f"\n[Sistema]: {TEXTO_HISTORICO_COM_DADO_DO_BANCO}")
        return
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
