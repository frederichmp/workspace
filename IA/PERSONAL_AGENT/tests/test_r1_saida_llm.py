"""
R1 ampliada (docs/plans/1.11-R1-ampliada.md; docs/entregas/1.11/r1_ampliada/decisao_c1.md): o que volta ao LLM.

O resultado_tool vai ao coordenador, que pode ser o Gemini em nuvem. Estes testes conferem, com sentinelas, que
nenhum ramo das ferramentas Oracle leva ao LLM o DSN, host:porta, erro de rede, texto cru de exceção, usuário
protegido, aprovador, nome do pacote ou hashes (V1-V7), e que o código do erro continua lá (asserção positiva).
Sem Oracle: oracledb.connect é substituído por fakes; credenciais fictícias; ORACLE_SANDBOX não é tocada.
"""
import ast
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import oracledb
import pytest

from src.tools import oracle_dba as od
from src.tools.oracle_dba import calcular_hash_identidade
from tests.fakes_oracle import COLUNAS_ALVO, USER_DIAG_FAKE, USER_KILL_FAKE, _OracleFake, _linha_alvo

RAIZ = Path(__file__).resolve().parent.parent
DSN_SENTINELA = "host-sentinela-r1:1599/SVC_SENTINELA"
APROVADOR_SENTINELA = "aprovador-sentinela"
SENTINELAS = (
    "host-sentinela-r1", "1599", "SVC_SENTINELA", "rede-sentinela", "texto-sentinela", "exc-sentinela",
    "STARTUPADMIN", APROVADOR_SENTINELA, "PKG_OPS_KILL", "OPS_OWNER", "KILL_SESSION",
)
CHAVES_PROIBIDAS = ('"instancia"', '"detalhe_rede"', '"hash_aprovado"', '"hash_atual"')
REGEX_HASH = re.compile(r"[0-9a-f]{64}")
ERRO_ORA = oracledb.DatabaseError("ORA-99999: texto-sentinela")
ERRO_EXC = RuntimeError("exc-sentinela")
IDENTIDADE = {"username": "APP_USER", "program": "app.exe", "machine": "srv-app01",
              "logon_time": datetime(2026, 11, 23, 10, 0, 0)}
REF = "0123456789abcdef0123456789abcdef"
ARGS = {"inst_id": 1, "sid": 101, "serial": 202}


def _sem_vazamento(texto, caso):
    for sentinela in SENTINELAS:
        assert sentinela not in texto, f"{caso}: {sentinela!r} vai ao LLM"
    for chave in CHAVES_PROIBIDAS:
        assert chave not in texto, f"{caso}: chave {chave} vai ao LLM"
    assert not REGEX_HASH.search(texto), f"{caso}: hash de 64 hexadecimais vai ao LLM"


@pytest.fixture
def rede(monkeypatch):
    """Credenciais fictícias, DSN sentinela e sonda de rede controlável (falha na N-ésima chamada, ou sempre)."""
    monkeypatch.setenv("ORACLE_USER_DIAG", USER_DIAG_FAKE)
    monkeypatch.setenv("ORACLE_PASSWORD_DIAG", "senha-ficticia")
    monkeypatch.setenv("ORACLE_USER_KILL", USER_KILL_FAKE)
    monkeypatch.setenv("ORACLE_PASSWORD_KILL", "senha-ficticia")
    monkeypatch.setenv("ORACLE_DSN", DSN_SENTINELA)
    estado = {"falha_em": None, "chamadas": 0}

    def sonda(dsn, timeout=3.0):
        estado["chamadas"] += 1
        falha = estado["falha_em"] == "sempre" or estado["falha_em"] == estado["chamadas"]
        return {"acessivel": not falha, "host": "host-sentinela-r1", "porta": 1599, "latencia_ms": 0.1,
                "erro_rede": "rede-sentinela" if falha else None}

    monkeypatch.setattr(od, "verificar_acessibilidade_host", sonda)
    monkeypatch.setattr(od, "enviar_alerta_email", lambda assunto, corpo: (True, "mock"))
    return estado


# ---- fake das ferramentas de diagnóstico (o _OracleFake só cobre a consulta de alvo e o kill) ----

class _CursorDiag:
    def __init__(self):
        self.description, self._sql = None, ""

    def execute(self, sql, **binds):
        self._sql = sql
        if "COUNT(*)" in sql:
            self.description = [("COUNT(*)",)]
        elif "gv$sqlarea" in sql.lower():
            self.description = [(c,) for c in ("SQL_ID", "EXECUTIONS", "ELAPSED_SEG_TOTAL", "ELAPSED_POR_EXEC",
                                               "SQL_TEXT_CURTO")]
        elif "DBMS_XPLAN" in sql:
            self.description = [("PLAN_TABLE_OUTPUT",)]
        else:
            self.description = [(c,) for c in ("INST_ID", "SID", "serial#", "SERIAL", "USERNAME", "PROGRAM",
                                               "MACHINE", "STATUS", "SQL_ID", "EVENT")]

    def fetchone(self):
        return (3,)

    def fetchall(self):
        if "gv$sqlarea" in self._sql.lower():
            return [("abc123def4567", 10, 1.5, 0.15, "SELECT 1 FROM dual")]
        if "DBMS_XPLAN" in self._sql:
            return [("Plan hash value: 1",)]
        return [(1, 101, 202, 202, "APP_USER", "app.exe", "srv-app01", "ACTIVE", "abc123def4567", "ev")]

    def close(self):
        pass


def _instalar_diag(monkeypatch, erro_connect=None, erro_cursor=None):
    conexoes = []

    class _Conexao:
        def cursor(self):
            if erro_cursor is not None:
                raise erro_cursor
            return _CursorDiag()

        def close(self):
            pass

    def connect(*a, **k):
        conexoes.append(k.get("user"))
        if erro_connect is not None:
            raise erro_connect
        return _Conexao()

    monkeypatch.setattr(oracledb, "connect", connect)
    return conexoes


FERRAMENTAS_DIAG = {
    "sessoes": lambda: od.coletar_sessoes_ativas(),
    "top_sql": lambda: od.coletar_top_sql(),
    "plano": lambda: od.coletar_plano_execucao("abc123def4567"),
}
MOTIVO_ORACLE_DIAG = {"sessoes": "OracleError", "top_sql": "DatabaseError", "plano": "DatabaseError"}


@pytest.mark.parametrize("ferramenta", list(FERRAMENTAS_DIAG))
@pytest.mark.parametrize("ramo", ["sucesso", "erro_config", "rede", "erro_oracle", "excecao"])
def test_r1_varredura_ferramentas_de_diagnostico(monkeypatch, rede, ferramenta, ramo):
    """V1-V3 (decisao_c1.md §2.1-2.3) nas 3 ferramentas de diagnóstico, em todo ramo (os 15 casos do P0)."""
    if ramo == "erro_config":
        monkeypatch.delenv("ORACLE_USER_DIAG")
    if ramo == "rede":
        rede["falha_em"] = "sempre"
    conexoes = _instalar_diag(
        monkeypatch, erro_connect=ERRO_ORA if ramo == "erro_oracle" else None,
        erro_cursor=ERRO_EXC if ramo == "excecao" else None,
    )

    texto = FERRAMENTAS_DIAG[ferramenta]()
    resultado = json.loads(texto)

    _sem_vazamento(texto, f"{ferramenta}:{ramo}")
    esperado = {
        "sucesso": ("status", "sucesso"), "erro_config": ("motivo", "ERRO_CONFIG"),
        "rede": ("motivo", "HostInacessivelVPN"), "erro_oracle": ("motivo", MOTIVO_ORACLE_DIAG[ferramenta]),
        "excecao": ("motivo", "RuntimeError"),
    }[ramo]
    assert resultado[esperado[0]] == esperado[1]
    if ramo == "erro_oracle":
        assert resultado["codigo_erro"] == "ORA-99999" and "ORA-99999" in resultado["mensagem"]
    if ramo == "excecao":
        assert resultado["codigo_erro"] == "RuntimeError"
    if ramo == "rede":
        assert resultado["mensagem"] == od.TEXTO_HOST_INACESSIVEL_VPN
    assert (conexoes == []) == (ramo in ("erro_config", "rede"))


@pytest.mark.parametrize(
    "ramo, fake_kw, motivo",
    [
        ("erro_config", dict(status_pkg="ENCERRADA"), "ERRO_CONFIG"),
        ("rede", dict(status_pkg="ENCERRADA"), "HostInacessivelVPN"),
        ("erro_oracle_antes", dict(erro_connect_kill=ERRO_ORA), "ERRO_ORACLE"),
        ("erro_oracle_depois", dict(erro_kill=ERRO_ORA), "ERRO_ORACLE"),
        ("excecao_antes", dict(erro_var_kill=ERRO_EXC), "RuntimeError"),
        ("d8", dict(status_pkg="ENCERRADA", erro_getvalue_status=ERRO_EXC), "RuntimeError"),
        ("encerrada", dict(status_pkg="ENCERRADA"), "ENCERRADA"),
        ("recusa_pkg", dict(status_pkg="NAO_USUARIO"), "NAO_USUARIO"),
        ("desconhecido", dict(status_pkg=""), od.STATUS_PKG_VAZIO),
    ],
)
def test_r1_varredura_matar_sessao_oracle(monkeypatch, rede, ramo, fake_kw, motivo):
    """V1, V2, V3 e V6 em matar_sessao_oracle chamada direto, em todo ramo."""
    monkeypatch.setattr(oracledb, "connect", _OracleFake([], **fake_kw).connect)
    if ramo == "erro_config":
        monkeypatch.delenv("ORACLE_USER_KILL")
    if ramo == "rede":
        rede["falha_em"] = "sempre"

    texto = od.matar_sessao_oracle(sid=101, serial=202, inst_id=1, identidade_esperada=dict(IDENTIDADE),
                                   ref_aprovacao=REF)
    resultado = json.loads(texto)

    _sem_vazamento(texto, f"matar:{ramo}")
    assert resultado["motivo"] == motivo
    if ramo.startswith("erro_oracle"):
        assert resultado["codigo_erro"] == "ORA-99999" and "ORA-99999" in resultado["mensagem"]
    if ramo == "erro_oracle_depois":
        assert resultado["resultado_desconhecido"] is True
        assert od.MENSAGEM_RESULTADO_DESCONHECIDO in resultado["mensagem"]
    if ramo == "excecao_antes":
        assert resultado["mensagem"] == "RuntimeError" and resultado["resultado_desconhecido"] is False
    if ramo == "encerrada":
        assert resultado["mensagem"].startswith("Encerramento executado para inst_id=1, sid=101, serial=202.")


def _connect_diag_falhando_na(fake, numero, erro):
    """connect do fake, mas a N-ésima conexão DIAG levanta `erro` (a 1ª é a pré-consulta, a 2ª a reconsulta)."""
    contagem = {"diag": 0}

    def connect(user=None, password=None, dsn=None, **kwargs):
        if user == USER_DIAG_FAKE:
            contagem["diag"] += 1
            if contagem["diag"] == numero:
                raise erro
        return fake.connect(user=user, password=password, dsn=dsn, **kwargs)

    return connect


@pytest.mark.parametrize("ramo", ["protegido", "erro_oracle", "excecao", "rede"])
def test_r1_varredura_pre_consulta(monkeypatch, rede, ramo):
    """V2, V3 e V4 na pré-consulta (preparar_intervencao_kill -> resultado_tool), antes do prompt."""
    linhas = [_linha_alvo(username="STARTUPADMIN")] if ramo == "protegido" else [_linha_alvo()]
    fake = _OracleFake(linhas, kill_permitido=False)
    connect = fake.connect
    if ramo in ("erro_oracle", "excecao"):
        connect = _connect_diag_falhando_na(fake, 1, ERRO_ORA if ramo == "erro_oracle" else ERRO_EXC)
    if ramo == "rede":
        rede["falha_em"] = "sempre"
    monkeypatch.setattr(oracledb, "connect", connect)

    prep = od.preparar_intervencao_kill(dict(ARGS), caminho_log=None)
    texto = prep["resultado_tool"]

    assert prep["requer_aprovacao"] is False
    _sem_vazamento(texto, f"preparar:{ramo}")
    motivo = {"protegido": "USUARIO_PROTEGIDO", "erro_oracle": "ERRO_ORACLE", "excecao": "RuntimeError",
              "rede": "HostInacessivelVPN"}[ramo]
    assert json.loads(texto)["motivo"] == motivo
    if ramo == "erro_oracle":
        assert "ORA-99999" in texto


def _aprovar_sentinela(prep):
    return "APROVADO", APROVADOR_SENTINELA, None


@pytest.mark.parametrize("ramo", ["rede", "erro_oracle", "excecao"])
def test_r1_varredura_reconsulta_no_fluxo_aprovado(monkeypatch, rede, tmp_path, ramo):
    """Achado novo do C1 (decisao_c1.md §2.8): a reconsulta repassa a mensagem da pré-consulta ao LLM pelo
    fluxo aprovado (executar_kill_verificado). A correção na origem cobre esse caminho."""
    fake = _OracleFake([_linha_alvo(), _linha_alvo()], kill_permitido=False)
    connect = fake.connect
    if ramo in ("erro_oracle", "excecao"):
        connect = _connect_diag_falhando_na(fake, 2, ERRO_ORA if ramo == "erro_oracle" else ERRO_EXC)
    if ramo == "rede":
        rede["falha_em"] = 2  # 1ª sonda: pré-consulta; 2ª: reconsulta
    monkeypatch.setattr(oracledb, "connect", connect)

    desfecho = od.conduzir_kill_hitl(dict(ARGS), solicitar_aprovacao=_aprovar_sentinela, canal="TESTE",
                                     caminho_log=tmp_path / "k.log")
    texto = desfecho["resultado_tool"]

    _sem_vazamento(texto, f"reconsulta:{ramo}")
    assert fake.conexoes_kill == []
    banco = {"rede": "HostInacessivelVPN", "erro_oracle": "ERRO_ORACLE", "excecao": "RuntimeError"}[ramo]
    assert desfecho["resultado_banco"] == banco
    if ramo == "erro_oracle":
        assert "ORA-99999" in texto


def test_r1_varredura_reconsulta_usuario_protegido(monkeypatch, rede):
    """V4 pela reconsulta: o fluxo não alcança este ramo (o hash é conferido antes da elegibilidade e o username
    entra no hash), então executar_kill_verificado é chamado direto com o hash da identidade protegida."""
    alvo = dict(zip([c.lower() for c in COLUNAS_ALVO], _linha_alvo(username="STARTUPADMIN")))
    monkeypatch.setattr(oracledb, "connect", _OracleFake([_linha_alvo(username="STARTUPADMIN")]).connect)

    texto = od.executar_kill_verificado(
        inst_id=1, sid=101, serial=202, hash_aprovado=calcular_hash_identidade(alvo),
        aprovacao_expirada=lambda: False, ref_aprovacao=REF,
    )

    _sem_vazamento(texto, "reconsulta:protegido")
    assert json.loads(texto)["motivo"] == "USUARIO_PROTEGIDO"


@pytest.mark.parametrize("ramo", ["encerrada", "alvo_alterado", "erro_oracle_depois", "rejeitado"])
def test_r1_varredura_fluxo_hitl(monkeypatch, rede, tmp_path, ramo):
    """V3, V5, V6 e V7 no resultado_tool do fluxo HITL (o aprovador é a sentinela)."""
    linhas = [_linha_alvo(), _linha_alvo(machine="outra-maquina")] if ramo == "alvo_alterado" else [_linha_alvo(), _linha_alvo()]
    fake_kw = {"encerrada": dict(status_pkg="ENCERRADA"), "erro_oracle_depois": dict(erro_kill=ERRO_ORA)}.get(ramo, {})
    monkeypatch.setattr(oracledb, "connect", _OracleFake(linhas, kill_permitido=ramo != "alvo_alterado", **fake_kw).connect)
    decisao = "REJEITADO" if ramo == "rejeitado" else "APROVADO"

    desfecho = od.conduzir_kill_hitl(dict(ARGS), solicitar_aprovacao=lambda prep: (decisao, APROVADOR_SENTINELA, None),
                                     canal="TESTE", caminho_log=tmp_path / "k.log")
    texto = desfecho["resultado_tool"]

    _sem_vazamento(texto, f"fluxo:{ramo}")
    esperado = {"encerrada": "ENCERRADA", "alvo_alterado": "ALVO_ALTERADO", "erro_oracle_depois": "ERRO_ORACLE",
                "rejeitado": None}[ramo]
    assert desfecho["resultado_banco"] == esperado
    if ramo == "erro_oracle_depois":
        assert "ORA-99999" in texto


def test_r1_schema_das_ferramentas_oracle_sem_nome_do_pacote():
    """V6: a descrição das ferramentas vai ao LLM em toda chamada; não nomeia o pacote."""
    texto = json.dumps(od.oracle_tools_schema, ensure_ascii=False)
    for proibido in ("PKG_OPS_KILL", "OPS_OWNER", "KILL_SESSION"):
        assert proibido not in texto


# ---- peças comuns (decisao_c1.md §1) ----

@pytest.mark.parametrize(
    "exc, esperado",
    [
        (oracledb.DatabaseError("ORA-00600: erro interno [x]"), "ORA-00600"),
        (oracledb.DatabaseError("DPY-4008: no bind placeholder"), "DPY-4008"),
        (oracledb.DatabaseError("TNS-12541: no listener"), "TNS-12541"),
        (oracledb.DatabaseError("DPI-1047: cannot locate"), "DPI-1047"),
        (oracledb.DatabaseError("sem código texto-sentinela"), "DatabaseError"),
        (RuntimeError("ORA-00600 texto-sentinela"), "RuntimeError"),
    ],
)
def test_r1_codigo_erro_so_o_codigo(exc, esperado):
    """_codigo_erro: o 1º código de um oracledb.Error; senão o nome do tipo. Nunca o texto."""
    assert od._codigo_erro(exc) == esperado


def test_r1_codigo_erro_nunca_levanta():
    class _StrQuebrado(oracledb.DatabaseError):
        def __str__(self):
            raise ValueError("quebrado")

    assert od._codigo_erro(_StrQuebrado()) == "_StrQuebrado"


def test_r1_registrar_erro_local_leva_o_detalhe_ao_log_e_nunca_levanta(caplog):
    with caplog.at_level(logging.WARNING, logger=od.logger.name):
        od._registrar_erro_local("ferramenta_x", "ERRO_ORACLE", exc=ERRO_ORA,
                                 rede={"host": "host-sentinela-r1", "porta": 1599, "erro_rede": "rede-sentinela"})
        od._registrar_erro_local("ferramenta_x", "X", rede="não é dict")
    texto = caplog.text
    assert "texto-sentinela" in texto and "host-sentinela-r1:1599" in texto and "rede-sentinela" in texto


@pytest.mark.parametrize(
    "base_url, esperado",
    [
        ("http://localhost:11434/v1", True), ("http://127.0.0.1:11434/v1", True), ("http://[::1]:11434/v1", True),
        ("https://generativelanguage.googleapis.com/v1beta/openai/", False),
        ("http://localhost.evil.com/v1", False), ("http://127.0.0.1.nip.io/v1", False), ("", False),
    ],
)
def test_r1_coordenador_e_local_pelo_hostname_exato(base_url, esperado):
    class _Cliente:
        pass

    cliente = _Cliente()
    cliente.base_url = base_url
    assert od.coordenador_e_local(cliente) is esperado


def test_r1_coordenador_e_local_falha_fechada():
    class _SemBaseUrl:
        pass

    class _BaseUrlLevanta:
        @property
        def base_url(self):
            raise RuntimeError("x")

    assert od.coordenador_e_local(_SemBaseUrl()) is False
    assert od.coordenador_e_local(_BaseUrlLevanta()) is False
    assert od.coordenador_e_local(None) is False


@pytest.mark.parametrize(
    "mensagens, esperado",
    [
        ([], False),
        ([{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}], False),
        ([{"role": "tool", "name": "coletar_metricas_hardware", "content": "{}"}], False),
        ([{"role": "tool", "name": "buscar_script_interno", "content": "{}"}], False),
        ([{"role": "tool", "name": "coletar_sessoes_ativas", "content": od.RESULTADO_ORACLE_SO_LOCAL}], False),
        ([{"role": "tool", "name": "coletar_sessoes_ativas", "content": "{}"}], True),
        ([{"role": "tool", "name": "matar_sessao_oracle", "content": "{}"}], True),
        ([{"role": "tool", "content": "{}"}], True),
        ([{"role": "tool", "name": "ferramenta_nova", "content": "{}"}], True),
        ("não é lista", True),
        (None, True),
    ],
)
def test_r1_historico_tem_dado_do_banco(mensagens, esperado):
    assert od.historico_tem_dado_do_banco(mensagens) is esperado


def test_r1_nomes_sem_dado_do_banco_iguais_aos_schemas_de_so_e_rag():
    """A constante de oracle_dba (sem importar o RAG) tem de ser igual aos nomes de os_tools_schema e
    rag_tools_schema: ferramenta nova nesses schemas obriga a revisar a trava de histórico."""
    from src.tools.os_tools import os_tools_schema
    from src.tools.rag_search import rag_tools_schema

    nomes = {f["function"]["name"] for f in os_tools_schema + rag_tools_schema}
    assert od.NOMES_FERRAMENTAS_SEM_DADO_DO_BANCO == nomes
    assert nomes.isdisjoint({f["function"]["name"] for f in od.oracle_tools_schema})


# ---- AST (decisao_c1.md §8.4) ----

ARQUIVOS_AST = ["src/tools/oracle_dba.py"]
CHAVES_PROIBIDAS_AST = {"instancia", "hash_aprovado", "hash_atual", "detalhe_rede"}
FUNCOES_PERMITIDAS_COM_EXCECAO = {"type", "isinstance", "getattr", "_codigo_erro", "_registrar_erro_local"}
FUNCOES_QUE_PODEM_DESCREVER = {"_codigo_erro", "_registrar_erro_local"}


def _arvore(rel):
    return ast.parse((RAIZ / rel).read_text(encoding="utf-8"), filename=rel)


def _pais(arvore):
    pais = {}
    for no in ast.walk(arvore):
        for filho in ast.iter_child_nodes(no):
            pais[filho] = no
    return pais


def _e_chamada_de_log(no):
    return (
        isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
        and isinstance(no.func.value, ast.Name) and no.func.value.id in ("logger", "logging")
    )


def _nome_da_chamada(no):
    if isinstance(no.func, ast.Name):
        return no.func.id
    if isinstance(no.func, ast.Attribute):
        return no.func.attr
    return None


@pytest.mark.parametrize("rel", ARQUIVOS_AST)
def test_r1_ast_a1_json_dumps_sem_chaves_proibidas(rel):
    """A1: nenhum json.dumps com dict literal leva instancia, hash_aprovado, hash_atual ou detalhe_rede."""
    achados = []
    for no in ast.walk(_arvore(rel)):
        if isinstance(no, ast.Call) and _nome_da_chamada(no) == "dumps" and no.args:
            for dicionario in ast.walk(no.args[0]):
                if isinstance(dicionario, ast.Dict):
                    for chave in dicionario.keys:
                        if isinstance(chave, ast.Constant) and chave.value in CHAVES_PROIBIDAS_AST:
                            achados.append((chave.value, chave.lineno))
    assert achados == [], f"{rel}: {achados}"


@pytest.mark.parametrize("rel", ARQUIVOS_AST)
def test_r1_ast_a2_excecao_so_em_tipo_codigo_registro_ou_log(rel):
    """A2: dentro de `except ... as X`, X só aparece em type/isinstance/getattr, como argumento de _codigo_erro ou
    _registrar_erro_local, ou dentro de uma chamada logger.*/logging.* (nunca str(X) ou f"{X}" ao LLM)."""
    arvore = _arvore(rel)
    pais = _pais(arvore)
    achados = []
    for handler in ast.walk(arvore):
        if not (isinstance(handler, ast.ExceptHandler) and handler.name):
            continue
        for comando in handler.body:
            for no in ast.walk(comando):
                if not (isinstance(no, ast.Name) and no.id == handler.name and isinstance(no.ctx, ast.Load)):
                    continue
                ancestral, permitido = pais.get(no), False
                while ancestral is not None and ancestral is not handler:
                    if isinstance(ancestral, ast.Call) and (
                        _nome_da_chamada(ancestral) in FUNCOES_PERMITIDAS_COM_EXCECAO or _e_chamada_de_log(ancestral)
                    ):
                        permitido = True
                        break
                    ancestral = pais.get(ancestral)
                if not permitido:
                    achados.append((handler.name, no.lineno))
    assert achados == [], f"{rel}: uso da exceção fora do permitido em {achados}"


@pytest.mark.parametrize("rel", ARQUIVOS_AST)
def test_r1_ast_a3_descrever_erro_so_nas_pecas_ou_no_log(rel):
    """A3: _descrever_erro (texto cru) só é chamado dentro de _codigo_erro, _registrar_erro_local ou de log."""
    arvore = _arvore(rel)
    pais = _pais(arvore)
    achados = []
    for no in ast.walk(arvore):
        if not (isinstance(no, ast.Call) and _nome_da_chamada(no) == "_descrever_erro"):
            continue
        ancestral, permitido = pais.get(no), False
        while ancestral is not None:
            if isinstance(ancestral, ast.FunctionDef) and ancestral.name in FUNCOES_QUE_PODEM_DESCREVER:
                permitido = True
                break
            if _e_chamada_de_log(ancestral):
                permitido = True
                break
            ancestral = pais.get(ancestral)
        if not permitido:
            achados.append(no.lineno)
    assert achados == [], f"{rel}: _descrever_erro fora do permitido nas linhas {achados}"
