"""
Smoke test do fluxo HITL na CLI (src/main.py), sem conexão: LLM, Oracle, rede e SMTP são falsos.

Neutralizações (fixture de módulo): load_dotenv no-op, credenciais fictícias, handler nulo na raiz
(basicConfig vira no-op, sem FileHandler para auditoria_oracle.log) e socket.create_connection
bloqueado (127.0.0.1:11434 -> OSError; qualquer outro destino -> falha do teste).
Os patches de Oracle miram `tools.oracle_dba` (objeto usado por main.py), não `src.tools.oracle_dba`.
"""
import json
import logging
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests._guarda_env import instalar as _instalar_guarda_env
from tests.fakes_oracle import (
    USER_DIAG_FAKE,
    USER_KILL_FAKE,
    _OracleFake,
    _eh_consulta_alvo,
    _linha_alvo,
)

RAIZ = Path(__file__).resolve().parent.parent
LOGS_REAIS = (RAIZ / "auditoria_oracle.log", RAIZ / "data" / "logs" / "auditoria_oracle.log")
ARGS_KILL = {"inst_id": 1, "sid": 101, "serial": 202}


class _LLMFalso:
    """Substitui main.client: 1ª chamada pede matar_sessao_oracle (ou `nome`); 2ª devolve texto final.

    Expectativa alterada, declarada (R1 ampliada, r1_ampliada/decisao_c1.md §8.5): o falso ganha base_url, local
    por padrão, porque com o coordenador em nuvem as ferramentas Oracle (e o kill) são recusadas (decisão 5.2.1)."""

    # Fase 2, K5 (expectativa alterada, declarada; decisao_c1.md §8.4): o cliente local é 127.0.0.1, não localhost.
    def __init__(self, base_url="http://127.0.0.1:11434/v1", nome="matar_sessao_oracle", argumentos=None):
        self.base_url = base_url
        self.nome, self.argumentos = nome, (ARGS_KILL if argumentos is None else argumentos)
        self.chamadas = []  # cópia da lista de mensagens recebida em cada chamada
        self.tools = []  # catálogo recebido em cada chamada
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model=None, messages=None, tools=None, **kwargs):
        self.chamadas.append(list(messages))
        self.tools.append(tools)
        if len(self.chamadas) == 1:
            tool_call = SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(name=self.nome, arguments=json.dumps(self.argumentos)),
            )
            msg = SimpleNamespace(content=None, tool_calls=[tool_call])
        else:
            msg = SimpleNamespace(content="Resposta final do agente falso.", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    def resultado_tool(self):
        """JSON devolvido ao LLM (mensagem role=tool vista na 2ª chamada)."""
        assert len(self.chamadas) == 2, "o LLM falso deveria ter sido chamado exatamente 2 vezes"
        tools = [m for m in self.chamadas[1] if isinstance(m, dict) and m.get("role") == "tool"]
        assert len(tools) == 1
        return json.loads(tools[0]["content"])


def _snapshot(caminho):
    try:
        st = caminho.stat()
    except FileNotFoundError:
        return (False, None, None)
    return (True, st.st_size, st.st_mtime_ns)


def _filehandlers_auditoria():
    """FileHandlers cujo arquivo é um dos logs reais de auditoria (raiz, tools.oracle_dba e main)."""
    alvos = {str(p.resolve()).lower() for p in LOGS_REAIS}
    encontrados = []
    for nome in ("", "tools.oracle_dba", "src.tools.oracle_dba", "main"):
        for h in logging.getLogger(nome).handlers:
            if isinstance(h, logging.FileHandler) and str(Path(h.baseFilename).resolve()).lower() in alvos:
                encontrados.append(h)
    return encontrados


def _instalar_guarda_dotenv(mp, ficticio):
    """load_dotenv e dotenv_values viram stubs que registram a chamada; o guarda de tests/_guarda_env.py
    recusa (LeituraEnvRealBloqueada) e registra qualquer leitura de RAIZ/.env e redireciona open/io.open/os.stat
    do .env real para `ficticio` (arquivo vazio de teste).

    Devolve o registro; o teste afirma `leituras_env_reais == []` (nenhum leitor chega ao .env real) e
    `cargas` conta as chamadas a load_dotenv (a carga em si). As chamadas a dotenv_values ficam em `valores`."""
    import dotenv

    registro = _instalar_guarda_env(mp.setattr, RAIZ / ".env", ficticio)

    def _load_dotenv(*a, **k):
        registro.cargas.append({"funcao": "load_dotenv"})
        return False

    def _dotenv_values(*a, **k):
        registro.valores.append({"funcao": "dotenv_values"})
        return {}

    mp.setattr(dotenv, "load_dotenv", _load_dotenv)
    mp.setattr(dotenv, "dotenv_values", _dotenv_values)
    return registro


_AUSENTE = object()
_ATRIBUTO_ESTADO_ENV = "_personal_agent_estado_env"


@pytest.fixture(scope="module")
def main_cli(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    ficticio = tmp_path_factory.mktemp("env_ficticio_cli") / "ficticio.env"
    ficticio.write_bytes(b"")
    registro = _instalar_guarda_dotenv(mp, ficticio)
    leituras_env_reais = registro.leituras_env_reais
    # Achado 2: o estado da carga do .env vive em sys; se já existir, o import de main não carregaria nada.
    # Salvo aqui e removido logo antes do import; restaurado EXATAMENTE no teardown (sem
    # monkeypatch.delattr: não registra restauração sobre atributo ausente, L1).
    estado_env_antes = vars(sys).get(_ATRIBUTO_ESTADO_ENV, _AUSENTE)
    for caminho in (str(RAIZ / "src"), str(RAIZ)):
        mp.syspath_prepend(caminho)
    mp.setenv("ORACLE_USER_DIAG", USER_DIAG_FAKE)
    mp.setenv("ORACLE_PASSWORD_DIAG", "senha_diag_ficticia")
    mp.setenv("ORACLE_USER_KILL", USER_KILL_FAKE)
    mp.setenv("ORACLE_PASSWORD_KILL", "senha_kill_ficticia")
    mp.setenv("ORACLE_DSN", "host-ficticio.invalid:1521/FAKE")
    mp.delenv("ORACLE_SANDBOX", raising=False)
    # Fase 2 da R1 (decisao_c1.md §2.3; expectativa alterada, declarada): o kill exige OPS_KILL_PKG_VERSAO=2.
    mp.setenv("OPS_KILL_PKG_VERSAO", "2")

    import socket

    def _create_connection(endereco, *args, **kwargs):
        if tuple(endereco) == ("127.0.0.1", 11434):
            raise OSError("Ollama indisponível (neutralizado no teste)")
        pytest.fail(f"Tentativa de conexão de rede não permitida: {endereco!r}")

    mp.setattr(socket, "create_connection", _create_connection)

    nulo = logging.NullHandler()
    logging.getLogger().addHandler(nulo)
    ja_importado = "main" in sys.modules
    vars(sys).pop(_ATRIBUTO_ESTADO_ENV, None)
    try:
        import main
        main.client = _LLMFalso()
        assert not _filehandlers_auditoria(), "import de main não pode adicionar FileHandler de auditoria"
        assert leituras_env_reais == []
        assert len(registro.cargas) == 1, "a carga do .env deveria ter rodado exatamente 1 vez no import de main"
        yield main
        assert leituras_env_reais == []
    finally:
        logging.getLogger().removeHandler(nulo)
        if not ja_importado:
            sys.modules.pop("main", None)
        mp.undo()
        if estado_env_antes is _AUSENTE:
            vars(sys).pop(_ATRIBUTO_ESTADO_ENV, None)
        else:
            vars(sys)[_ATRIBUTO_ESTADO_ENV] = estado_env_antes
        assert leituras_env_reais == []


@pytest.fixture
def cenario(main_cli, monkeypatch, isolar_log_aprovacao, caplog, capsys):
    """Prepara um fluxo: devolve executar(linhas_diag, status_pkg, entradas, kill_permitido)."""
    import tools.oracle_dba as od

    # O log de aprovação padrão deve apontar para tmp_path (autouse do conftest ou redirecionamento local)
    if od.CAMINHO_LOG_APROVACAO_PADRAO != isolar_log_aprovacao:
        monkeypatch.setattr(od, "CAMINHO_LOG_APROVACAO_PADRAO", isolar_log_aprovacao)
    assert od.CAMINHO_LOG_APROVACAO_PADRAO == isolar_log_aprovacao

    emails = []

    def _email(assunto, corpo):
        emails.append((assunto, corpo))
        return True, "capturado (fake)"

    monkeypatch.setattr(
        od, "verificar_acessibilidade_host",
        lambda dsn, timeout=3.0: {"acessivel": True, "host": "fake", "porta": 1521, "erro_rede": None},
    )
    monkeypatch.setattr(od, "enviar_alerta_email", _email)
    caplog.set_level(logging.INFO)

    def executar(linhas_diag, status_pkg, entradas, kill_permitido=True, erro_kill=None):
        oracle = _OracleFake(linhas_diag, status_pkg=status_pkg, kill_permitido=kill_permitido, erro_kill=erro_kill)
        monkeypatch.setattr(od.oracledb, "connect", oracle.connect)
        iterador = iter(entradas)
        monkeypatch.setattr("builtins.input", lambda *a, **k: next(iterador))
        llm = _LLMFalso()
        monkeypatch.setattr(main_cli, "client", llm)
        main_cli.executar_agente("mate a sessão 101,202 da instância 1")
        assert next(iterador, None) is None, "sobraram entradas não consumidas em input()"
        linhas = []
        if isolar_log_aprovacao.exists():
            linhas = [json.loads(l) for l in isolar_log_aprovacao.read_text(encoding="utf-8").splitlines() if l.strip()]
        consultas_diag = sum(1 for conta, sql, _ in oracle.sql_executado if conta == "DIAG" and _eh_consulta_alvo(sql))
        return SimpleNamespace(
            oracle=oracle, llm=llm, emails=emails, linhas=linhas, consultas_diag=consultas_diag,
            tela=capsys.readouterr().out, log=caplog.text, json_tool=llm.resultado_tool(),
        )

    return executar


def _um_registro(r):
    assert len(r.linhas) == 1
    return r.linhas[0]


def _par_intencao_resultado(r):
    """APROVADO grava 2 linhas (decisão 1): [0] INTENCAO (resultado_banco None) e [1] RESULTADO, mesmo id."""
    assert len(r.linhas) == 2
    intencao, resultado = r.linhas
    assert intencao["fase"] == "INTENCAO" and intencao["decisao"] == "APROVADO"
    assert intencao["resultado_banco"] is None
    assert resultado["fase"] == "RESULTADO"
    assert intencao["id_intervencao"] == resultado["id_intervencao"]
    assert re.fullmatch(r"[0-9a-f]{32}", resultado["id_intervencao"])
    return resultado


def _sem_filehandler_real():
    assert not _filehandlers_auditoria()


def test_cli_aprovado_encerrada(cenario):
    r = cenario([_linha_alvo(), _linha_alvo()], "ENCERRADA", ["dba", "S"])
    assert r.consultas_diag == 2
    assert len(r.oracle.conexoes_kill) == 1
    assert len(r.emails) == 1 and "Intervenção Aprovada" in r.emails[0][0]
    reg = _par_intencao_resultado(r)
    assert reg["decisao"] == "APROVADO" and reg["resultado_banco"] == "ENCERRADA"
    assert reg["aprovador"] == "dba"
    assert "EXECUTADA COM SUCESSO" in r.tela
    assert "AUDITORIA HITL: APROVADO" in r.log
    assert r.json_tool["decisao"] == "APROVADO" and r.json_tool["executado"] is True
    assert r.json_tool["resultado_banco"] == "ENCERRADA"
    _sem_filehandler_real()


def test_cli_aprovado_nao_usuario(cenario):
    r = cenario([_linha_alvo(), _linha_alvo()], "NAO_USUARIO", ["dba", "S"])
    assert r.consultas_diag == 2
    assert len(r.oracle.conexoes_kill) == 1
    assert len(r.emails) == 1 and "NÃO executada" in r.emails[0][0]
    reg = _par_intencao_resultado(r)
    assert reg["decisao"] == "APROVADO" and reg["resultado_banco"] == "NAO_USUARIO"
    assert "mas NÃO EXECUTADA" in r.tela
    assert r.json_tool["decisao"] == "APROVADO" and r.json_tool["executado"] is False
    assert r.json_tool["resultado_banco"] == "NAO_USUARIO"
    _sem_filehandler_real()


def test_cli_rejeitado(cenario):
    r = cenario([_linha_alvo()], None, ["dba", "N"], kill_permitido=False)
    assert r.consultas_diag == 1
    assert len(r.oracle.conexoes_kill) == 0
    assert r.emails == []
    reg = _um_registro(r)
    assert reg["decisao"] == "REJEITADO" and reg["resultado_banco"] is None
    assert reg["motivo"] == "REJEITADO_PELO_APROVADOR"
    assert "NÃO aprovada" in r.tela
    assert r.json_tool["decisao"] == "REJEITADO" and r.json_tool["executado"] is False
    _sem_filehandler_real()


def test_cli_aprovador_vazio(cenario):
    r = cenario([_linha_alvo()], None, [""], kill_permitido=False)
    assert r.consultas_diag == 1
    assert len(r.oracle.conexoes_kill) == 0
    assert r.emails == []
    reg = _um_registro(r)
    assert reg["decisao"] == "REJEITADO" and reg["resultado_banco"] is None
    assert reg["motivo"] == "SEM_IDENTIFICACAO"
    assert "Identificação do aprovador é obrigatória" in r.tela
    assert r.json_tool["decisao"] == "REJEITADO" and r.json_tool["executado"] is False
    assert r.json_tool["motivo"] == "SEM_IDENTIFICACAO"
    _sem_filehandler_real()


def test_cli_alvo_alterado(cenario):
    r = cenario([_linha_alvo(), _linha_alvo(program="outro.exe")], None, ["dba", "S"], kill_permitido=False)
    assert r.consultas_diag == 2
    assert len(r.oracle.conexoes_kill) == 0
    assert len(r.emails) == 1 and "NÃO executada" in r.emails[0][0]
    reg = _par_intencao_resultado(r)
    assert reg["decisao"] == "APROVADO" and reg["resultado_banco"] == "ALVO_ALTERADO"
    assert "mas NÃO EXECUTADA" in r.tela
    assert "ALVO_ALTERADO" in r.log
    assert r.json_tool["decisao"] == "APROVADO" and r.json_tool["executado"] is False
    assert r.json_tool["resultado_banco"] == "ALVO_ALTERADO"
    _sem_filehandler_real()


def test_cli_nao_grava_auditoria_real(cenario):
    antes = [_snapshot(p) for p in LOGS_REAIS]
    r = cenario([_linha_alvo(), _linha_alvo()], "ENCERRADA", ["dba", "S"])
    assert r.json_tool["executado"] is True
    depois = [_snapshot(p) for p in LOGS_REAIS]
    assert antes == depois, "auditoria_oracle.log real foi alterado pelo fluxo CLI"
    _sem_filehandler_real()


# ---------------------------------------------------------------------------
# Item 1 (1d, T13, T14, reconciliador): mensagens da CLI
# ---------------------------------------------------------------------------

def test_cli_falha_log_aprovacao(cenario, monkeypatch):
    """T13: falha do log na INTENCAO -> NÃO EXECUTADA, 0 KILL, 1 só DIAG, 0 e-mail."""
    def _fsync_falha(fd):
        raise OSError(5, "fsync falhou (injetado)")

    monkeypatch.setattr(os, "fsync", _fsync_falha)
    r = cenario([_linha_alvo()], None, ["dba", "S"], kill_permitido=False)

    assert r.consultas_diag == 1, "sem reconsulta DIAG depois da decisão"
    assert len(r.oracle.conexoes_kill) == 0
    assert r.emails == []
    assert "NÃO EXECUTADA" in r.tela
    assert "nenhuma chamada à conta kill" in r.tela.lower()
    assert "FALHA_LOG_APROVACAO" in r.tela
    assert r.json_tool["motivo"] == "FALHA_LOG_APROVACAO" and r.json_tool["executado"] is False
    assert "FALHA_LOG_APROVACAO" in r.log
    _sem_filehandler_real()


def test_cli_excecao_rota_kill(cenario, monkeypatch):
    """T14 (CLI, plano 9.3): exceção no fluxo de kill não é silenciosa e o estado é declarado desconhecido."""
    import tools.oracle_dba as od

    def _explode(*a, **k):
        raise RuntimeError("detalhe-interno-xyz")

    monkeypatch.setattr(od, "registrar_decisao_kill", _explode)
    r = cenario([_linha_alvo()], None, ["dba", "S"], kill_permitido=False)

    assert "[Sistema]: ERRO interno no fluxo de kill; estado desconhecido" in r.tela
    assert r.json_tool["executado"] is None
    assert "estado desconhecido" in r.json_tool["mensagem"]
    assert "detalhe-interno-xyz" not in json.dumps(r.json_tool)
    assert len(r.oracle.conexoes_kill) == 0
    _sem_filehandler_real()


def test_cli_resultado_desconhecido(cenario):
    """ERRO_ORACLE a partir do execute do KILL_SESSION: tela, e-mail e resultado_tool dizem 'resultado desconhecido'."""
    import oracledb
    import tools.oracle_dba as od

    r = cenario(
        [_linha_alvo(), _linha_alvo()], None, ["dba", "S"], erro_kill=oracledb.DatabaseError("PLS-00306: x")
    )

    assert "resultado desconhecido: conferir sessão" in r.tela
    assert "resultado desconhecido: conferir sessão" in r.emails[0][0]
    assert "NÃO executada" not in r.emails[0][0]
    assert r.json_tool["resultado_desconhecido"] is True
    assert "resultado desconhecido: conferir sessão" in r.json_tool["mensagem"]
    assert r.json_tool["executado"] is False
    assert od.MENSAGEM_RESULTADO_DESCONHECIDO == "resultado desconhecido: conferir sessão"


def test_cli_status_pkg_vazio_e_resultado_desconhecido(cenario):
    """K2 (A1, m29): p_status vazio (fora da lista fechada): a tela diz 'resultado desconhecido' com o texto comum
    'desfecho no banco não confirmado' e não 'NÃO EXECUTADA' nem 'erro a partir da chamada ao PKG'."""
    import tools.oracle_dba as od

    r = cenario([_linha_alvo(), _linha_alvo()], "", ["dba", "S"])

    assert len(r.oracle.conexoes_kill) == 1
    assert od.MENSAGEM_RESULTADO_DESCONHECIDO in r.tela
    assert od.MENSAGEM_DESFECHO_NAO_CONFIRMADO in r.tela
    assert "NÃO EXECUTADA" not in r.tela and "NÃO executada" not in r.tela
    assert "erro a partir da chamada ao PKG" not in r.tela
    assert od.MENSAGEM_RESULTADO_DESCONHECIDO in r.emails[0][0]
    assert "NÃO executada" not in r.emails[0][0]
    assert od.MENSAGEM_DESFECHO_NAO_CONFIRMADO in r.emails[0][1]
    assert "erro do Oracle" not in r.emails[0][1]
    assert r.json_tool["resultado_desconhecido"] is True and r.json_tool["executado"] is False


def test_cli_reconciliador_na_subida(main_cli, isolar_log_aprovacao, capsys):
    """Reconciliador da CLI: INTENCAO antiga ganha RESULTADO NAO_CONCLUIDA e é avisada; nunca levanta."""
    from datetime import datetime, timedelta, timezone

    antiga = {
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), "fase": "INTENCAO",
        "id_intervencao": "d" * 32, "aprovador": "dba", "decisao": "APROVADO", "resultado_banco": None,
        "motivo": None, "hash_payload": "h", "parametros": {"inst_id": 1, "sid": 1, "serial": 1}, "alvo": {},
    }
    isolar_log_aprovacao.write_text(json.dumps(antiga) + "\n", encoding="utf-8")

    main_cli._reconciliar_na_subida_cli()

    tela = capsys.readouterr().out
    assert "d" * 32 in tela and "OPS_KILL_AUDIT" in tela
    linhas = [json.loads(l) for l in isolar_log_aprovacao.read_text(encoding="utf-8").splitlines()]
    assert [l["fase"] for l in linhas] == ["INTENCAO", "RESULTADO"]
    assert linhas[1]["resultado_banco"] == "NAO_CONCLUIDA" and linhas[1]["motivo"] == "RECONCILIADO_NA_SUBIDA"

    main_cli._reconciliar_na_subida_cli()  # idempotente
    assert len(isolar_log_aprovacao.read_text(encoding="utf-8").splitlines()) == 2
    assert "d" * 32 not in capsys.readouterr().out


def test_cli_reconciliador_falha_nao_derruba(main_cli, monkeypatch, capsys):
    """Qualquer falha do reconciliador (lock, E/S) vira aviso na tela; a CLI sobe do mesmo jeito."""
    import tools.oracle_dba as od

    def _lock_indisponivel(*a, **k):
        raise od.LockLogAprovacaoIndisponivel("lock indisponível (injetado)")

    monkeypatch.setattr(main_cli, "reconciliar_intencoes_orfas", _lock_indisponivel)
    main_cli._reconciliar_na_subida_cli()  # não levanta
    assert "Reconciliação do log de aprovações NÃO executada" in capsys.readouterr().out


# =============================================================================
# R1 ampliada V8/V3 (r1_ampliada/decisao_c1.md §8.3): coordenador em nuvem na CLI (C1, C2) e erro (C3)
# =============================================================================

NOMES_ORACLE = {"coletar_sessoes_ativas", "coletar_top_sql", "coletar_plano_execucao", "matar_sessao_oracle"}
URL_GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/"


def _nomes(tools):
    return {f["function"]["name"] for f in (tools or [])}


def _tools_vistas(llm, indice=-1):
    return [m for m in llm.chamadas[indice] if isinstance(m, dict) and m.get("role") == "tool"]


def _rodar(main_cli, monkeypatch, llm):
    monkeypatch.setattr(main_cli, "client", llm)
    main_cli.executar_agente("pedido de teste")
    return llm


def test_cli_c1_catalogo_local_tem_oracle_e_nuvem_nao(main_cli, monkeypatch):
    """C1 (mata V8a, V9a): catálogo local com as ferramentas Oracle; da nuvem, sem nenhuma; nunca o
    analisar_log_complexo."""
    local = _rodar(main_cli, monkeypatch, _LLMFalso(nome="ferramenta_inexistente", argumentos={}))
    assert NOMES_ORACLE <= _nomes(local.tools[0]) and "analisar_log_complexo" not in _nomes(local.tools[0])

    nuvem = _rodar(main_cli, monkeypatch, _LLMFalso(base_url=URL_GEMINI, nome="ferramenta_inexistente", argumentos={}))
    nomes = _nomes(nuvem.tools[0])
    assert nomes and not (nomes & NOMES_ORACLE) and "analisar_log_complexo" not in nomes


@pytest.mark.parametrize("ferramenta", sorted(NOMES_ORACLE))
def test_cli_c2_nuvem_chamada_inventada_a_ferramenta_oracle_e_recusada(main_cli, monkeypatch, ferramenta):
    """C2 (mata V8b): com a nuvem, chamada a qualquer ferramenta Oracle devolve a recusa fixa, sem conexão."""
    import tools.oracle_dba as od

    conexoes = []
    monkeypatch.setattr(od.oracledb, "connect", lambda *a, **k: conexoes.append(1))
    monkeypatch.setattr(od, "verificar_acessibilidade_host", lambda *a, **k: pytest.fail("sonda chamada"))
    monkeypatch.setattr("builtins.input", lambda *a, **k: pytest.fail("prompt HITL exibido"))
    llm = _rodar(main_cli, monkeypatch, _LLMFalso(base_url=URL_GEMINI, nome=ferramenta, argumentos=dict(ARGS_KILL)))

    assert conexoes == []
    (tool,) = _tools_vistas(llm)
    assert tool["content"] == od.RESULTADO_ORACLE_SO_LOCAL


def test_cli_c3_erro_execucao_so_com_o_tipo(main_cli, monkeypatch, caplog):
    """C3, CLI (mata V3 na interface): exceção numa ferramenta vira {"erro_execucao": <tipo>} ao LLM; o texto
    cru vai só ao log local."""
    def _quebra(*a, **k):
        raise RuntimeError("exc-sentinela")

    monkeypatch.setattr(main_cli, "coletar_top_sql", _quebra)
    caplog.set_level(logging.WARNING)
    llm = _rodar(main_cli, monkeypatch, _LLMFalso(nome="coletar_top_sql", argumentos={"limite": 3}))

    (tool,) = _tools_vistas(llm)
    assert json.loads(tool["content"]) == {"erro_execucao": "RuntimeError"}
    assert not any("exc-sentinela" in json.dumps(m, default=str) for msgs in llm.chamadas for m in msgs)
    assert "exc-sentinela" in caplog.text


def test_cli_historico_com_dado_do_banco_nao_vai_a_nuvem(main_cli, monkeypatch, capsys):
    """V8c na CLI: com a nuvem e uma mensagem de ferramenta Oracle já no histórico (simulada), a chamada não é feita.
    Hoje a CLI cria `messages` por chamada (decisao_c1.md §3.4); o teste fixa a checagem mesmo assim."""
    import tools.oracle_dba as od

    llm = _LLMFalso(base_url=URL_GEMINI, nome="coletar_sessoes_ativas", argumentos={})
    monkeypatch.setattr(main_cli, "client", llm)
    original = od.historico_tem_dado_do_banco
    monkeypatch.setattr(main_cli, "historico_tem_dado_do_banco", lambda msgs: True)
    main_cli.executar_agente("pedido de teste")

    assert llm.chamadas == [], "a nuvem recebeu o histórico com dado do banco"
    assert od.TEXTO_HISTORICO_COM_DADO_DO_BANCO in capsys.readouterr().out
    assert original([{"role": "tool", "name": "coletar_sessoes_ativas", "content": "{}"}]) is True


class _LLMSempreFerramenta(_LLMFalso):
    """Pede uma tool_call em toda chamada (o loop da CLI chega ao limite de 6 passos)."""

    def _create(self, model=None, messages=None, tools=None, **kwargs):
        self.chamadas.append(list(messages))
        self.tools.append(tools)
        tool_call = SimpleNamespace(
            id=f"call_{len(self.chamadas)}", function=SimpleNamespace(name=self.nome, arguments="{}"),
        )
        msg = SimpleNamespace(content=None, tool_calls=[tool_call])
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_cli_trava_do_laudo_final_depois_do_limite_de_passos(main_cli, monkeypatch, capsys):
    """V8c, laudo final da CLI (src/main.py, depois do loop; conferencia_c7.md §6.3): com a nuvem, se o histórico
    passa a ter dado do banco só na checagem do laudo final (7ª), a nuvem não recebe o laudo: 6 chamadas, não 7."""
    import tools.oracle_dba as od

    llm = _LLMSempreFerramenta(base_url=URL_GEMINI, nome="ferramenta_inexistente", argumentos={})
    monkeypatch.setattr(main_cli, "client", llm)
    checagens = []

    def _historico(mensagens):
        checagens.append(1)
        return len(checagens) > 6

    monkeypatch.setattr(main_cli, "historico_tem_dado_do_banco", _historico)
    main_cli.executar_agente("pedido de teste")

    assert len(checagens) == 7, "a checagem do laudo final não rodou"
    assert len(llm.chamadas) == 6, "a nuvem recebeu o laudo final com dado do banco"
    assert od.TEXTO_HISTORICO_COM_DADO_DO_BANCO in capsys.readouterr().out


# =============================================================================
# R1 ampliada fase 2, K1 (fase2/decisao_c1.md §2): gate de produção do kill na CLI (K1-T2 e K1-T4)
# =============================================================================

def test_cli_k1_t4_sem_gate_kill_fora_do_catalogo_e_despacho_recusa(main_cli, monkeypatch, isolar_log_aprovacao, capsys):
    """K1-T2 na interface e K1-T4 (mata M_K1_CAT_LOCAL na CLI e M_K1_DESP_CLI): coordenador local e sem
    OPS_KILL_PKG_VERSAO. O kill não está no catálogo; o LLM o chama mesmo assim e recebe a recusa fixa, sem
    conduzir_kill_hitl, sem prompt, sem conexão e sem JSONL."""
    import tools.oracle_dba as od

    monkeypatch.delenv("OPS_KILL_PKG_VERSAO")
    monkeypatch.setattr(main_cli, "conduzir_kill_hitl", lambda *a, **k: pytest.fail("conduzir_kill_hitl chamado"))
    monkeypatch.setattr("builtins.input", lambda *a, **k: pytest.fail("prompt HITL exibido"))
    monkeypatch.setattr(od.oracledb, "connect", lambda *a, **k: pytest.fail("conexão com o kill desabilitado"))
    llm = _rodar(main_cli, monkeypatch, _LLMFalso(nome="matar_sessao_oracle", argumentos=dict(ARGS_KILL)))

    nomes = _nomes(llm.tools[0])
    assert "matar_sessao_oracle" not in nomes and (NOMES_ORACLE - {"matar_sessao_oracle"}) <= nomes
    (tool,) = _tools_vistas(llm)
    assert tool["name"] == "matar_sessao_oracle" and tool["content"] == od.RESULTADO_KILL_DESABILITADO
    assert not isolar_log_aprovacao.exists()
    assert "indisponível nesta instalação (OPS_KILL_PKG_VERSAO)" in capsys.readouterr().out


def test_cli_k1_t6b_gate_retirado_durante_o_prompt(cenario, monkeypatch):
    """K1-T6b na CLI (além da lista do §2.4; mata M_K1_TELA_CLI): a variável é retirada entre o aprovador e a
    confirmação. Uma RESULTADO KILL_DESABILITADO sem INTENCAO, só a pré-consulta DIAG, sem conta KILL e sem
    e-mail; a tela diz que a intervenção aprovada NÃO foi executada."""
    def _entradas():
        yield "dba"
        monkeypatch.delenv("OPS_KILL_PKG_VERSAO")
        yield "S"

    r = cenario([_linha_alvo(), _linha_alvo()], "ENCERRADA", _entradas())
    reg = _um_registro(r)
    assert reg["fase"] == "RESULTADO" and reg["decisao"] == "APROVADO" and reg["aprovador"] == "dba"
    assert reg["resultado_banco"] == "KILL_DESABILITADO" and reg["resultado_desconhecido"] is False
    assert r.consultas_diag == 1 and r.oracle.conexoes_kill == [] and r.emails == []
    assert "NÃO EXECUTADA: encerramento desabilitado nesta instalação (OPS_KILL_PKG_VERSAO)" in r.tela
    assert r.json_tool["motivo"] == "KILL_DESABILITADO" and r.json_tool["executado"] is False
    assert "dba" not in json.dumps(r.json_tool, ensure_ascii=False)


# =============================================================================
# R1 ampliada fase 2, K2 (fase2/decisao_c1.md §1 e §8.2): lista de permissão na CLI (K2-T5)
# =============================================================================

LIBERADAS_K2 = {"coletar_metricas_hardware", "verificar_espaco_disco"}
NOVA_K2 = {"type": "function", "function": {"name": "ferramenta_nova", "parameters": {"type": "object"}}}


def test_cli_k2_t5_catalogo_da_nuvem_so_com_as_liberadas(main_cli, monkeypatch):
    """K2-T5 (mata M_K2_CAT_EXCLUSAO e M_K2_CLI_CAT_SOMA): com uma ferramenta nova no registro da CLI, o catálogo
    local a recebe (o teste não é cego) e o da nuvem é exatamente as 2 de SO."""
    monkeypatch.setattr(main_cli, "todas_ferramentas", main_cli.todas_ferramentas + [NOVA_K2])
    local = _rodar(main_cli, monkeypatch, _LLMFalso(nome="ferramenta_inexistente", argumentos={}))
    assert "ferramenta_nova" in _nomes(local.tools[0])

    nuvem = _rodar(main_cli, monkeypatch, _LLMFalso(base_url=URL_GEMINI, nome="ferramenta_inexistente", argumentos={}))
    assert _nomes(nuvem.tools[0]) == LIBERADAS_K2


@pytest.mark.parametrize(
    "ferramenta, argumentos", [("buscar_script_interno", {"tema_ou_problema": "x"}), ("ferramenta_nova", {})]
)
def test_cli_k2_t5_nuvem_recusa_rag_e_ferramenta_nova(main_cli, monkeypatch, ferramenta, argumentos):
    """K2-T5 (mata M_K2_DESP_CLI_ORACLE e M_K2_ROTA_ANTES): com a nuvem, o RAG e um nome sem classificação dão a
    recusa fixa; o RAG não é executado."""
    import tools.oracle_dba as od

    monkeypatch.setattr(main_cli, "buscar_script_interno", lambda *a, **k: pytest.fail("RAG executado com a nuvem"))
    llm = _rodar(main_cli, monkeypatch, _LLMFalso(base_url=URL_GEMINI, nome=ferramenta, argumentos=argumentos))

    (tool,) = _tools_vistas(llm)
    assert tool["content"] == od.RESULTADO_ORACLE_SO_LOCAL


def test_cli_k2_t5_nuvem_executa_a_liberada(main_cli, monkeypatch):
    """K2-T5, controle positivo: com a nuvem, coletar_metricas_hardware é executada e o resultado vai ao LLM."""
    monkeypatch.setattr(main_cli, "coletar_metricas_hardware", lambda *a, **k: '{"sentinela_hw": 1}')
    llm = _rodar(main_cli, monkeypatch, _LLMFalso(base_url=URL_GEMINI, nome="coletar_metricas_hardware", argumentos={}))

    (tool,) = _tools_vistas(llm)
    assert json.loads(tool["content"]) == {"sentinela_hw": 1}
