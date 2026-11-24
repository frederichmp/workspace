"""
Fakes de Oracle compartilhados pelos testes sem conexão (movidos de test_oracle_kill.py).

Roteamento por SQL: só a consulta de alvo (consultar_alvo_sessao_diag: FROM GV$SESSION com
bind :p_serial, conta DIAG) consome a fila `linhas_diag`; as demais consultas não a consomem.
"""
import re
from datetime import datetime

import oracledb
import pytest

USER_DIAG_FAKE = "diag_teste_fake"
USER_KILL_FAKE = "kill_teste_fake"

# LOGON_TIME no fim: preserva row[2] = serial# (a produção lê o serial# por posição).
COLUNAS_ALVO = [
    "INST_ID", "SID", "serial#", "USERNAME", "PROGRAM", "MACHINE", "STATUS", "SQL_ID", "EVENT", "TYPE", "LOGON_TIME",
]

LOGON_TIME_PADRAO = datetime(2026, 11, 23, 10, 0, 0)

# NÃO VERIFICADA (L7): charset do banco do MODELO assumido como AL32UTF8 (1 a 4 bytes por caractere). O PKG mede
# a identidade com LENGTHB (ops_kill.sql:123-125); o fake simula esse limite de 128 bytes com UTF-8.
PREMISSA_CHARSET_MODELO = "AL32UTF8"
LIMITE_LENGTHB_IDENTIDADE = 128
BINDS_IDENTIDADE_TEXTO = ("p_username_esperado", "p_program_esperado", "p_machine_esperado")
TAMANHO_PADRAO_VAR_VARCHAR = 4000  # tamanho padrão de uma var VARCHAR do oracledb quando o size não é informado


def _linha_alvo(
    username="APP_USER",
    program="app.exe",
    machine="srv-app01",
    status="ACTIVE",
    sql_id="2z0udr4rc402m",
    event="SQL*Net message from client",
    tipo="USER",
    inst_id=1,
    sid=101,
    serial=202,
    logon_time=LOGON_TIME_PADRAO,
):
    return (inst_id, sid, serial, username, program, machine, status, sql_id, event, tipo, logon_time)


class _VarFake:
    """
    Var de bind: guarda o tipo, o size pedido e o valor. getvalue pode levantar (T9, D8) e setvalue também.
    A var VARCHAR nasce sem valor: o p_status só é gravado dentro do execute da conta KILL (_gravar_saida).
    """

    def __init__(self, tipo=None, valor=None, erro_getvalue=None, size=None, erro_setvalue=None):
        self.tipo = tipo
        self.size = size
        self._valor = valor
        self._erro_getvalue = erro_getvalue
        self._erro_setvalue = erro_setvalue

    def setvalue(self, pos, valor):
        if self._erro_setvalue is not None:
            raise self._erro_setvalue
        if pos != 0:
            raise IndexError(f"posição inválida para setvalue (fake): {pos!r}; só a posição 0 existe")
        if self.tipo is oracledb.DB_TYPE_DATE and not isinstance(valor, datetime):
            raise TypeError(f"setvalue (fake): var DATE exige datetime, recebeu {type(valor).__name__}")
        self._valor = valor

    def _gravar_saida(self, valor):
        """Grava a saída do PL/SQL; VARCHAR estoura com ORA-06502 se o valor passa do size da var."""
        if isinstance(valor, str) and self.tipo is oracledb.DB_TYPE_VARCHAR:
            tamanho = self.size if self.size else TAMANHO_PADRAO_VAR_VARCHAR
            if len(valor.encode("utf-8")) > tamanho:
                raise oracledb.DatabaseError("ORA-06502: PL/SQL: numeric or value error (fake)")
        self._valor = valor

    def getvalue(self):
        if self._erro_getvalue is not None:
            raise self._erro_getvalue
        return self._valor


def _eh_consulta_alvo(sql):
    """Identifica a consulta de alvo de consultar_alvo_sessao_diag: GV$SESSION filtrada por :p_serial."""
    s = sql.lower()
    return "from gv$session" in s and ":p_serial" in s


def _sem_comentarios_sql(sql):
    """Remove comentários de linha `--` (o Oracle também ignora o que está neles)."""
    return re.sub(r"--[^\n]*", "", sql)


def _colunas_do_select(sql):
    """
    Nomes das colunas na ordem do SELECT (entre SELECT e FROM), sem comentários `--` e com o alias:
    `serial# AS "serial#"` vira `serial#`.
    """
    limpo = _sem_comentarios_sql(sql)
    m = re.search(r"\bselect\b(.*?)\bfrom\b", limpo, flags=re.IGNORECASE | re.DOTALL)
    assert m, "SELECT da consulta de alvo não encontrado (fake)"
    nomes = []
    for item in m.group(1).split(","):
        item = item.strip()
        alias = re.match(r"^(.*?)\s+as\s+(.+)$", item, flags=re.IGNORECASE | re.DOTALL)
        nome = alias.group(2).strip() if alias else item
        nomes.append(nome.strip('"'))
    return nomes


def _placeholders_sql(sql):
    """Conjunto dos :nome do SQL, sem os que estão em comentários `--`."""
    return set(re.findall(r":([A-Za-z_][A-Za-z0-9_$#]*)", _sem_comentarios_sql(sql)))


class _CursorFake:
    def __init__(self, oracle_fake, conta):
        self.oracle = oracle_fake
        self.conta = conta
        self.description = [(c,) for c in COLUNAS_ALVO]
        self._linha = None

    def execute(self, sql, **binds):
        self.oracle.sql_executado.append((self.conta, sql, binds))
        if self.conta == "KILL":
            # O Oracle exige que os :nomes do SQL sejam exatamente as chaves dos binds (DPY-4008/DPY-4010).
            if _placeholders_sql(sql) != set(binds):
                raise oracledb.DatabaseError("DPY-4008 (fake): binds divergentes")
            if self.oracle.erro_kill is not None:
                raise self.oracle.erro_kill  # exceção levantada A PARTIR do execute da conta KILL
            self._executar_pkg_kill(binds)
        if self.conta == "DIAG" and _eh_consulta_alvo(sql):
            self._executar_consulta_alvo(sql)

    def _executar_pkg_kill(self, binds):
        status = self.oracle.status_pkg
        for nome in BINDS_IDENTIDADE_TEXTO:
            valor = binds.get(nome)
            if valor is not None and len(str(valor).encode("utf-8")) > LIMITE_LENGTHB_IDENTIDADE:
                status = "PARAM_INVALIDO"  # LENGTHB do PKG (ops_kill.sql:123-125), premissa de charset do modelo
        saida = binds.get("p_status")
        if status is not None and isinstance(saida, _VarFake):
            saida._gravar_saida(status)

    def _executar_consulta_alvo(self, sql):
        """description e linha derivadas do SELECT: mesma ordem, a partir da linha completa por nome de coluna."""
        colunas = _colunas_do_select(sql)
        completa = self.oracle.linhas_diag.pop(0) if self.oracle.linhas_diag else None
        self.description = [(c,) for c in colunas]
        if completa is None:
            self._linha = None
            return
        por_nome = {c.lower(): v for c, v in zip(COLUNAS_ALVO, completa)}
        linha = []
        for c in colunas:
            if c.lower() not in por_nome:
                raise AssertionError(f"coluna desconhecida no SELECT da consulta de alvo (fake): {c!r}")
            linha.append(por_nome[c.lower()])
        self._linha = tuple(linha)

    def fetchone(self):
        return self._linha

    def var(self, tipo=None, size=None, *args, **kwargs):
        # A var VARCHAR (p_status) nasce sem valor: o execute da conta KILL grava o status_pkg (e valida o size).
        # As demais (ex.: DATE) devolvem o que o setvalue gravou.
        if self.conta == "KILL" and self.oracle.erro_var_kill is not None:
            raise self.oracle.erro_var_kill
        if tipo is oracledb.DB_TYPE_VARCHAR:
            erro_getvalue = self.oracle.erro_getvalue_status
        else:
            erro_getvalue = None
        var = _VarFake(
            tipo, erro_getvalue=erro_getvalue, size=size, erro_setvalue=self.oracle.erro_setvalue,
        )
        self.oracle.vars_criadas.append(var)
        return var

    def close(self):
        pass


class _ConexaoFake:
    def __init__(self, oracle_fake, conta):
        self.oracle = oracle_fake
        self.conta = conta

    def cursor(self):
        return _CursorFake(self.oracle, self.conta)

    def close(self):
        pass


class _OracleFake:
    """Simula oracledb.connect: fila de linhas para a conta DIAG e p_status para a conta KILL."""

    def __init__(
        self, linhas_diag, status_pkg=None, kill_permitido=True, erro_kill=None, erro_connect_kill=None,
        erro_getvalue_status=None, erro_var_kill=None, erro_setvalue=None,
    ):
        self.linhas_diag = list(linhas_diag)
        self.status_pkg = status_pkg
        self.erro_getvalue_status = erro_getvalue_status  # exceção levantada pelo getvalue da var do p_status
        self.erro_var_kill = erro_var_kill  # exceção levantada pelo cursor.var da conta KILL
        self.erro_setvalue = erro_setvalue  # exceção levantada pelo setvalue das vars da conta KILL
        self.vars_criadas = []
        self.kill_permitido = kill_permitido
        self.erro_kill = erro_kill  # exceção levantada pelo execute da conta KILL
        self.erro_connect_kill = erro_connect_kill  # exceção levantada pelo connect da conta KILL
        self.conexoes = []
        self.sql_executado = []

    def connect(self, user=None, password=None, dsn=None, **kwargs):
        self.conexoes.append(user)
        if user == USER_KILL_FAKE:
            if not self.kill_permitido:
                pytest.fail("oracledb.connect não deve ser chamado para a conta KILL neste cenário")
            if self.erro_connect_kill is not None:
                raise self.erro_connect_kill
            return _ConexaoFake(self, "KILL")
        if user == USER_DIAG_FAKE:
            return _ConexaoFake(self, "DIAG")
        pytest.fail(f"Conexão com conta inesperada: {user!r}")

    @property
    def conexoes_kill(self):
        return [u for u in self.conexoes if u == USER_KILL_FAKE]
