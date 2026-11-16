"""
Módulo Executor Seguro de Scripts Oracle por script_id (TAREFA 1).
Aplica 9 regras de validação estritas em ordem obrigatória.
O LLM nunca envia SQL bruto; executa exclusivamente scripts homologados no registro.
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

# Constantes e Diretivas SQL*Plus a recusar
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
        # Leitura de LOB (CLOB/BLOB/NCLOB)
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


def tokenizar_e_validar_sql(raw_sql: str) -> Tuple[bool, Optional[str], str, str]:
    """
    Tokeniza o código SQL bruto, inspeciona comentários, literais de string (incluindo q'[...]'),
    aspas duplas, diretivas SQL*Plus e contagem de statements.

    Retorna:
        (valido, codigo_motivo, mensagem_erro, sql_pronto_para_execucao)
        codigo_motivo pode ser 'DIRETIVA_SQLPLUS', 'MULTIPLOS_STATEMENTS' ou None.
    """
    # 1. Verificação de Diretivas SQL*Plus por linha (SET, PROMPT, SPOOL, COL, @, /, EXEC sem bloco)
    for num_linha, linha in enumerate(raw_sql.splitlines(), start=1):
        strip_l = linha.strip()
        if not strip_l:
            continue

        # Barra isolada '/'
        if strip_l == "/":
            return False, "DIRETIVA_SQLPLUS", f"Linha {num_linha}: Barra isolada '/' detectada.", ""

        # Diretiva de script externo (@ ou @@)
        if strip_l.startswith("@"):
            return False, "DIRETIVA_SQLPLUS", f"Linha {num_linha}: Diretiva de inclusão de script '{strip_l.split()[0]}' detectada.", ""

        # Comentários de linha isolados
        if strip_l.startswith("--"):
            continue
        if strip_l.startswith("/*") and strip_l.endswith("*/"):
            continue

        primeira_palavra = re.split(r"\s+", strip_l)[0].upper()
        if primeira_palavra in SQLPLUS_DIRECTIVES:
            return False, "DIRETIVA_SQLPLUS", f"Linha {num_linha}: Diretiva SQL*Plus '{primeira_palavra}' detectada.", ""

        # EXEC sem bloco BEGIN/DECLARE
        if primeira_palavra in ("EXEC", "EXECUTE"):
            resto = strip_l[len(primeira_palavra):].strip().upper()
            if not (resto.startswith("BEGIN") or resto.startswith("DECLARE")):
                return False, "DIRETIVA_SQLPLUS", f"Linha {num_linha}: Diretiva SQL*Plus 'EXEC' sem bloco autônomo detectada.", ""

    # 2. Tokenização completa respeitando comentários, literais normais e literais Q
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
            i += 2  # pula q'
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
                        i += 2  # aspas duplicadas '' escapadas
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

        # Ponto e vírgula fora de strings e comentários
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

        # Símbolos avulsos (: , ( ) + - = etc.)
        tokens.append(("SYMBOL", c))
        i += 1

    # Extrai palavras de código fora de comentários para avaliar estrutura
    palavras_codigo: List[str] = []
    for t_type, t_val in tokens:
        if t_type in ("WORD", "IDENT_QUOTED"):
            palavras_codigo.append(t_val.upper())

    if not palavras_codigo:
        return False, "MULTIPLOS_STATEMENTS", "Arquivo vazio ou contendo apenas comentários.", ""

    primeira_palavra = palavras_codigo[0]

    # Verifica se é bloco PL/SQL ou DDL de Procedure/Function/Package/Trigger/Type
    eh_plsql = False
    if primeira_palavra in ("DECLARE", "BEGIN"):
        eh_plsql = True
    elif primeira_palavra == "CREATE":
        sub_palavras = [w for w in palavras_codigo[1:6] if w not in ("OR", "REPLACE", "EDITIONABLE", "NONEDITIONABLE")]
        if sub_palavras and sub_palavras[0] in ("PROCEDURE", "FUNCTION", "PACKAGE", "TRIGGER", "TYPE"):
            eh_plsql = True

    if eh_plsql:
        # Validação de Bloco PL/SQL único:
        # Rastreia profundidade do bloco com BEGIN/CASE vs END
        depth = 0
        iniciou_bloco = False
        bloco_fechado = False
        tokens_apos_bloco: List[Tuple[str, str]] = []

        for t_type, t_val in tokens:
            word = t_val.upper() if t_type == "WORD" else ""
            if word in ("BEGIN", "CASE"):
                if bloco_fechado:
                    return False, "MULTIPLOS_STATEMENTS", "Segundo bloco PL/SQL iniciado no mesmo arquivo.", ""
                depth += 1
                iniciou_bloco = True
            elif word == "END":
                depth -= 1
                if depth == 0:
                    bloco_fechado = True
            elif bloco_fechado:
                if t_type == "SEMICOLON":
                    continue  # Ponto e vírgula que fecha o END;
                if t_type == "WORD" and depth == 0:
                    # Rótulo de fechamento após END (ex: END nome_proc;)
                    continue
                if t_type not in ("WHITESPACE", "COMMENT_LINE", "COMMENT_BLOCK"):
                    tokens_apos_bloco.append((t_type, t_val))

        if tokens_apos_bloco:
            return (
                False,
                "MULTIPLOS_STATEMENTS",
                f"Múltiplos statements detectados após o fechamento do bloco PL/SQL: {[t[1] for t in tokens_apos_bloco]}",
                "",
            )

        sql_limpo = raw_sql.strip()
        if not sql_limpo.endswith(";"):
            sql_limpo += ";"
        return True, None, "", sql_limpo

    else:
        # Validação de Statement SQL Único (SELECT, INSERT, UPDATE, DELETE, etc.)
        # Ponto e vírgula só é permitido no final absoluto do comando
        ja_viu_ponto_e_virgula = False
        tokens_apos_delimitador = False

        for t_type, t_val in tokens:
            if t_type == "SEMICOLON":
                if ja_viu_ponto_e_virgula:
                    return False, "MULTIPLOS_STATEMENTS", "Múltiplos delimitadores ';' detectados em SQL comum.", ""
                ja_viu_ponto_e_virgula = True
            elif ja_viu_ponto_e_virgula:
                if t_type not in ("WHITESPACE", "COMMENT_LINE", "COMMENT_BLOCK"):
                    tokens_apos_delimitador = True
                    break

        if tokens_apos_delimitador:
            return False, "MULTIPLOS_STATEMENTS", "Múltiplos statements SQL separados por ';' detectados.", ""

        sql_limpo = raw_sql.strip()
        if sql_limpo.endswith(";"):
            sql_limpo = sql_limpo[:-1].rstrip()

        return True, None, "", sql_limpo


def _validar_binds(
    binds_declarados: List[Any],
    binds_fornecidos: Optional[Dict[str, Any]],
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Valida se os parâmetros nomeados passados batem exatamente com o registro homologado.
    Recusa se houver bind extra ou faltante.
    """
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

    # Conversão/validação de tipos básicos
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
    Executa um script Oracle homologado a partir de seu script_id e binds declarados.
    
    Aplica as 9 regras obrigatórias:
    1. Existência no registro (NAO_EXISTE) -> sem conectar
    2. Status homologado (BLOQUEADO) -> sem conectar
    3. Validação de SHA256 dos bytes brutos (HASH_DIVERGENTE) -> sem conectar
    4. Tokenização (MULTIPLOS_STATEMENTS / DIRETIVA_SQLPLUS) -> sem conectar
    5. Validação exata de binds declarados (BIND_INVALIDO) -> sem conectar
    6. Conexão segregada por tipo (ORACLE_USER_READ vs ORACLE_USER_MUT)
    7. Configuração de call_timeout na conexão
    8. Execução: SELECT fetchmany(50) com LOB truncado / DML com commit e rollback em erro
    9. Retorno estruturado em JSON padronizado
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
    # REGRA 3: Calcular sha256 do arquivo; diferente do registro -> recusar, sem conectar
    # -------------------------------------------------------------------------
    caminho_arquivo = obter_caminho_scripts_dir() / registro.arquivo
    if not caminho_arquivo.is_file():
        return json.dumps(
            {
                "status": "recusado",
                "motivo": "HASH_DIVERGENTE",
                "script_id": script_id,
                "sha256_verificado": None,
                "mensagem": f"Arquivo físico '{registro.arquivo}' não encontrado no diretório de scripts.",
            },
            ensure_ascii=False,
        )

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
    # REGRA 4: Tokenizar o arquivo (respeitar literais, comentários, aspas)
    # Recusar se múltiplos statements ou diretiva SQL*Plus -> sem conectar
    # -------------------------------------------------------------------------
    try:
        conteudo_sql = bytes_brutos.decode("utf-8")
    except UnicodeDecodeError:
        conteudo_sql = bytes_brutos.decode("latin-1", errors="replace")

    valido, cod_motivo, msg_erro, sql_execucao = tokenizar_e_validar_sql(conteudo_sql)
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

    # -------------------------------------------------------------------------
    # REGRA 5: Binds nomeados oracledb; coincidir estritamente com o registro -> recusar
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
    # REGRA 6: Usuário Oracle pelo tipo: SELECT -> ORACLE_USER_READ; demais -> ORACLE_USER_MUT
    # -------------------------------------------------------------------------
    if registro.tipo == "SELECT":
        user = os.getenv("ORACLE_USER_READ") or os.getenv("ORACLE_USER")
        password = os.getenv("ORACLE_PASSWORD_READ") or os.getenv("ORACLE_PASSWORD")
    else:
        user = os.getenv("ORACLE_USER_MUT") or os.getenv("ORACLE_USER")
        password = os.getenv("ORACLE_PASSWORD_MUT") or os.getenv("ORACLE_PASSWORD")

    dsn = os.getenv("ORACLE_DSN")

    if not all([user, password, dsn]):
        return json.dumps(
            {
                "status": "erro",
                "motivo": "ERRO_ORACLE",
                "script_id": script_id,
                "sha256_verificado": sha256_calculado,
                "instancia": dsn or "NAO_CONFIGURADO",
                "mensagem": "Credenciais do Oracle incompletas no arquivo de configuração (.env).",
            },
            ensure_ascii=False,
        )

    connection: Optional[oracledb.Connection] = None
    cursor: Optional[oracledb.Cursor] = None

    try:
        # Abertura da conexão com o banco
        connection = oracledb.connect(user=user, password=password, dsn=dsn)

        # ---------------------------------------------------------------------
        # REGRA 7: Conexão com call_timeout definido em configuração
        # ---------------------------------------------------------------------
        call_timeout_ms = int(os.getenv("ORACLE_CALL_TIMEOUT_MS", "30000"))
        connection.call_timeout = call_timeout_ms

        cursor = connection.cursor()

        # Coleta ID da instância Oracle via contexto nativo
        cursor.execute("SELECT SYS_CONTEXT('USERENV', 'INSTANCE') FROM dual")
        row_inst = cursor.fetchone()
        inst_id = str(row_inst[0]) if row_inst and row_inst[0] is not None else "1"

        # ---------------------------------------------------------------------
        # REGRA 8: Execução (SELECT fetchmany / DML commit e rollback em exceção)
        # ---------------------------------------------------------------------
        limite_select = int(os.getenv("ORACLE_SELECT_LIMIT", str(LIMITE_PADRAO_SELECT)))
        limite_lob = int(os.getenv("ORACLE_LOB_LIMIT", str(LIMITE_PADRAO_LOB)))

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

            # -----------------------------------------------------------------
            # REGRA 9: Retorno JSON estruturado de sucesso para SELECT
            # -----------------------------------------------------------------
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
            # Habilita captura de DBMS_OUTPUT para blocos PL/SQL
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

        else:
            # DML ou DDL
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
                    "saida": f"Comando {registro.tipo} executado e commit realizado com sucesso.",
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
