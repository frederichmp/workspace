"""
Módulo Executor Seguro de Scripts Oracle por script_id (TAREFA 1 & 1.1 & 1.2).
Aplica regras estritas de validação em ordem obrigatória (fail-fast sem conexão).
O LLM nunca envia SQL bruto; executa exclusivamente scripts homologados no registro.

NOTA DE GOVERNANÇA (D5):
No Oracle Database, DDL executa COMMIT implícito antes e depois da instrução. Portanto,
nenhuma alteração feita antes do DDL pode ser revertida por este executor. Se um DDL falhar
no meio de sua execução, o próprio Oracle reverte a instrução; não há rollback de múltiplas
instruções. O executor não promete atomicidade para DDL.
"""

import hashlib
import json
import os
import re
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import oracledb
from dotenv import load_dotenv

from src.tools.registry import (
    ScriptRegistryEntry,
    carregar_registro,
    obter_caminho_scripts_dir,
    obter_script,
)

# Carrega variáveis de ambiente
load_dotenv()
env_personal_agent = Path(__file__).resolve().parent.parent.parent / ".env"
if env_personal_agent.is_file():
    load_dotenv(dotenv_path=env_personal_agent, override=False)

# Constantes e Diretivas SQL*Plus a recusar terminantemente
SQLPLUS_DIRECTIVES = {
    "SET", "PROMPT", "SPOOL", "COL", "COLUMN", "CLEAR",
    "@", "@@", "START", "WHENEVER", "PAUSE", "CONNECT",
    "DISCONNECT", "DESC", "DESCRIBE"
}

LIMITE_PADRAO_SELECT = 50
LIMITE_PADRAO_LOB = 500


def _serializar_valor(valor: Any, limite_lob: int = LIMITE_PADRAO_LOB) -> Any:
    """Serializa valores Oracle para JSON, aplicando truncamento estrito em LOBs."""
    if valor is None:
        return None
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor) if "." in str(valor) else int(valor)
    if hasattr(valor, "read"):
        try:
            conteudo = valor.read()
            if isinstance(conteudo, bytes):
                conteudo = conteudo.decode("utf-8", errors="replace")
            else:
                conteudo = str(conteudo)
            if len(conteudo) > limite_lob:
                return conteudo[:limite_lob] + "... [LOB TRUNCADO]"
            return conteudo
        except Exception as e:
            return f"<Erro ao ler LOB: {str(e)}>"
    return valor


def tokenizar_sql_stream(raw_sql: str) -> List[Tuple[str, str]]:
    """Tokeniza SQL preservando strings, strings Q, identificadores e comentários."""
    i = 0
    n = len(raw_sql)
    tokens: List[Tuple[str, str]] = []

    while i < n:
        c = raw_sql[i]

        # Comentário de linha --
        if c == "-" and i + 1 < n and raw_sql[i + 1] == "-":
            start = i
            while i < n and raw_sql[i] not in ("\r", "\n"):
                i += 1
            tokens.append(("COMMENT_LINE", raw_sql[start:i]))
            continue

        # Comentário de bloco /* ... */
        if c == "/" and i + 1 < n and raw_sql[i + 1] == "*":
            start = i
            i += 2
            while i < n and not (raw_sql[i - 1] == "*" and raw_sql[i] == "/"):
                i += 1
            if i < n:
                i += 1
            tokens.append(("COMMENT_BLOCK", raw_sql[start:i]))
            continue

        # Literal Q: q'[...]', Q'(...)' etc.
        if c in ("q", "Q") and i + 1 < n and raw_sql[i + 1] == "'":
            start = i
            i += 2
            if i < n:
                open_delim = raw_sql[i]
                close_delim = {"[": "]", "{": "}", "(": ")", "<": ">"}.get(open_delim, open_delim)
                i += 1
                while i < n:
                    if raw_sql[i] == close_delim and i + 1 < n and raw_sql[i + 1] == "'":
                        i += 2
                        break
                    i += 1
                tokens.append(("STRING_Q", raw_sql[start:i]))
                continue

        # Literal de string padrão '...'
        if c == "'":
            start = i
            i += 1
            while i < n:
                if raw_sql[i] == "'":
                    if i + 1 < n and raw_sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            tokens.append(("STRING", raw_sql[start:i]))
            continue

        # Identificador com aspas duplas "..."
        if c == '"':
            start = i
            i += 1
            while i < n:
                if raw_sql[i] == '"':
                    if i + 1 < n and raw_sql[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            tokens.append(("IDENT_QUOTED", raw_sql[start:i]))
            continue

        # Espaços e quebras de linha
        if c.isspace():
            start = i
            while i < n and raw_sql[i].isspace():
                i += 1
            tokens.append(("WHITESPACE", raw_sql[start:i]))
            continue

        # Ponto e vírgula
        if c == ";":
            tokens.append(("SEMICOLON", ";"))
            i += 1
            continue

        # Barra isolada
        if c == "/":
            tokens.append(("SLASH", "/"))
            i += 1
            continue

        # Palavras ou identificadores alfanuméricos
        if c.isalnum() or c == "_":
            start = i
            while i < n and (raw_sql[i].isalnum() or raw_sql[i] == "_"):
                i += 1
            tokens.append(("WORD", raw_sql[start:i]))
            continue

        # Símbolos avulsos
        tokens.append(("SYMBOL", c))
        i += 1

    return tokens


def _analisar_blocos_plsql(tokens: List[Tuple[str, str]]) -> Tuple[bool, Optional[str], str]:
    """
    C1: Controle estrito de blocos PL/SQL com pilha de contexto.
    Aberturas: BEGIN, DECLARE, CASE, IF, LOOP
    Fechamentos: END, END IF, END LOOP, END CASE
    
    Após fechamento do bloco superior, qualquer token que não seja espaço, comentário ou ';'
    gera MULTIPLOS_STATEMENTS.
    Se não puder provar bloco único, recusa com PLSQL_AMBIGUO (default-deny).
    """
    sig_words = [t[1].upper() for t in tokens if t[0] == "WORD"]
    if sig_words and sig_words[0] == "CREATE":
        sub = [w for w in sig_words[1:6] if w not in ("OR", "REPLACE", "EDITIONABLE", "NONEDITIONABLE")]
        if sub and sub[0] in ("PACKAGE", "TYPE"):
            return False, "PLSQL_AMBIGUO", f"Estrutura CREATE {sub[0]} não possui bloco único comprovável (default-deny)."

    stack: List[str] = []
    top_level_started = False
    top_level_closed = False

    i = 0
    num_tokens = len(tokens)

    while i < num_tokens:
        t_type, t_val = tokens[i]

        if top_level_closed:
            # Qualquer token pós-fechamento que não seja espaço, comentário ou ';' é MULTIPLOS_STATEMENTS
            if t_type not in ("WHITESPACE", "COMMENT_LINE", "COMMENT_BLOCK", "SEMICOLON"):
                return False, "MULTIPLOS_STATEMENTS", f"Instrução ou token extra detectado após o término do bloco: '{t_val}'"
            i += 1
            continue

        if t_type != "WORD":
            i += 1
            continue

        word = t_val.upper()

        if word == "DECLARE":
            top_level_started = True
            if stack and stack[-1] == "DECLARE":
                return False, "PLSQL_AMBIGUO", "Múltiplas cláusulas DECLARE consecutivas sem bloco."
            stack.append("DECLARE")
            i += 1
            continue

        elif word == "BEGIN":
            top_level_started = True
            if stack and stack[-1] == "DECLARE":
                stack[-1] = "BEGIN"
            else:
                stack.append("BEGIN")
            i += 1
            continue

        elif word == "IF":
            if not top_level_started:
                return False, "PLSQL_AMBIGUO", "IF encontrado fora de bloco PL/SQL principal."
            stack.append("IF")
            i += 1
            continue

        elif word == "LOOP":
            if not top_level_started:
                return False, "PLSQL_AMBIGUO", "LOOP encontrado fora de bloco PL/SQL principal."
            stack.append("LOOP")
            i += 1
            continue

        elif word == "CASE":
            if not top_level_started:
                return False, "PLSQL_AMBIGUO", "CASE encontrado fora de bloco PL/SQL principal."
            stack.append("CASE")
            i += 1
            continue

        elif word == "END":
            if not stack:
                return False, "PLSQL_AMBIGUO", "Palavra-chave END encontrada sem abertura correspondente."

            # Verifica próximo token de palavra para identificar END IF, END LOOP, END CASE
            j = i + 1
            prox_palavra = None
            prox_palavra_idx = -1
            while j < num_tokens:
                if tokens[j][0] == "WORD":
                    prox_palavra = tokens[j][1].upper()
                    prox_palavra_idx = j
                    break
                elif tokens[j][0] in ("SEMICOLON", "SYMBOL"):
                    break
                j += 1

            if prox_palavra == "IF":
                if stack[-1] != "IF":
                    return False, "PLSQL_AMBIGUO", f"END IF encontrado mas bloco atual no topo é {stack[-1]}."
                stack.pop()
                i = prox_palavra_idx + 1
            elif prox_palavra == "LOOP":
                if stack[-1] != "LOOP":
                    return False, "PLSQL_AMBIGUO", f"END LOOP encontrado mas bloco atual no topo é {stack[-1]}."
                stack.pop()
                i = prox_palavra_idx + 1
            elif prox_palavra == "CASE":
                if stack[-1] != "CASE":
                    return False, "PLSQL_AMBIGUO", f"END CASE encontrado mas bloco atual no topo é {stack[-1]}."
                stack.pop()
                i = prox_palavra_idx + 1
            else:
                # END comum (fecha BEGIN ou CASE sem palavra CASE)
                if stack[-1] in ("BEGIN", "CASE"):
                    stack.pop()
                    if prox_palavra is not None and prox_palavra not in ("IF", "LOOP", "CASE"):
                        # Rótulo ou nome de rotina opcional (ex: END pr_nome; ou END bloco;)
                        i = prox_palavra_idx + 1
                    else:
                        i += 1
                else:
                    return False, "PLSQL_AMBIGUO", f"END encontrado para fechar bloco {stack[-1]} sem a devida terminação."

            if top_level_started and len(stack) == 0:
                top_level_closed = True
            continue

        i += 1

    if not top_level_started:
        return False, "PLSQL_AMBIGUO", "Nenhum bloco PL/SQL foi iniciado."
    if stack:
        return False, "PLSQL_AMBIGUO", f"Bloco PL/SQL não finalizado. Pilha remanescente: {stack}"
    if not top_level_closed:
        return False, "PLSQL_AMBIGUO", "Bloco PL/SQL não pôde ser comprovado como unitário."

    return True, None, "Bloco PL/SQL único e válido comprovado."


def verificar_diretivas_sqlplus(raw_sql: str, tokens: List[Tuple[str, str]]) -> Tuple[bool, Optional[str], str]:
    """
    D1: Detecta diretivas SQL*Plus apenas no início de statement e linha isolada '/':
    - Linha contendo somente '/' (política conservadora; ver caso A28).
    - Diretivas como primeiro token significativo de um statement:
      * SET, PROMPT, SPOOL, COL, COLUMN, CLEAR, WHENEVER, PAUSE, DESC, DESCRIBE -> DIRETIVA_SQLPLUS
      * START seguido de qualquer token que não seja WITH -> DIRETIVA_SQLPLUS
      * CONNECT seguido de qualquer token que não seja BY -> DIRETIVA_SQLPLUS
      * EXEC / EXECUTE seguido de algo que não seja BEGIN ou DECLARE -> DIRETIVA_SQLPLUS
      * '@' ou '@@' como primeiro caractere do statement -> DIRETIVA_SQLPLUS
    """
    # 1. Linha contendo somente '/'
    for num_linha, linha in enumerate(raw_sql.splitlines(), start=1):
        if linha.strip() == "/":
            return False, "DIRETIVA_SQLPLUS", f"Linha {num_linha}: Barra isolada '/' detectada."

    # 2. Varredura por statements para encontrar primeiro token significativo de cada statement
    sig_tokens = [(t_type, t_val) for t_type, t_val in tokens if t_type not in ("WHITESPACE", "COMMENT_LINE", "COMMENT_BLOCK")]
    if not sig_tokens:
        return True, None, ""

    primeira_palavra = sig_tokens[0][1].upper() if sig_tokens[0][0] in ("WORD", "IDENT_QUOTED") else ""

    # Determina se o primeiro statement é bloco PL/SQL
    eh_plsql_raiz = primeira_palavra in ("DECLARE", "BEGIN")
    if primeira_palavra == "CREATE":
        sub = [t[1].upper() for t in sig_tokens[1:6] if t[0] == "WORD" and t[1].upper() not in ("OR", "REPLACE", "EDITIONABLE", "NONEDITIONABLE")]
        if sub and sub[0] in ("PROCEDURE", "FUNCTION", "PACKAGE", "TRIGGER", "TYPE"):
            eh_plsql_raiz = True

    statement_starts = [0]
    if not eh_plsql_raiz:
        for idx, (t_type, t_val) in enumerate(sig_tokens):
            if t_type == "SEMICOLON" and idx + 1 < len(sig_tokens):
                statement_starts.append(idx + 1)

    for st_idx in statement_starts:
        if st_idx >= len(sig_tokens):
            continue
        t_type, t_val = sig_tokens[st_idx]

        # '@' ou '@@' como primeiro caractere do statement
        if t_type == "SYMBOL" and t_val.startswith("@"):
            return False, "DIRETIVA_SQLPLUS", f"Diretiva de inclusão de script '{t_val}' detectada no início do statement."
        if t_val in ("@", "@@"):
            return False, "DIRETIVA_SQLPLUS", f"Diretiva de inclusão de script '{t_val}' detectada no início do statement."

        if t_type == "WORD":
            w = t_val.upper()
            if w in ("SET", "PROMPT", "SPOOL", "COL", "COLUMN", "CLEAR", "WHENEVER", "PAUSE", "DESC", "DESCRIBE"):
                return False, "DIRETIVA_SQLPLUS", f"Diretiva SQL*Plus '{w}' detectada no início do statement."

            if w == "START":
                prox = sig_tokens[st_idx + 1][1].upper() if st_idx + 1 < len(sig_tokens) and sig_tokens[st_idx + 1][0] == "WORD" else ""
                if prox != "WITH":
                    return False, "DIRETIVA_SQLPLUS", "Diretiva SQL*Plus 'START' detectada no início do statement."

            if w == "CONNECT":
                prox = sig_tokens[st_idx + 1][1].upper() if st_idx + 1 < len(sig_tokens) and sig_tokens[st_idx + 1][0] == "WORD" else ""
                if prox != "BY":
                    return False, "DIRETIVA_SQLPLUS", "Diretiva SQL*Plus 'CONNECT' detectada no início do statement."

            if w in ("EXEC", "EXECUTE"):
                prox = sig_tokens[st_idx + 1][1].upper() if st_idx + 1 < len(sig_tokens) and sig_tokens[st_idx + 1][0] == "WORD" else ""
                if prox not in ("BEGIN", "DECLARE"):
                    return False, "DIRETIVA_SQLPLUS", f"Diretiva SQL*Plus '{w}' sem bloco autônomo detectada no início do statement."

    return True, None, ""


def determinar_tipo_real_sql(tokens: List[Tuple[str, str]]) -> Tuple[Optional[str], Optional[str]]:
    """
    D2: Determina o tipo real do comando SQL com mapeamento fixo e igualdade exata:
    - CREATE [OR REPLACE] PROCEDURE | FUNCTION | PACKAGE | PACKAGE BODY | TRIGGER | TYPE | TYPE BODY -> PLSQL
    - Demais CREATE, ALTER, DROP, TRUNCATE, RENAME, COMMENT, GRANT, REVOKE, ANALYZE, AUDIT, NOAUDIT -> DDL
    - SELECT ou WITH sem DML/DDL de nível superior -> SELECT
    - SELECT ou WITH com DML/DDL de nível superior -> TIPO_DIVERGENTE (tipo detectado: DML/DDL)
    - INSERT, UPDATE, DELETE, MERGE -> DML
    - DECLARE ou BEGIN -> PLSQL
    - Demais -> DESCONHECIDO (D3)
    """
    sig_words = [t[1].upper() for t in tokens if t[0] == "WORD"]
    if not sig_words:
        return None, "Script vazio ou contendo apenas comentários."

    primeira = sig_words[0]

    if primeira in ("SELECT", "WITH"):
        paren_depth = 0
        for t_type, t_val in tokens:
            if t_type == "SYMBOL":
                if t_val == "(":
                    paren_depth += 1
                elif t_val == ")":
                    paren_depth = max(paren_depth - 1, 0)
            elif t_type == "WORD" and paren_depth == 0:
                palavra_upper = t_val.upper()
                if palavra_upper in ("INSERT", "UPDATE", "DELETE", "MERGE"):
                    return "TIPO_DIVERGENTE", f"Comando {primeira} contém instrução DML ({palavra_upper}) de nível superior."
                if palavra_upper in ("DROP", "ALTER", "CREATE", "TRUNCATE", "RENAME"):
                    return "TIPO_DIVERGENTE", f"Comando {primeira} contém instrução DDL ({palavra_upper}) de nível superior."
        return "SELECT", None

    elif primeira in ("INSERT", "UPDATE", "DELETE", "MERGE"):
        return "DML", None

    elif primeira in ("DECLARE", "BEGIN"):
        return "PLSQL", None

    elif primeira == "CREATE":
        sub = [w for w in sig_words[1:6] if w not in ("OR", "REPLACE", "EDITIONABLE", "NONEDITIONABLE")]
        if sub and sub[0] in ("PROCEDURE", "FUNCTION", "PACKAGE", "TRIGGER", "TYPE"):
            return "PLSQL", None
        return "DDL", None

    elif primeira in ("ALTER", "DROP", "TRUNCATE", "RENAME", "COMMENT", "GRANT", "REVOKE", "ANALYZE", "AUDIT", "NOAUDIT"):
        return "DDL", None

    return "DESCONHECIDO", f"Comando com início '{primeira}' não categorizado."


def tokenizar_e_validar_sql(raw_sql: str) -> Tuple[bool, Optional[str], str, str, str]:
    """
    Tokeniza e valida o código SQL aplicando D1 (diretivas no início do statement),
    D2 (mapeamento fixo de tipo), D3 (recusa explícita de DESCONHECIDO) e controle de statements.
    Retorna:
        (valido, codigo_motivo, mensagem_erro, sql_execucao, tipo_real_detectado)
    """
    # 1. Tokenização completa do stream
    tokens = tokenizar_sql_stream(raw_sql)

    # 2. Verificação de Diretivas SQL*Plus (D1)
    valido_dir, mot_dir, msg_dir = verificar_diretivas_sqlplus(raw_sql, tokens)
    if not valido_dir:
        return False, mot_dir, msg_dir, "", "DIRETIVA_SQLPLUS"

    # 3. Determinação do Tipo Real (D2 & D3)
    tipo_real, erro_tipo = determinar_tipo_real_sql(tokens)
    if tipo_real == "TIPO_DIVERGENTE":
        return False, "TIPO_DIVERGENTE", erro_tipo, "", "DML"
    if tipo_real == "DESCONHECIDO":
        return False, "TIPO_NAO_RECONHECIDO", erro_tipo or "Tipo de comando SQL não reconhecido.", "", "DESCONHECIDO"
    if not tipo_real:
        return False, "MULTIPLOS_STATEMENTS", "Arquivo vazio ou contendo apenas comentários.", "", ""

    # 4. Validação Estrutural de Statements (C1 para PLSQL / Detecção em SQL comum)
    if tipo_real == "PLSQL":
        valido_plsql, motivo_plsql, msg_plsql = _analisar_blocos_plsql(tokens)
        if not valido_plsql:
            return False, motivo_plsql, msg_plsql, "", tipo_real

        sql_limpo = raw_sql.strip()
        if not sql_limpo.endswith(";"):
            sql_limpo += ";"
        return True, None, "", sql_limpo, tipo_real

    else:
        # SQL comum (SELECT, DML, DDL tradicional)
        ja_viu_ponto_e_virgula = False
        tokens_apos_delimitador = False

        for t_type, t_val in tokens:
            if t_type == "SEMICOLON":
                if ja_viu_ponto_e_virgula:
                    return False, "MULTIPLOS_STATEMENTS", "Múltiplos delimitadores ';' detectados em SQL comum.", "", tipo_real
                ja_viu_ponto_e_virgula = True
            elif ja_viu_ponto_e_virgula:
                if t_type not in ("WHITESPACE", "COMMENT_LINE", "COMMENT_BLOCK"):
                    tokens_apos_delimitador = True
                    break

        if tokens_apos_delimitador:
            return False, "MULTIPLOS_STATEMENTS", "Múltiplos statements SQL separados por ';' detectados.", "", tipo_real

        sql_limpo = raw_sql.strip()
        if sql_limpo.endswith(";"):
            sql_limpo = sql_limpo[:-1].rstrip()

        return True, None, "", sql_limpo, tipo_real


def _validar_binds(
    binds_declarados: List[Any],
    binds_fornecidos: Optional[Dict[str, Any]],
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """Valida correspondência exata de binds nomeados em relação ao registro homologado."""
    binds_input = binds_fornecidos or {}
    nomes_declarados = {b.nome for b in binds_declarados}
    nomes_recebidos = set(binds_input.keys())

    if nomes_declarados != nomes_recebidos:
        faltantes = nomes_declarados - nomes_recebidos
        extras = nomes_recebidos - nomes_declarados
        msg_erro = []
        if faltantes:
            msg_erro.append(f"Binds faltantes: {sorted(faltantes)}")
        if extras:
            msg_erro.append(f"Binds extras não declarados: {sorted(extras)}")
        return False, "; ".join(msg_erro), {}

    binds_processados: Dict[str, Any] = {}
    for def_b in binds_declarados:
        val = binds_input[def_b.nome]
        tipo_esperado = def_b.tipo.lower()
        if tipo_esperado in ("int", "integer", "number"):
            try:
                binds_processados[def_b.nome] = int(val)
            except (ValueError, TypeError):
                return False, f"Bind '{def_b.nome}' deve ser inteiro. Recebido: {val}", {}
        elif tipo_esperado in ("float", "decimal", "double"):
            try:
                binds_processados[def_b.nome] = float(val)
            except (ValueError, TypeError):
                return False, f"Bind '{def_b.nome}' deve ser número flutuante. Recebido: {val}", {}
        elif tipo_esperado in ("str", "string", "varchar", "varchar2", "text"):
            if not isinstance(val, str):
                return False, f"Bind '{def_b.nome}' deve ser string. Recebido: {type(val).__name__}", {}
            binds_processados[def_b.nome] = val
        else:
            binds_processados[def_b.nome] = val

    return True, None, binds_processados


def executar_script(script_id: str, binds: Optional[Dict[str, Any]] = None) -> str:
    """
    Executa um script Oracle homologado por script_id e binds declarados.
    
    Aplica ordem obrigatória de regras:
    1. Existência no registro (NAO_EXISTE) -> sem conectar
    2. Status homologado (BLOQUEADO) -> sem conectar
    3. Validação de Path Traversal (C4) resolve() e is_relative_to (PATH_INVALIDO) -> sem ler, sem conectar
    4. Validação de SHA256 dos bytes brutos (HASH_DIVERGENTE) -> sem conectar
    5. Tokenização estrita (C1: controle de blocos PL/SQL, MULTIPLOS_STATEMENTS, PLSQL_AMBIGUO, DIRETIVA_SQLPLUS)
    6. Verificação de Tipo (C2: TIPO_DIVERGENTE) -> sem conectar
    7. Validação estrita de binds declarados (BIND_INVALIDO) -> sem conectar
    8. Credenciais segregadas sem fallback (C3: ERRO_CONFIG) -> sem conectar
    9. Conexão Oracle com call_timeout configurado
    10. Execução: SELECT fetchmany(50) com LOB truncado / DML com commit e rollback em erro
        (D5: DDL no Oracle executa commit implícito antes e depois; não suporta rollback)
    11. Retorno JSON estruturado padronizado
    """
    # -------------------------------------------------------------------------
    # REGRA 1: script_id não existe no registro -> recusar, sem conectar
    # -------------------------------------------------------------------------
    registro = obter_script(script_id)
    if registro is None:
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "NAO_EXISTE",
                "script_id": script_id,
                "sha256_verificado": None,
                "mensagem": f"Script ID '{script_id}' não existe no registro homologado.",
            },
            ensure_ascii=False,
        )

    # -------------------------------------------------------------------------
    # REGRA 2: status != homologado -> recusar, sem conectar
    # -------------------------------------------------------------------------
    if registro.status != "homologado":
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "BLOQUEADO",
                "script_id": script_id,
                "sha256_verificado": None,
                "mensagem": f"Script ID '{script_id}' está com status '{registro.status}' e foi bloqueado.",
            },
            ensure_ascii=False,
        )

    # -------------------------------------------------------------------------
    # REGRA 3 (C4): Campo arquivo: resolve() e is_relative_to(scripts_dir)
    # Bloqueia ../ e caminhos absolutos antes de qualquer leitura de arquivo
    # -------------------------------------------------------------------------
    scripts_dir = obter_caminho_scripts_dir().resolve()
    try:
        caminho_arquivo = (scripts_dir / registro.arquivo).resolve()
        if not caminho_arquivo.is_relative_to(scripts_dir) or caminho_arquivo == scripts_dir:
            return json.dumps(
                {
                    "status": "recusado",
                    "motivo": "PATH_INVALIDO",
                    "script_id": script_id,
                    "sha256_verificado": None,
                    "mensagem": (
                        f"Caminho do arquivo '{registro.arquivo}' tenta acessar diretório externo "
                        f"a '{scripts_dir}'."
                    ),
                },
                ensure_ascii=False,
            )
    except Exception as e:
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "PATH_INVALIDO",
                "script_id": script_id,
                "sha256_verificado": None,
                "mensagem": f"Falha na validação do caminho do arquivo: {str(e)}",
            },
            ensure_ascii=False,
        )

    if not caminho_arquivo.is_file():
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "HASH_DIVERGENTE",
                "script_id": script_id,
                "sha256_verificado": None,
                "mensagem": f"Arquivo físico '{registro.arquivo}' não encontrado.",
            },
            ensure_ascii=False,
        )

    # -------------------------------------------------------------------------
    # REGRA 4: Calcular sha256 dos bytes brutos
    # -------------------------------------------------------------------------
    with open(caminho_arquivo, "rb") as f:
        bytes_brutos = f.read()
    sha256_calculado = hashlib.sha256(bytes_brutos).hexdigest()

    if sha256_calculado != registro.sha256:
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "HASH_DIVERGENTE",
                "script_id": script_id,
                "sha256_verificado": sha256_calculado,
                "sha256_esperado": registro.sha256,
                "mensagem": (
                    f"Hash SHA256 do arquivo físico ({sha256_calculado}) diverge do "
                    f"registro homologado ({registro.sha256})."
                ),
            },
            ensure_ascii=False,
        )

    # -------------------------------------------------------------------------
    # REGRA 5 (C1 & C2): Tokenização, verificação de tipo e análise de blocos
    # -------------------------------------------------------------------------
    try:
        conteudo_sql = bytes_brutos.decode("utf-8")
    except UnicodeDecodeError:
        conteudo_sql = bytes_brutos.decode("latin-1", errors="replace")

    valido, cod_motivo, msg_erro, sql_execucao, tipo_detectado = tokenizar_e_validar_sql(conteudo_sql)
    if not valido:
        return json.dumps(
            {
                "status": "recusado",
                "motivo": cod_motivo,
                "script_id": script_id,
                "sha256_verificado": sha256_calculado,
                "mensagem": msg_erro,
            },
            ensure_ascii=False,
        )

    # D2: Verificação de divergência de tipo com igualdade estrita (sem relaxamento)
    if registro.tipo != tipo_detectado:
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "TIPO_DIVERGENTE",
                "script_id": script_id,
                "sha256_verificado": sha256_calculado,
                "tipo_declarado": registro.tipo,
                "tipo_detectado": tipo_detectado,
                "mensagem": (
                    f"Tipo declarado no registro ({registro.tipo}) diverge do tipo real "
                    f"detectado no código ({tipo_detectado})."
                ),
            },
            ensure_ascii=False,
        )

    # -------------------------------------------------------------------------
    # REGRA 6: Validação de Binds
    # -------------------------------------------------------------------------
    binds_ok, msg_binds, binds_validados = _validar_binds(registro.binds, binds)
    if not binds_ok:
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "BIND_INVALIDO",
                "script_id": script_id,
                "sha256_verificado": sha256_calculado,
                "mensagem": f"Parâmetros de bind inválidos: {msg_binds}",
            },
            ensure_ascii=False,
        )

    # -------------------------------------------------------------------------
    # REGRA 7 (C3): Sem fallback de credenciais -> ERRO_CONFIG
    # -------------------------------------------------------------------------
    if registro.tipo == "SELECT":
        user = os.getenv("ORACLE_USER_READ")
        password = os.getenv("ORACLE_PASSWORD_READ")
        if not user or not password:
            return json.dumps(
                {
                    "status": "recusado",
                    "motivo": "ERRO_CONFIG",
                    "script_id": script_id,
                    "sha256_verificado": sha256_calculado,
                    "mensagem": (
                        "Configuração incompleta: ORACLE_USER_READ ou ORACLE_PASSWORD_READ "
                        "não configurados no ambiente (.env)."
                    ),
                },
                ensure_ascii=False,
            )
    else:
        user = os.getenv("ORACLE_USER_MUT")
        password = os.getenv("ORACLE_PASSWORD_MUT")
        if not user or not password:
            return json.dumps(
                {
                    "status": "recusado",
                    "motivo": "ERRO_CONFIG",
                    "script_id": script_id,
                    "sha256_verificado": sha256_calculado,
                    "mensagem": (
                        "Configuração incompleta: ORACLE_USER_MUT ou ORACLE_PASSWORD_MUT "
                        "não configurados no ambiente (.env)."
                    ),
                },
                ensure_ascii=False,
            )

    dsn = os.getenv("ORACLE_DSN")
    if not dsn:
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "ERRO_CONFIG",
                "script_id": script_id,
                "sha256_verificado": sha256_calculado,
                "mensagem": "Configuração incompleta: ORACLE_DSN não configurado no ambiente (.env).",
            },
            ensure_ascii=False,
        )

    # -------------------------------------------------------------------------
    # REGRA 8: Conexão com o banco e call_timeout
    # -------------------------------------------------------------------------
    connection: Optional[oracledb.Connection] = None
    cursor: Optional[oracledb.Cursor] = None

    try:
        connection = oracledb.connect(user=user, password=password, dsn=dsn)
        call_timeout_ms = int(os.getenv("ORACLE_CALL_TIMEOUT_MS", "30000"))
        connection.call_timeout = call_timeout_ms

        cursor = connection.cursor()
        cursor.execute("SELECT SYS_CONTEXT('USERENV', 'INSTANCE') FROM dual")
        row_inst = cursor.fetchone()
        inst_id = str(row_inst[0]) if row_inst and row_inst[0] is not None else "1"

        limite_select = int(os.getenv("ORACLE_SELECT_LIMIT", str(LIMITE_PADRAO_SELECT)))
        limite_lob = int(os.getenv("ORACLE_LOB_LIMIT", str(LIMITE_PADRAO_LOB)))

        # ---------------------------------------------------------------------
        # REGRA 9 (D5): Execução e Transacionalidade
        # ---------------------------------------------------------------------
        if registro.tipo == "SELECT":
            cursor.execute(sql_execucao, binds_validados)
            colunas = [col[0].lower() for col in cursor.description]
            linhas_brutas = cursor.fetchmany(limite_select)

            registros_saida: List[Dict[str, Any]] = []
            for row in linhas_brutas:
                registro_map = {}
                for col_nome, val in zip(colunas, row):
                    registro_map[col_nome] = _serializar_valor(val, limite_lob=limite_lob)
                registros_saida.append(registro_map)

            return json.dumps(
                {
                    "status": "sucesso",
                    "script_id": script_id,
                    "sha256_verificado": sha256_calculado,
                    "instancia": dsn,
                    "inst_id": inst_id,
                    "tipo": registro.tipo,
                    "linhas_afetadas": len(registros_saida),
                    "saida": registros_saida,
                },
                ensure_ascii=False,
            )

        elif registro.tipo == "PLSQL":
            try:
                cursor.callproc("dbms_output.enable", [None])
            except Exception:
                pass

            cursor.execute(sql_execucao, binds_validados)
            connection.commit()

            linhas_output: List[str] = []
            try:
                status_var = cursor.var(int)
                linha_var = cursor.var(str)
                while True:
                    cursor.callproc("dbms_output.get_line", (linha_var, status_var))
                    if status_var.getvalue() != 0:
                        break
                    linhas_output.append(linha_var.getvalue() or "")
            except Exception:
                pass

            linhas_afetadas = max(cursor.rowcount, 0)
            saida_texto = "\n".join(linhas_output[:50]) if linhas_output else "Bloco PL/SQL executado com sucesso."

            return json.dumps(
                {
                    "status": "sucesso",
                    "script_id": script_id,
                    "sha256_verificado": sha256_calculado,
                    "instancia": dsn,
                    "inst_id": inst_id,
                    "tipo": registro.tipo,
                    "linhas_afetadas": linhas_afetadas,
                    "saida": saida_texto,
                },
                ensure_ascii=False,
            )

        elif registro.tipo == "DML":
            cursor.execute(sql_execucao, binds_validados)
            connection.commit()
            linhas_afetadas = max(cursor.rowcount, 0)

            return json.dumps(
                {
                    "status": "sucesso",
                    "script_id": script_id,
                    "sha256_verificado": sha256_calculado,
                    "instancia": dsn,
                    "inst_id": inst_id,
                    "tipo": registro.tipo,
                    "linhas_afetadas": linhas_afetadas,
                    "saida": "Comando DML executado e commit realizado com sucesso.",
                },
                ensure_ascii=False,
            )

        else:
            # DDL: Auto-commit nativo do Oracle (D5)
            cursor.execute(sql_execucao, binds_validados)
            linhas_afetadas = max(cursor.rowcount, 0)

            return json.dumps(
                {
                    "status": "sucesso",
                    "script_id": script_id,
                    "sha256_verificado": sha256_calculado,
                    "instancia": dsn,
                    "inst_id": inst_id,
                    "tipo": registro.tipo,
                    "linhas_afetadas": linhas_afetadas,
                    "saida": "Comando DDL executado com sucesso (commit implícito no Oracle).",
                },
                ensure_ascii=False,
            )

    except oracledb.Error as db_err:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass

        return json.dumps(
            {
                "status": "erro",
                "motivo": "ERRO_ORACLE",
                "script_id": script_id,
                "sha256_verificado": sha256_calculado,
                "instancia": dsn,
                "mensagem": str(db_err),
            },
            ensure_ascii=False,
        )

    except Exception as exc:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass

        return json.dumps(
            {
                "status": "erro",
                "motivo": "ERRO_ORACLE",
                "script_id": script_id,
                "sha256_verificado": sha256_calculado,
                "instancia": dsn,
                "mensagem": f"Erro inesperado durante execução: {str(exc)}",
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
