"""
Fakes de Oracle compartilhados pelos testes sem conexão (movidos de test_oracle_kill.py).

Roteamento por SQL: só a consulta de alvo (consultar_alvo_sessao_diag: FROM GV$SESSION com
bind :p_serial, conta DIAG) consome a fila `linhas_diag`; as demais consultas não a consomem.
"""
import pytest

USER_DIAG_FAKE = "diag_teste_fake"
USER_KILL_FAKE = "kill_teste_fake"

COLUNAS_ALVO = ["INST_ID", "SID", "serial#", "USERNAME", "PROGRAM", "MACHINE", "STATUS", "SQL_ID", "EVENT", "TYPE"]


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
):
    return (inst_id, sid, serial, username, program, machine, status, sql_id, event, tipo)


class _VarFake:
    def __init__(self, valor):
        self._valor = valor

    def getvalue(self):
        return self._valor


def _eh_consulta_alvo(sql):
    """Identifica a consulta de alvo de consultar_alvo_sessao_diag: GV$SESSION filtrada por :p_serial."""
    s = sql.lower()
    return "from gv$session" in s and ":p_serial" in s


class _CursorFake:
    def __init__(self, oracle_fake, conta):
        self.oracle = oracle_fake
        self.conta = conta
        self.description = [(c,) for c in COLUNAS_ALVO]
        self._linha = None

    def execute(self, sql, **binds):
        self.oracle.sql_executado.append((self.conta, sql, binds))
        if self.conta == "KILL" and self.oracle.erro_kill is not None:
            raise self.oracle.erro_kill  # exceção levantada A PARTIR do execute da conta KILL
        if self.conta == "DIAG" and _eh_consulta_alvo(sql):
            self._linha = self.oracle.linhas_diag.pop(0) if self.oracle.linhas_diag else None

    def fetchone(self):
        return self._linha

    def var(self, *args, **kwargs):
        return _VarFake(self.oracle.status_pkg)

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

    def __init__(self, linhas_diag, status_pkg=None, kill_permitido=True, erro_kill=None, erro_connect_kill=None):
        self.linhas_diag = list(linhas_diag)
        self.status_pkg = status_pkg
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
