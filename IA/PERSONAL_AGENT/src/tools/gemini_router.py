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
