"""
Fakes de Oracle compartilhados pelos testes sem conexão (movidos de test_oracle_kill.py).

Roteamento por SQL: só a consulta de alvo (consultar_alvo_sessao_diag: FROM GV$SESSION com
bind :p_serial, conta DIAG) consome a fila `linhas_diag`; as demais consultas não a consomem.
"""
from datetime import datetime

import pytest

USER_DIAG_FAKE = "diag_teste_fake"
USER_KILL_FAKE = "kill_teste_fake"

LOGON_TIME_FAKE = datetime(2026, 11, 17, 8, 0, 0)

COLUNAS_ALVO = ["INST_ID", "SID", "serial#", "USERNAME", "PROGRAM", "MACHINE", "LOGON_TIME", "STATUS", "SQL_ID", "EVENT", "TYPE"]


def _linha_alvo(
    username="APP_USER",
    program="app.exe",
    machine="srv-app01",
    logon_time=LOGON_TIME_FAKE,
    status="ACTIVE",
    sql_id="2z0udr4rc402m",
    event="SQL*Net message from client",
    tipo="USER",
    inst_id=1,
    sid=101,
    serial=202,
):
    return (inst_id, sid, serial, username, program, machine, logon_time, status, sql_id, event, tipo)


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
        if self.conta == "KILL":
            if "OPS_OWNER.PKG_OPS_KILL.KILL_SESSION" not in sql:
                pytest.fail("Conta KILL só pode executar OPS_OWNER.PKG_OPS_KILL.KILL_SESSION")
            if self.oracle.erro_kill is not None:
                raise self.oracle.erro_kill
        if self.conta == "DIAG" and _eh_consulta_alvo(sql):
            self._linha = self.oracle.linhas_diag.pop(0) if self.oracle.linhas_diag else None

    def fetchone(self):
        return self._linha

    def var(self, *args, **kwargs):
        var = _VarFake(self.oracle.status_pkg)
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

    def __init__(self, linhas_diag, status_pkg=None, kill_permitido=True, erro_kill=None):
        self.linhas_diag = list(linhas_diag)
        self.status_pkg = status_pkg
        self.kill_permitido = kill_permitido
        self.erro_kill = erro_kill  # exceção levantada pelo execute da conta KILL
        self.vars_criadas = []
        self.conexoes = []
        self.sql_executado = []

    def connect(self, user=None, password=None, dsn=None, **kwargs):
        self.conexoes.append(user)
        if user == USER_KILL_FAKE:
            if not self.kill_permitido:
                pytest.fail("oracledb.connect não deve ser chamado para a conta KILL neste cenário")
            return _ConexaoFake(self, "KILL")
        if user == USER_DIAG_FAKE:
            return _ConexaoFake(self, "DIAG")
        pytest.fail(f"Conexão com conta inesperada: {user!r}")

    @property
    def conexoes_kill(self):
        return [u for u in self.conexoes if u == USER_KILL_FAKE]


BINDS_KILL_V2 = (
    "p_inst_id",
    "p_sid",
    "p_serial",
    "p_username_esperado",
    "p_program_esperado",
    "p_machine_esperado",
    "p_logon_time_esperado",
    "p_ref_aprovacao",
    "p_status",
)


def assert_kill_binds(fake, inst_id, sid, serial, username, program, machine, logon_time, ref_aprovacao=None):
    """Exige exatamente 1 execute na conta KILL, com os 9 binds nomeados do PKG v2 e valores esperados."""
    execs = [(sql, binds) for conta, sql, binds in fake.sql_executado if conta == "KILL"]
    assert len(execs) == 1, f"esperado 1 execute na conta KILL, obtido {len(execs)}"
    sql, binds = execs[0]
    assert "OPS_OWNER.PKG_OPS_KILL.KILL_SESSION" in sql
    assert sorted(binds) == sorted(BINDS_KILL_V2)
    esperado = {
        "p_inst_id": inst_id,
        "p_sid": sid,
        "p_serial": serial,
        "p_username_esperado": username,
        "p_program_esperado": program,
        "p_machine_esperado": machine,
        "p_logon_time_esperado": logon_time,
    }
    for nome, valor in esperado.items():
        assert binds[nome] == valor, f"{nome}: esperado {valor!r}, obtido {binds[nome]!r}"
    assert isinstance(binds["p_status"], _VarFake) and any(binds["p_status"] is v for v in fake.vars_criadas)
    if ref_aprovacao is not None:
        assert binds["p_ref_aprovacao"] == ref_aprovacao
    return binds
