"""
Item 1 da tarefa 1.11: ordem fail-closed da aprovação (INTENCAO antes do kill, RESULTADO depois).
Especificação: docs/entregas/1.11/item1/decisao.md (T1-T12, §d1) e docs/plans/1.11.md (item 1).

Todos os testes são sem conexão: _OracleFake, ambiente_fake, log em tmp_path e contas fictícias.
Nenhum skip de plataforma. Falhas de E/S são injetadas assim:
  - monkeypatch.setattr(oracle_dba, "open", proxy, raising=False) (sombreia o `open` builtin só no módulo);
  - monkeypatch.setattr(os, "fsync", ...);
  - monkeypatch.setattr(oracle_dba, "_fsync_diretorio" / "_FSYNC_DIRETORIO" / "_travar_arquivo", ...).
Os subprocessos (`python -I`) não importam o .env: o módulo `dotenv` é substituído por um falso no filho,
e o filho de lock usa só msvcrt/fcntl.
"""
from datetime import datetime, timedelta, timezone
import errno
import json
import logging
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
import time

import oracledb
import pytest

from src.tools import oracle_dba
from src.tools.oracle_dba import (
    LockLogAprovacaoIndisponivel,
    MENSAGEM_RESULTADO_DESCONHECIDO,
    RECONCILIACAO_IDADE_MINIMA_SEGUNDOS,
    calcular_hash_identidade,
    conduzir_kill_hitl,
    reconciliar_intencoes_orfas,
    registrar_decisao_kill,
    registrar_log_aprovacao_kill,
)
from tests.fakes_oracle import (
    COLUNAS_ALVO,
    USER_DIAG_FAKE,
    USER_KILL_FAKE,
    _OracleFake,
    _linha_alvo,
)
from tests.test_oracle_kill import (  # noqa: F401  (ambiente_fake é uma fixture)
    ARGS_ALVO,
    _aprovar,
    _instalar_oracle,
    _relogio_relativo,
    _solicitar_capturando,
    ambiente_fake,
)

RAIZ = Path(__file__).resolve().parent.parent
ID_A = "a" * 32
ID_B = "b" * 32
ID_C = "c" * 32


# =============================================================================
# Utilitários
# =============================================================================

def _ler_jsonl(caminho):
    """Linhas JSON válidas do arquivo (linhas ilegíveis são ignoradas); arquivo ausente -> []."""
    if not Path(caminho).exists():
        return []
    validas = []
    for linha in Path(caminho).read_bytes().splitlines():
        try:
            validas.append(json.loads(linha.decode("utf-8")))
        except ValueError:
            continue
    return validas


def _fases_no_log(caminho):
    return [r.get("fase") for r in _ler_jsonl(caminho)]


def _contar_sonda(monkeypatch, estado=None):
    """Substitui a sonda TCP por uma que conta chamadas; estado["ok"]=False simula host inacessível."""
    chamadas = []

    def sonda(dsn, timeout=3.0):
        chamadas.append(1)
        ok = True if estado is None else estado.get("ok", True)
        return {
            "acessivel": ok, "host": "host-teste", "porta": 1521, "latencia_ms": 0.1,
            "erro_rede": None if ok else "bloqueado",
        }

    monkeypatch.setattr(oracle_dba, "verificar_acessibilidade_host", sonda)
    return chamadas


def _espiar_fsync(monkeypatch, eventos=None):
    """Conta os os.fsync em fd de arquivo regular (ignora fd de diretório)."""
    contagem = []
    real = os.fsync

    def espiao(fd):
        if stat.S_ISREG(os.fstat(fd).st_mode):
            contagem.append(1)
            if eventos is not None:
                eventos.append(("fsync",))
        return real(fd)

    monkeypatch.setattr(os, "fsync", espiao)
    return contagem


class _ArquivoProxy:
    """Envolve o arquivo real de `open(log, "a+b")` e injeta uma falha de E/S conforme o modo."""

    def __init__(self, real, modo):
        self._real = real
        self._modo = modo

    def __enter__(self):
        self._real.__enter__()
        return self

    def __exit__(self, *exc):
        resultado = self._real.__exit__(*exc)
        if self._modo == "close_levanta":
            raise OSError(errno.EIO, "close falhou (injetado)")
        return resultado

    def write(self, dados):
        if self._modo == "write_parcial":
            self._real.write(dados[: len(dados) // 2])
            self._real.flush()
            raise OSError(errno.ENOSPC, "sem espaço (injetado)")
        return self._real.write(dados)

    def flush(self):
        if self._modo == "flush_levanta":
            raise OSError(errno.EIO, "flush falhou (injetado)")
        return self._real.flush()

    def __getattr__(self, nome):
        return getattr(self._real, nome)


def _instalar_open_proxy(monkeypatch, nome_arquivo, modo, falhar_na_gravacao=None):
    """
    Sombreia `open` em oracle_dba. modo: "write_parcial" | "flush_levanta" | "close_levanta" (proxy do
    arquivo) ou "open_levanta" (o próprio open falha). falhar_na_gravacao: nº (1-based) da gravação em que a
    falha ocorre; None = todas. Devolve a lista de gravações observadas.
    """
    import builtins

    real_open = builtins.open
    gravacoes = []

    def _open(path, mode="r", *a, **k):
        if Path(path).name == nome_arquivo and mode == "a+b":
            gravacoes.append(1)
            if falhar_na_gravacao is None or len(gravacoes) == falhar_na_gravacao:
                if modo == "open_levanta":
                    raise OSError(errno.EIO, "open falhou (injetado)")
                return _ArquivoProxy(real_open(path, mode, *a, **k), modo)
        return real_open(path, mode, *a, **k)

    monkeypatch.setattr(oracle_dba, "open", _open, raising=False)
    return gravacoes


def _alvo_dict(**kw):
    return dict(zip([c.lower() for c in COLUNAS_ALVO], _linha_alvo(**kw)))


# =============================================================================
# T1: INTENCAO gravada (com fsync) antes de qualquer conexão posterior à decisão
# =============================================================================

def test_intencao_gravada_antes_da_conta_kill(monkeypatch, tmp_path, ambiente_fake):
    """a, b: DIAG (log vazio) -> fsync -> DIAG (só INTENCAO) -> KILL (só INTENCAO) -> fsync; 2 linhas, mesmo id."""
    log = tmp_path / "kill.log"
    eventos = []
    fake = _OracleFake([_linha_alvo(), _linha_alvo()], status_pkg="ENCERRADA")

    def connect_espiao(**kw):
        eventos.append(("connect", kw.get("user"), _fases_no_log(log)))
        return fake.connect(**kw)

    monkeypatch.setattr(oracledb, "connect", connect_espiao)
    _espiar_fsync(monkeypatch, eventos)

    desfecho = conduzir_kill_hitl(dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log)

    assert eventos == [
        ("connect", USER_DIAG_FAKE, []),
        ("fsync",),
        ("connect", USER_DIAG_FAKE, ["INTENCAO"]),
        ("connect", USER_KILL_FAKE, ["INTENCAO"]),
        ("fsync",),
    ]
    registros = _ler_jsonl(log)
    assert [r["fase"] for r in registros] == ["INTENCAO", "RESULTADO"]
    intencao, resultado = registros
    assert intencao["decisao"] == "APROVADO" and intencao["resultado_banco"] is None
    assert intencao["id_intervencao"] == resultado["id_intervencao"] == desfecho["id_intervencao"]
    assert re.fullmatch(r"[0-9a-f]{32}", intencao["id_intervencao"])
    assert resultado["resultado_banco"] == "ENCERRADA"
    assert desfecho["falha_registro"] is None
    # Sem o item 6 (aa9a0a5 revertido): a chamada ao PKG continua v1 (4 binds), sem ref_aprovacao
    (_, _, binds), = [s for s in fake.sql_executado if s[0] == "KILL"]
    assert set(binds) == {"p_inst_id", "p_sid", "p_serial", "p_status"}


# =============================================================================
# T2: falha da INTENCAO -> FALHA_LOG_APROVACAO, sem KILL, sem reconsulta, sem e-mail
# =============================================================================

MODOS_T2 = [
    "caminho_diretorio", "encode_falha", "write_parcial", "flush_levanta", "fsync_levanta",
    "close_levanta", "fsync_diretorio_levanta", "lock_indisponivel", "makedirs_falha",
]


@pytest.mark.parametrize("modo", MODOS_T2)
def test_falha_log_intencao_nao_chama_kill(monkeypatch, tmp_path, ambiente_fake, caplog, modo):
    log = tmp_path / "kill.log"
    aprovador = "dba_teste"
    if modo == "caminho_diretorio":
        log = tmp_path / "log_e_diretorio"
        log.mkdir()
    elif modo == "encode_falha":
        aprovador = "dba\ud800"
    elif modo in ("write_parcial", "flush_levanta", "close_levanta"):
        _instalar_open_proxy(monkeypatch, log.name, modo)
    elif modo == "fsync_levanta":
        def _boom(fd):
            raise OSError(errno.EIO, "fsync falhou (injetado)")
        monkeypatch.setattr(os, "fsync", _boom)
    elif modo == "fsync_diretorio_levanta":
        def _boom_dir(diretorio):
            raise OSError(errno.EIO, "fsync do diretório falhou (injetado)")
        monkeypatch.setattr(oracle_dba, "_FSYNC_DIRETORIO", True)
        monkeypatch.setattr(oracle_dba, "_fsync_diretorio", _boom_dir)
    elif modo == "lock_indisponivel":
        def _travar_negado(fd):
            raise OSError(errno.EACCES, "lock negado (injetado)")
        monkeypatch.setattr(oracle_dba, "_travar_arquivo", _travar_negado)
        monkeypatch.setattr(oracle_dba, "LOCK_LOG_TIMEOUT_SEGUNDOS", 0.2)
    elif modo == "makedirs_falha":
        log = tmp_path / "pasta_inexistente" / "kill.log"

        def _makedirs_negado(*a, **k):
            raise PermissionError(errno.EACCES, "makedirs negado (injetado)")
        monkeypatch.setattr(os, "makedirs", _makedirs_negado)

    fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo(), _linha_alvo()], kill_permitido=False))
    sonda = _contar_sonda(monkeypatch)
    snapshot = {}

    def solicitar(prep):
        snapshot["conexoes"] = list(fake.conexoes)
        snapshot["sql"] = len(fake.sql_executado)
        snapshot["sonda"] = len(sonda)
        return "APROVADO", aprovador, None

    caplog.set_level(logging.INFO)
    desfecho = conduzir_kill_hitl(dict(ARGS_ALVO), solicitar_aprovacao=solicitar, canal="TESTE", caminho_log=log)

    assert desfecho["decisao"] == "APROVADO"
    assert desfecho["motivo"] == "FALHA_LOG_APROVACAO"
    assert desfecho["executado"] is False
    assert desfecho["resultado_banco"] is None
    assert desfecho["falha_registro"] == "INTENCAO"
    assert desfecho["registro"] is None
    assert desfecho["assunto_email"] is None
    id_interv = desfecho["id_intervencao"]
    assert re.fullmatch(r"[0-9a-f]{32}", id_interv)

    assert fake.conexoes == snapshot["conexoes"] == [USER_DIAG_FAKE]
    assert len(fake.sql_executado) == snapshot["sql"]
    assert len(sonda) == snapshot["sonda"] == 1, "nenhuma sonda TCP depois da decisão"
    assert fake.conexoes_kill == []
    assert ambiente_fake == [], "FALHA_LOG_APROVACAO não envia e-mail (decisão 2)"

    erros = [r for r in caplog.records if r.levelno == logging.ERROR and "FALHA_LOG_APROVACAO" in r.getMessage()]
    assert len(erros) == 1 and id_interv in erros[0].getMessage()
    assert "senha-fake" not in caplog.text

    tool = json.loads(desfecho["resultado_tool"])
    assert tool["status"] == "abortado" and tool["motivo"] == "FALHA_LOG_APROVACAO"
    assert tool["executado"] is False and tool["resultado_banco"] is None
    assert id_interv not in desfecho["resultado_tool"]

    if log.is_file() or modo == "encode_falha":
        validas = _ler_jsonl(log)
        assert "RESULTADO" not in [r.get("fase") for r in validas]
        assert len(validas) == 0 or (len(validas) == 1 and validas[0]["fase"] == "INTENCAO"
                                     and validas[0]["id_intervencao"] == id_interv)
    if modo == "encode_falha":
        assert not log.exists()
    if modo == "makedirs_falha":
        assert not log.parent.exists()


# =============================================================================
# T3 / T4 / T5 / T6: rotina de gravação
# =============================================================================

def test_linha_parcial_anterior_isolada(tmp_path):
    log = tmp_path / "kill.log"
    parcial = b'{"fase": "INTEN'
    log.write_bytes(parcial)

    res = registrar_decisao_kill(
        decisao="REJEITADO", aprovador="dba_teste", inst_id=1, sid=101, serial=202, alvo={},
        hash_aprovado="h", canal="TESTE", preparado_em=None, motivo="REJEITADO_PELO_APROVADOR", caminho_log=log,
    )

    assert res["falha_registro"] is None
    linhas = log.read_bytes().split(b"\n")
    assert linhas[0] == parcial, "a linha parcial fica intacta e isolada"
    ultima = json.loads(linhas[1])
    assert ultima["fase"] == "RESULTADO" and ultima["decisao"] == "REJEITADO"
    assert linhas[2] == b""


def test_log_aprovacao_faz_fsync(monkeypatch, tmp_path, ambiente_fake):
    """1 fsync por REJEITADO, 2 por APROVADO; bytes terminam em LF e não contêm CRLF (modo binário)."""
    contagem = _espiar_fsync(monkeypatch)
    log = tmp_path / "kill.log"

    registrar_decisao_kill(
        decisao="REJEITADO", aprovador="dba_teste", inst_id=1, sid=101, serial=202, alvo={},
        hash_aprovado="h", canal="TESTE", preparado_em=None, motivo="REJEITADO_PELO_APROVADOR", caminho_log=log,
    )
    assert len(contagem) == 1
    antes = log.read_bytes()
    assert antes.endswith(b"\n") and b"\r\n" not in antes

    _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo(), _linha_alvo()], status_pkg="ENCERRADA"))
    contagem.clear()
    desfecho = conduzir_kill_hitl(dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log)
    assert desfecho["executado"] is True
    assert len(contagem) == 2
    novos = log.read_bytes()[len(antes):]
    assert novos.endswith(b"\n") and b"\r\n" not in novos


@pytest.mark.parametrize("fsync_dir_ativo", [True, False], ids=["posix", "windows"])
def test_fsync_diretorio_so_quando_arquivo_novo(monkeypatch, tmp_path, fsync_dir_ativo):
    chamadas = []
    monkeypatch.setattr(oracle_dba, "_FSYNC_DIRETORIO", fsync_dir_ativo)
    monkeypatch.setattr(oracle_dba, "_fsync_diretorio", lambda d: chamadas.append(Path(d)))
    log = tmp_path / "kill.log"

    for id_ in (ID_A, ID_B):
        registrar_log_aprovacao_kill(
            "dba_teste", "REJEITADO", "h", {"sid": 1}, motivo="T", caminho_log=log,
            fase="RESULTADO", id_intervencao=id_,
        )
    assert chamadas == ([log.parent] if fsync_dir_ativo else [])


def test_registro_fase_e_id_validados(tmp_path):
    log = tmp_path / "kill.log"
    base = dict(aprovador="dba", hash_payload="h", parametros={}, caminho_log=log)

    with pytest.raises(TypeError):
        registrar_log_aprovacao_kill(decisao="REJEITADO", id_intervencao=ID_A, **base)  # sem fase
    with pytest.raises(TypeError):
        registrar_log_aprovacao_kill(decisao="REJEITADO", fase="RESULTADO", **base)  # sem id
    for kw in (
        dict(decisao="REJEITADO", fase="X", id_intervencao=ID_A),
        dict(decisao="REJEITADO", fase="INTENCAO", id_intervencao=ID_A),
        dict(decisao="APROVADO", fase="INTENCAO", id_intervencao=ID_A, resultado_banco="ENCERRADA"),
        dict(decisao="REJEITADO", fase="RESULTADO", id_intervencao="abc"),
        dict(decisao="REJEITADO", fase="RESULTADO", id_intervencao="A" * 32),
        dict(decisao="REJEITADO", fase="RESULTADO", id_intervencao=None),
        dict(decisao="INVALIDA", fase="RESULTADO", id_intervencao=ID_A),
    ):
        with pytest.raises(ValueError):
            registrar_log_aprovacao_kill(**kw, **base)
    assert not log.exists()


# =============================================================================
# T7: TTL vence entre a reconsulta e o kill
# =============================================================================

def test_ttl_vence_entre_reconsulta_e_kill(monkeypatch, tmp_path, ambiente_fake):
    fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo(), _linha_alvo()], kill_permitido=False))
    log = tmp_path / "kill.log"
    cap = {}
    leituras = []

    def relogio():
        leituras.append(1)
        return datetime.fromisoformat(cap["ts"]) + timedelta(seconds=10 if len(leituras) == 1 else 301)

    desfecho = conduzir_kill_hitl(
        dict(ARGS_ALVO), solicitar_aprovacao=_solicitar_capturando(cap), canal="TESTE",
        caminho_log=log, agora=relogio,
    )

    assert len(leituras) == 2, "o relógio é lido na decisão e no recheck"
    assert fake.conexoes.count(USER_DIAG_FAKE) == 2
    assert fake.conexoes_kill == []
    assert desfecho["decisao"] == "APROVADO"
    assert desfecho["resultado_banco"] == "APROVACAO_EXPIRADA"
    assert desfecho["executado"] is False
    intencao, resultado = _ler_jsonl(log)
    assert intencao["fase"] == "INTENCAO" and resultado["fase"] == "RESULTADO"
    assert resultado["resultado_banco"] == "APROVACAO_EXPIRADA" and resultado["decisao"] == "APROVADO"
    assert intencao["id_intervencao"] == resultado["id_intervencao"]
    assert len(ambiente_fake) == 1 and "NÃO executada" in ambiente_fake[0]["assunto"]


# =============================================================================
# T8: RESULTADO por caso de falha
# =============================================================================

_ALVO = _linha_alvo()
CASOS_T8 = [
    pytest.param(
        dict(linhas=[_ALVO, _ALVO], fake=dict(erro_kill=oracledb.DatabaseError("ORA-00600: erro interno")),
             esperado="ERRO_ORACLE", kill=1, email="desconhecido"),
        id="ora00600",
    ),
    pytest.param(
        dict(linhas=[_ALVO, _ALVO], fake=dict(erro_connect_kill=oracledb.DatabaseError("ORA-12541: sem listener")),
             esperado="ERRO_ORACLE", kill=1, email="nao_executada"),
        id="erro_connect_kill",
    ),
    pytest.param(
        dict(linhas=[_ALVO, None], esperado="ALVO_NAO_ENCONTRADO", kill=0, email="nao_executada"),
        id="alvo_nao_encontrado_reconsulta",
    ),
    pytest.param(
        dict(linhas=[_ALVO, _linha_alvo(tipo="BACKGROUND")], esperado="NAO_USUARIO", kill=0, email="nao_executada"),
        id="nao_usuario_reconsulta",
    ),
    pytest.param(
        dict(direto="protegido", esperado="USUARIO_PROTEGIDO", kill=0, email="nao_executada"),
        id="usuario_protegido_reconsulta",
    ),
    pytest.param(
        dict(linhas=[_ALVO, _ALVO], hook="delenv_diag", esperado="ERRO_CONFIG", kill=0, email="nao_executada"),
        id="erro_config_diag",
    ),
    pytest.param(
        dict(linhas=[_ALVO, _ALVO], hook="sonda_falha", esperado="HostInacessivelVPN", kill=0,
             email="nao_executada"),
        id="host_inacessivel",
    ),
    pytest.param(
        dict(linhas=[_ALVO, _ALVO], hook="delenv_kill", esperado="ERRO_CONFIG", kill=0, email="nao_executada"),
        id="erro_config_kill",
    ),
    pytest.param(
        dict(direto="param_invalido", esperado="PARAM_INVALIDO", kill=0, email="nao_executada"),
        id="param_invalido_reconsulta",
    ),
]


@pytest.mark.parametrize("caso", CASOS_T8)
def test_resultado_por_caso_de_falha(monkeypatch, tmp_path, ambiente_fake, caso):
    """
    Exatamente 2 linhas (INTENCAO e RESULTADO, mesmo id) por caso.

    Limites declarados:
      - usuario_protegido_reconsulta: o `hash_aprovado` é calculado sobre a mesma identidade da reconsulta
        (hash COINCIDENTE). Isso exercita a elegibilidade na reconsulta, mas NÃO exercita hash divergente real:
        um alvo protegido nunca chega a ser aprovado pelo fluxo normal (a pré-consulta o recusa).
      - param_invalido_reconsulta: com o aa9a0a5 revertido não existe a identidade da reconsulta; o
        PARAM_INVALIDO local de matar_sessao_oracle (oracle_dba.py:703) é inalcançável por
        executar_kill_verificado, porque consultar_alvo_sessao_diag (oracle_dba.py:553) aplica antes a mesma
        validar_parametros_kill; ele é coberto por test_kill_param_invalido_sem_conexao. O caso usa sid=0 em
        chamada direta: PARAM_INVALIDO na reconsulta, sem nenhuma conexão.
    """
    log = tmp_path / "kill.log"
    fake = _instalar_oracle(
        monkeypatch,
        _OracleFake(caso.get("linhas", []), status_pkg=None, kill_permitido=caso["kill"] > 0, **caso.get("fake", {})),
    )
    estado_sonda = {"ok": True}
    _contar_sonda(monkeypatch, estado_sonda)

    if caso.get("direto"):
        if caso["direto"] == "protegido":
            alvo = _alvo_dict(username="SYS")
            fake.linhas_diag.append(_linha_alvo(username="SYS"))
            sid, hash_ap = 101, calcular_hash_identidade(alvo)
        else:
            alvo, sid, hash_ap = _alvo_dict(), 0, "hash-qualquer"
        desfecho = registrar_decisao_kill(
            decisao="APROVADO", aprovador="dba_teste", inst_id=1, sid=sid, serial=202, alvo=alvo,
            hash_aprovado=hash_ap, canal="TESTE", preparado_em=datetime.now(timezone.utc).isoformat(),
            caminho_log=log,
        )
    else:
        def solicitar(prep):
            if caso.get("hook") == "delenv_diag":
                monkeypatch.delenv("ORACLE_USER_DIAG")
            elif caso.get("hook") == "delenv_kill":
                monkeypatch.delenv("ORACLE_USER_KILL")
            elif caso.get("hook") == "sonda_falha":
                estado_sonda["ok"] = False
            return "APROVADO", "dba_teste", None

        desfecho = conduzir_kill_hitl(dict(ARGS_ALVO), solicitar_aprovacao=solicitar, canal="TESTE", caminho_log=log)

    if caso.get("direto") == "param_invalido":
        assert fake.conexoes == [], "PARAM_INVALIDO na reconsulta: nenhuma conexão DIAG nem KILL"

    registros = _ler_jsonl(log)
    assert [r["fase"] for r in registros] == ["INTENCAO", "RESULTADO"]
    intencao, resultado = registros
    assert intencao["id_intervencao"] == resultado["id_intervencao"] == desfecho["id_intervencao"]
    assert intencao["resultado_banco"] is None
    assert resultado["resultado_banco"] == caso["esperado"]
    assert resultado["decisao"] == "APROVADO"
    assert desfecho["resultado_banco"] == caso["esperado"]
    assert desfecho["executado"] is False
    assert desfecho["falha_registro"] is None
    assert len(fake.conexoes_kill) == caso["kill"]

    assert len(ambiente_fake) == 1
    assunto = ambiente_fake[0]["assunto"]
    tool = json.loads(desfecho["resultado_tool"])
    if caso["email"] == "desconhecido":
        assert MENSAGEM_RESULTADO_DESCONHECIDO in assunto and "NÃO executada" not in assunto
        assert desfecho["resultado_desconhecido"] is True
        assert tool["resultado_desconhecido"] is True and MENSAGEM_RESULTADO_DESCONHECIDO in tool["mensagem"]
    else:
        assert "NÃO executada" in assunto and MENSAGEM_RESULTADO_DESCONHECIDO not in assunto
        assert desfecho["resultado_desconhecido"] is False
        assert MENSAGEM_RESULTADO_DESCONHECIDO not in desfecho["resultado_tool"]


def test_pls00306_no_execute_e_resultado_desconhecido(monkeypatch, tmp_path, ambiente_fake):
    """Inclusive PLS-00306: erro a partir do execute do KILL_SESSION = resultado desconhecido."""
    log = tmp_path / "kill.log"
    fake = _instalar_oracle(
        monkeypatch,
        _OracleFake([_linha_alvo(), _linha_alvo()], erro_kill=oracledb.DatabaseError("PLS-00306: wrong number")),
    )
    desfecho = conduzir_kill_hitl(dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log)
    assert desfecho["resultado_banco"] == "ERRO_ORACLE" and desfecho["resultado_desconhecido"] is True
    assert [s for s in fake.sql_executado if s[0] == "KILL"].__len__() == 1, "sem nova tentativa"
    assert MENSAGEM_RESULTADO_DESCONHECIDO in desfecho["resultado_tool"]
    assert MENSAGEM_RESULTADO_DESCONHECIDO in ambiente_fake[0]["assunto"]


# =============================================================================
# T9 / T10: exceções dentro do fluxo
# =============================================================================

def _sonda_que_levanta_na_2a(monkeypatch, excecao):
    chamadas = []

    def sonda(dsn, timeout=3.0):
        chamadas.append(1)
        if len(chamadas) == 2:
            raise excecao
        return {"acessivel": True, "host": "host-teste", "porta": 1521, "latencia_ms": 0.1}

    monkeypatch.setattr(oracle_dba, "verificar_acessibilidade_host", sonda)


def test_erro_interno_grava_resultado(monkeypatch, tmp_path, ambiente_fake, caplog):
    fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo(), _linha_alvo()], kill_permitido=False))
    _sonda_que_levanta_na_2a(monkeypatch, RuntimeError("segredo-xyz"))
    log = tmp_path / "kill.log"
    caplog.set_level(logging.INFO)

    desfecho = conduzir_kill_hitl(dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log)

    intencao, resultado = _ler_jsonl(log)
    assert intencao["fase"] == "INTENCAO" and resultado["fase"] == "RESULTADO"
    assert resultado["resultado_banco"] == "ERRO_INTERNO" and resultado["motivo"] == "RuntimeError"
    assert intencao["id_intervencao"] == resultado["id_intervencao"]
    assert fake.conexoes_kill == []
    assert len(ambiente_fake) == 1 and "NÃO executada" in ambiente_fake[0]["assunto"]
    assert desfecho["resultado_banco"] == "ERRO_INTERNO" and desfecho["executado"] is False
    assert "segredo-xyz" not in log.read_text(encoding="utf-8")
    assert "segredo-xyz" not in desfecho["resultado_tool"]
    assert "segredo-xyz" not in caplog.text


def test_interrupcao_grava_resultado_e_propaga(monkeypatch, tmp_path, ambiente_fake, caplog):
    fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo(), _linha_alvo()], kill_permitido=False))
    _sonda_que_levanta_na_2a(monkeypatch, KeyboardInterrupt())
    log = tmp_path / "kill.log"
    caplog.set_level(logging.INFO)

    with pytest.raises(KeyboardInterrupt):
        conduzir_kill_hitl(dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log)

    intencao, resultado = _ler_jsonl(log)
    assert resultado["fase"] == "RESULTADO"
    assert resultado["resultado_banco"] == "INTERROMPIDO" and resultado["motivo"] == "KeyboardInterrupt"
    assert intencao["id_intervencao"] == resultado["id_intervencao"]
    assert fake.conexoes_kill == []
    assert ambiente_fake == [], "interrupção não envia e-mail"
    criticos = [r for r in caplog.records if r.levelno == logging.CRITICAL and "INTERROMPIDO" in r.getMessage()]
    assert len(criticos) == 1 and resultado["id_intervencao"] in criticos[0].getMessage()


def test_interrupcao_com_gravacao_falhando_vai_para_o_critical(monkeypatch, tmp_path, ambiente_fake, caplog):
    """T10 (variante): a gravação do INTERROMPIDO (2ª) falha -> o CRITICAL leva o registro."""
    _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo(), _linha_alvo()], kill_permitido=False))
    _sonda_que_levanta_na_2a(monkeypatch, KeyboardInterrupt())
    log = tmp_path / "kill.log"
    _instalar_open_proxy(monkeypatch, log.name, "open_levanta", falhar_na_gravacao=2)
    caplog.set_level(logging.INFO)

    with pytest.raises(KeyboardInterrupt):
        conduzir_kill_hitl(dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log)

    assert [r["fase"] for r in _ler_jsonl(log)] == ["INTENCAO"]
    criticos = [r.getMessage() for r in caplog.records if r.levelno == logging.CRITICAL and "INTERROMPIDO" in r.getMessage()]
    assert len(criticos) == 1 and "RESULTADO NAO GRAVADA" in criticos[0]
    serializado = json.loads(criticos[0].split("registro=", 1)[1])
    assert serializado["resultado_banco"] == "INTERROMPIDO"


# =============================================================================
# T11 / T12: falha da gravação da RESULTADO
# =============================================================================

def test_falha_registro_resultado_nao_silenciosa(monkeypatch, tmp_path, ambiente_fake, caplog):
    fake = _instalar_oracle(monkeypatch, _OracleFake([_linha_alvo(), _linha_alvo()], status_pkg="ENCERRADA"))
    log = tmp_path / "kill.log"
    _instalar_open_proxy(monkeypatch, log.name, "open_levanta", falhar_na_gravacao=2)
    caplog.set_level(logging.INFO)

    desfecho = conduzir_kill_hitl(dict(ARGS_ALVO), solicitar_aprovacao=_aprovar(), canal="TESTE", caminho_log=log)

    assert fake.conexoes_kill == [USER_KILL_FAKE]
    assert desfecho["falha_registro"] == "RESULTADO" and desfecho["registro"] is None
    assert desfecho["executado"] is True and desfecho["resultado_banco"] == "ENCERRADA"
    id_interv = desfecho["id_intervencao"]
    criticos = [r.getMessage() for r in caplog.records if r.levelno == logging.CRITICAL]
    assert len(criticos) == 1
    assert id_interv in criticos[0] and '"resultado_banco": "ENCERRADA"' in criticos[0]
    registro_serializado = json.loads(criticos[0].split("registro=", 1)[1])
    assert registro_serializado["id_intervencao"] == id_interv and registro_serializado["fase"] == "RESULTADO"
    assert len(ambiente_fake) == 1
    assert ambiente_fake[0]["assunto"].startswith("[REGISTRO DE RESULTADO FALHOU] ")
    assert "id_intervencao=" + id_interv in ambiente_fake[0]["corpo"]
    assert [r["fase"] for r in _ler_jsonl(log)] == ["INTENCAO"]


@pytest.mark.parametrize("decisao", ["REJEITADO", "TIMEOUT"])
def test_falha_registro_rejeitado_e_timeout(monkeypatch, tmp_path, ambiente_fake, caplog, decisao):
    fake = _instalar_oracle(monkeypatch, _OracleFake([], kill_permitido=False))
    log = tmp_path / "kill.log"
    _instalar_open_proxy(monkeypatch, log.name, "open_levanta")
    caplog.set_level(logging.INFO)

    desfecho = registrar_decisao_kill(
        decisao=decisao, aprovador="dba_teste", inst_id=1, sid=101, serial=202, alvo=_alvo_dict(),
        hash_aprovado="h-fake", canal="TESTE", preparado_em=None, caminho_log=log,
    )

    assert desfecho["decisao"] == decisao
    assert desfecho["falha_registro"] == "RESULTADO" and desfecho["registro"] is None
    assert desfecho["executado"] is False
    assert fake.conexoes_kill == [] and fake.conexoes == []
    assert ambiente_fake == []
    erros = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR and "registro=" in r.getMessage()]
    assert len(erros) == 1
    serializado = json.loads(erros[0].split("registro=", 1)[1])
    assert serializado["fase"] == "RESULTADO" and serializado["decisao"] == decisao
    assert serializado["id_intervencao"] == desfecho["id_intervencao"]
    assert not log.exists()


# =============================================================================
# Reconciliador
# =============================================================================

AGORA = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)
IDADE_MIN = RECONCILIACAO_IDADE_MINIMA_SEGUNDOS


def _intencao(id_, idade_s, timestamp=None, aprovador="dba_teste"):
    ts = timestamp if timestamp is not None else (AGORA - timedelta(seconds=idade_s)).isoformat()
    return {
        "timestamp": ts, "fase": "INTENCAO", "id_intervencao": id_, "aprovador": aprovador,
        "decisao": "APROVADO", "resultado_banco": None, "motivo": None, "hash_payload": "h-" + id_[:4],
        "parametros": {"inst_id": 1, "sid": 101, "serial": 202}, "alvo": {"username": "APP_USER"},
    }


def _resultado(id_, resultado_banco="ENCERRADA", idade_s=0):
    reg = _intencao(id_, idade_s)
    reg.update(fase="RESULTADO", resultado_banco=resultado_banco)
    return reg


def _escrever(caminho, registros, bruto_final=b""):
    dados = b"".join((json.dumps(r) + "\n").encode("utf-8") for r in registros)
    Path(caminho).write_bytes(dados + bruto_final)


def _reconciliar(log):
    return reconciliar_intencoes_orfas(caminho_log=log, agora=lambda: AGORA)


def test_reconciliador_constante_e_ttl():
    assert IDADE_MIN == oracle_dba.APROVACAO_TTL_SEGUNDOS + 300 == 600


def test_reconciliador_intencao_antiga_vira_nao_concluida(tmp_path):
    log = tmp_path / "kill.log"
    antiga = _intencao(ID_A, IDADE_MIN + 60)
    _escrever(log, [antiga])

    resumo = _reconciliar(log)

    assert resumo == {"reconciliadas": [ID_A], "recentes": [], "timestamp_invalido": [], "linhas_invalidas": 0}
    intencao, resultado = _ler_jsonl(log)
    assert intencao == antiga, "a INTENCAO original não é alterada"
    assert resultado["fase"] == "RESULTADO" and resultado["decisao"] == "APROVADO"
    assert resultado["resultado_banco"] == "NAO_CONCLUIDA" and resultado["motivo"] == "RECONCILIADO_NA_SUBIDA"
    for campo in ("id_intervencao", "aprovador", "hash_payload", "parametros", "alvo"):
        assert resultado[campo] == antiga[campo]
    assert datetime.fromisoformat(resultado["timestamp"]).tzinfo is not None
    assert not log.read_bytes().count(b"\r\n")


@pytest.mark.parametrize("idade, reconcilia", [(IDADE_MIN - 1, False), (IDADE_MIN - 0.001, False), (IDADE_MIN, True)])
def test_reconciliador_fronteira_de_idade(tmp_path, idade, reconcilia):
    log = tmp_path / "kill.log"
    _escrever(log, [_intencao(ID_A, idade)])
    antes = log.read_bytes()

    resumo = _reconciliar(log)

    if reconcilia:
        assert resumo["reconciliadas"] == [ID_A] and resumo["recentes"] == []
    else:
        assert resumo["reconciliadas"] == [] and resumo["recentes"] == [ID_A]
        assert log.read_bytes() == antes, "INTENCAO recente não é tocada"


def test_reconciliador_par_completo_nao_e_tocado(tmp_path):
    log = tmp_path / "kill.log"
    _escrever(log, [_intencao(ID_A, 5000), _resultado(ID_A, "ENCERRADA", 4990)])
    antes = log.read_bytes()
    resumo = _reconciliar(log)
    assert resumo == {"reconciliadas": [], "recentes": [], "timestamp_invalido": [], "linhas_invalidas": 0}
    assert log.read_bytes() == antes


def test_reconciliador_idempotente_e_resultado_real_posterior(tmp_path):
    log = tmp_path / "kill.log"
    _escrever(log, [_intencao(ID_A, 5000), _intencao(ID_B, 5000)])

    assert sorted(_reconciliar(log)["reconciliadas"]) == [ID_A, ID_B]
    depois_1 = log.read_bytes()
    segundo = _reconciliar(log)
    assert segundo["reconciliadas"] == [] and log.read_bytes() == depois_1

    # Uma RESULTADO real que chegue depois é anexada normalmente (o log é append-only) e prevalece para o auditor
    registrar_log_aprovacao_kill(
        "dba_teste", "APROVADO", "h", {"inst_id": 1, "sid": 101, "serial": 202}, resultado_banco="ENCERRADA",
        caminho_log=log, fase="RESULTADO", id_intervencao=ID_A,
    )
    resultados_a = [r["resultado_banco"] for r in _ler_jsonl(log) if r["fase"] == "RESULTADO"
                    and r["id_intervencao"] == ID_A]
    assert resultados_a == ["NAO_CONCLUIDA", "ENCERRADA"], "a posterior vem depois e é a última"
    depois_2 = log.read_bytes()
    assert _reconciliar(log)["reconciliadas"] == [] and log.read_bytes() == depois_2


def test_reconciliador_linhas_invalidas_e_parcial(tmp_path):
    log = tmp_path / "kill.log"
    legado = {"timestamp": AGORA.isoformat(), "aprovador": "x", "decisao": "APROVADO", "resultado_banco": "ENCERRADA"}
    conteudo = (
        b"isto nao e json\n"
        + (json.dumps(legado) + "\n").encode()
        + (json.dumps(_intencao(ID_A, 5000)) + "\n").encode()
        + (json.dumps({"fase": "INTENCAO", "id_intervencao": "curto"}) + "\n").encode()
        + b'{"fase": "INTEN'  # parcial, sem LF final
    )
    log.write_bytes(conteudo)

    resumo = _reconciliar(log)

    assert resumo["reconciliadas"] == [ID_A]
    assert resumo["linhas_invalidas"] == 3  # lixo, id fora do formato e a linha parcial
    bruto = log.read_bytes()
    assert bruto.startswith(conteudo), "nada é reescrito"
    linhas = bruto.split(b"\n")
    assert linhas[-3] == b'{"fase": "INTEN', "a parcial fica isolada em linha própria"
    ultima = json.loads(linhas[-2])
    assert ultima["fase"] == "RESULTADO" and ultima["id_intervencao"] == ID_A


def test_reconciliador_arquivo_inexistente_nao_cria_nada(tmp_path):
    pasta = tmp_path / "vazia"
    pasta.mkdir()
    resumo = _reconciliar(pasta / "kill.log")
    assert resumo == {"reconciliadas": [], "recentes": [], "timestamp_invalido": [], "linhas_invalidas": 0}
    assert list(pasta.iterdir()) == []
    assert not (tmp_path / "naoexiste").exists()
    assert _reconciliar(tmp_path / "naoexiste" / "kill.log")["reconciliadas"] == []
    assert not (tmp_path / "naoexiste").exists()


def test_reconciliador_timestamp_invalido_nao_e_tocado(tmp_path):
    log = tmp_path / "kill.log"
    _escrever(log, [
        _intencao(ID_A, 0, timestamp="lixo"),
        _intencao(ID_B, 0, timestamp="2020-01-01T00:00:00"),  # sem fuso
        _intencao(ID_C, 0, timestamp=""),
    ])
    antes = log.read_bytes()
    resumo = _reconciliar(log)
    assert resumo["reconciliadas"] == [] and resumo["recentes"] == []
    assert sorted(resumo["timestamp_invalido"]) == [ID_A, ID_B, ID_C]
    assert log.read_bytes() == antes


def test_reconciliador_lock_indisponivel(monkeypatch, tmp_path):
    log = tmp_path / "kill.log"
    _escrever(log, [_intencao(ID_A, 5000)])
    antes = log.read_bytes()

    def _negado(fd):
        raise OSError(errno.EACCES, "lock negado (injetado)")

    monkeypatch.setattr(oracle_dba, "_travar_arquivo", _negado)
    monkeypatch.setattr(oracle_dba, "LOCK_LOG_TIMEOUT_SEGUNDOS", 0.2)
    with pytest.raises(LockLogAprovacaoIndisponivel):
        _reconciliar(log)
    assert log.read_bytes() == antes
    assert issubclass(LockLogAprovacaoIndisponivel, TimeoutError)


# =============================================================================
# Lock entre processos e gravação concorrente
# =============================================================================

_CODIGO_FILHO_LOCK = r"""
import os, sys, time
caminho = sys.argv[1]
fd = os.open(caminho, os.O_RDWR | os.O_CREAT, 0o600)
if os.name == "nt":
    import msvcrt
    os.lseek(fd, 0, os.SEEK_SET)
    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
else:
    import fcntl
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
print("LOCKED", flush=True)
sys.stdin.readline()
"""


_PREFIXOS_ENV_SENSIVEIS = ("ORACLE_", "EMAIL_", "GEMINI_")


def _env_sem_segredos(remover=()):
    """Cópia de os.environ sem ORACLE_*, EMAIL_*, GEMINI_* (O2 do item 1) e sem as chaves em `remover`."""
    return {
        k: v for k, v in os.environ.items()
        if not k.startswith(_PREFIXOS_ENV_SENSIVEIS) and k not in remover
    }


def _filho_com_lock(caminho_lock):
    proc = subprocess.Popen(
        [sys.executable, "-I", "-c", _CODIGO_FILHO_LOCK, str(caminho_lock)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        env=_env_sem_segredos(),
    )
    linha = proc.stdout.readline()
    assert linha.strip() == "LOCKED", f"filho não obteve o lock: {proc.stderr.read() if proc.poll() else linha!r}"
    return proc


def _encerrar(proc):
    try:
        if proc.poll() is None:
            try:
                proc.stdin.write("fim\n")
                proc.stdin.flush()
            except OSError:
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)
    finally:
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            try:
                pipe.close()
            except Exception:
                pass


def test_lock_de_arquivo_entre_processos(monkeypatch, tmp_path):
    log = tmp_path / "kill.log"
    lock = tmp_path / "kill.log.lock"
    monkeypatch.setattr(oracle_dba, "LOCK_LOG_TIMEOUT_SEGUNDOS", 0.3)
    proc = _filho_com_lock(lock)
    try:
        inicio = time.monotonic()
        with pytest.raises(LockLogAprovacaoIndisponivel):
            with oracle_dba._lock_arquivo_log(log):
                pytest.fail("o lock não podia ser obtido enquanto o outro processo o detém")
        assert time.monotonic() - inicio >= 0.25, "deve tentar de novo até esgotar o prazo"

        # Uma gravação (INTENCAO) com o lock ocupado falha e não deixa linha no arquivo
        with pytest.raises(LockLogAprovacaoIndisponivel):
            registrar_log_aprovacao_kill(
                "dba_teste", "APROVADO", "h", {}, caminho_log=log, fase="INTENCAO", id_intervencao=ID_A,
            )
        assert not log.exists() or log.read_bytes() == b""
    finally:
        _encerrar(proc)

    # Liberado o lock, a gravação volta a funcionar
    registrar_log_aprovacao_kill(
        "dba_teste", "APROVADO", "h", {}, caminho_log=log, fase="INTENCAO", id_intervencao=ID_A,
    )
    assert _fases_no_log(log) == ["INTENCAO"]


def test_lock_liberado_durante_a_espera_permite_gravar(monkeypatch, tmp_path):
    """Novas tentativas: o outro processo solta o lock dentro do prazo e a gravação conclui."""
    log = tmp_path / "kill.log"
    monkeypatch.setattr(oracle_dba, "LOCK_LOG_TIMEOUT_SEGUNDOS", 15.0)
    proc = _filho_com_lock(tmp_path / "kill.log.lock")
    try:
        threading.Timer(0.5, lambda: (proc.stdin.write("fim\n"), proc.stdin.flush())).start()
        registrar_log_aprovacao_kill(
            "dba_teste", "APROVADO", "h", {}, caminho_log=log, fase="INTENCAO", id_intervencao=ID_B,
        )
    finally:
        _encerrar(proc)
    assert _fases_no_log(log) == ["INTENCAO"]


def test_gravacao_concorrente_threads(tmp_path):
    log = tmp_path / "kill.log"
    erros = []

    def trabalhador(indice):
        try:
            for n in range(15):
                registrar_log_aprovacao_kill(
                    f"dba_{indice}", "REJEITADO", "h", {"n": n}, motivo="T", caminho_log=log,
                    fase="RESULTADO", id_intervencao=f"{indice:016x}{n:016x}",
                )
        except Exception as exc:  # pragma: no cover
            erros.append(exc)

    threads = [threading.Thread(target=trabalhador, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert erros == []
    linhas = log.read_bytes().split(b"\n")
    assert linhas[-1] == b""
    validas = [json.loads(l) for l in linhas[:-1]]
    assert len(validas) == 6 * 15
    assert len({r["id_intervencao"] for r in validas}) == 6 * 15


# =============================================================================
# Pasta do log: criação só na gravação, padrão fora do OneDrive, .env.example
# =============================================================================

def test_gravacao_cria_a_pasta_do_log(tmp_path):
    log = tmp_path / "a" / "b" / "kill.log"
    assert not log.parent.exists()
    registrar_log_aprovacao_kill(
        "dba_teste", "REJEITADO", "h", {}, motivo="T", caminho_log=log, fase="RESULTADO", id_intervencao=ID_A,
    )
    assert log.is_file() and _fases_no_log(log) == ["RESULTADO"]


_CODIGO_FILHO_IMPORT = r"""
import os, sys, types
raiz, esperado_dir = sys.argv[1], sys.argv[2]
falso = types.ModuleType("dotenv")
falso.load_dotenv = lambda *a, **k: False
sys.modules["dotenv"] = falso
sys.path.insert(0, raiz)
antes = os.path.exists(esperado_dir)
from src.tools import oracle_dba as od
assert os.path.exists(esperado_dir) == antes, "o import não pode criar nem remover a pasta"
print(str(od.DIRETORIO_LOG_APROVACAO))
print(str(od.CAMINHO_LOG_APROVACAO_PADRAO))
print(od.DIRETORIO_LOG_PADRAO)
"""


def _importar_em_subprocesso(tmp_path, env_extra, pasta_a_vigiar):
    env = _env_sem_segredos(remover=("AGENTDBA_LOG_DIR",))
    env.update(env_extra)
    res = subprocess.run(
        [sys.executable, "-I", "-c", _CODIGO_FILHO_IMPORT, str(RAIZ), str(pasta_a_vigiar)],
        capture_output=True, text=True, env=env, timeout=120, cwd=str(tmp_path),
    )
    assert res.returncode == 0, res.stderr
    return res.stdout.splitlines()


def test_env_de_subprocesso_sem_segredos(monkeypatch):
    for nome in ("ORACLE_USER_KILL", "EMAIL_SENHA_APP", "GEMINI_API_KEY", "ORACLE_SANDBOX"):
        monkeypatch.setenv(nome, "x")
    monkeypatch.setenv("OUTRA_VAR", "ok")
    env = _env_sem_segredos()
    assert not [k for k in env if k.startswith(_PREFIXOS_ENV_SENSIVEIS)]
    assert env["OUTRA_VAR"] == "ok"
    assert "OUTRA_VAR" not in _env_sem_segredos(remover=("OUTRA_VAR",))


def test_import_nao_cria_a_pasta_do_log(tmp_path):
    alvo = tmp_path / "nao_criar"
    saida = _importar_em_subprocesso(tmp_path, {"AGENTDBA_LOG_DIR": str(alvo)}, alvo)
    assert Path(saida[0]) == alvo and Path(saida[1]) == alvo / "kill_approval.log"
    assert not alvo.exists()
    assert list(tmp_path.iterdir()) == []


def test_import_com_padrao_nao_cria_C_AgentDBA(tmp_path):
    padrao = Path(r"C:\AgentDBA\logs")
    saida = _importar_em_subprocesso(tmp_path, {}, padrao)
    assert saida[0] == saida[2] == r"C:\AgentDBA\logs"
    assert Path(saida[1]) == padrao / "kill_approval.log"


def test_conftest_define_diretorio_antes_do_import():
    """AGENTDBA_LOG_DIR (tmp, fora do OneDrive) já valia quando o módulo de produção foi importado."""
    destino = Path(os.environ["AGENTDBA_LOG_DIR"])
    assert oracle_dba.DIRETORIO_LOG_APROVACAO == destino
    assert destino.name.startswith("agentdba_test_")
    assert "onedrive" not in str(destino).lower()


def test_padrao_fora_do_onedrive():
    assert oracle_dba.DIRETORIO_LOG_PADRAO == r"C:\AgentDBA\logs"
    assert "onedrive" not in oracle_dba.DIRETORIO_LOG_PADRAO.lower()
    assert oracle_dba.LOCK_LOG_TIMEOUT_SEGUNDOS == 5.0


def test_env_example_log_dir_sem_onedrive():
    linhas = (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines()
    assert (
        "# Diretório do log de aprovações de kill (fora de pasta sincronizada). Padrão: C:\\AgentDBA\\logs" in linhas
    )
    assert "AGENTDBA_LOG_DIR=C:\\AgentDBA\\logs" in linhas
    assert "onedrive" not in "\n".join(linhas).lower()
