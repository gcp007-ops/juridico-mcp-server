import pytest

from juridico_mcp import cdp_common


def test_parse_host_port_extrai_host_e_porta():
    assert cdp_common._parse_host_port("http://127.0.0.1:9222") == ("127.0.0.1", 9222)
    assert cdp_common._parse_host_port("http://localhost:4444/") == ("localhost", 4444)


def test_cdp_url_or_raise_arg_explicito_vence(monkeypatch):
    monkeypatch.delenv("ANY_CDP_URL", raising=False)
    url = cdp_common.cdp_url_or_raise("http://127.0.0.1:9999", env_var="ANY_CDP_URL")
    assert url == "http://127.0.0.1:9999"


def test_cdp_url_or_raise_usa_env_quando_sem_arg(monkeypatch):
    monkeypatch.setenv("ANY_CDP_URL", "http://127.0.0.1:8888")
    assert cdp_common.cdp_url_or_raise(env_var="ANY_CDP_URL") == "http://127.0.0.1:8888"


def test_cdp_url_or_raise_usa_default_quando_sem_arg_e_sem_env(monkeypatch):
    monkeypatch.delenv("ANY_CDP_URL", raising=False)
    url = cdp_common.cdp_url_or_raise(
        env_var="ANY_CDP_URL", default="http://127.0.0.1:9222"
    )
    assert url == "http://127.0.0.1:9222"


def test_cdp_url_or_raise_sem_nada_levanta_com_nome_do_env(monkeypatch):
    monkeypatch.delenv("ANY_CDP_URL", raising=False)
    with pytest.raises(RuntimeError, match="ANY_CDP_URL"):
        cdp_common.cdp_url_or_raise(env_var="ANY_CDP_URL")


def test_cdp_session_init_guarda_host_e_porta():
    s = cdp_common.CdpSession("http://127.0.0.1:9222")
    assert (s._host, s._port) == ("127.0.0.1", 9222)
    assert s.cdp_url == "http://127.0.0.1:9222"


def test_cdp_session_expired_e_runtime_error():
    assert issubclass(cdp_common.CdpSessionExpired, RuntimeError)


def _session_com_ws(timeout=7.0):
    s = cdp_common.CdpSession("http://127.0.0.1:9222", timeout=timeout)
    s._ws = object()
    return s


def test_cmd_passa_recv_timeout(monkeypatch):
    # _cmd deve passar recv_timeout=self.timeout para nao bloquear indefinidamente.
    capt = {}

    def fake_call(ws, method, params, msg_id, recv_timeout=None):
        capt["recv_timeout"] = recv_timeout
        return {"result": {}}

    monkeypatch.setattr(cdp_common._cdp, "cdp_call", fake_call)
    _session_com_ws(timeout=7.0)._cmd("Page.enable")
    assert capt["recv_timeout"] == 7.0


def test_cmd_levanta_em_erro_de_protocolo(monkeypatch):
    monkeypatch.setattr(
        cdp_common._cdp, "cdp_call", lambda *a, **k: {"error": {"message": "boom"}}
    )
    with pytest.raises(cdp_common._cdp.CdpError):
        _session_com_ws()._cmd("Page.navigate", {"url": "x"})


def test_evaluate_sync_levanta_em_js_error(monkeypatch):
    # JS que lanca (subtype=="error") nao pode mais virar None silencioso.
    monkeypatch.setattr(
        cdp_common._cdp,
        "cdp_call",
        lambda *a, **k: {"result": {"result": {"subtype": "error", "description": "ReferenceError"}}},
    )
    with pytest.raises(cdp_common._cdp.CdpError):
        _session_com_ws().evaluate("foo.bar()")


def test_evaluate_sync_retorna_valor_normal(monkeypatch):
    monkeypatch.setattr(
        cdp_common._cdp,
        "cdp_call",
        lambda *a, **k: {"result": {"result": {"value": "complete"}}},
    )
    assert _session_com_ws().evaluate("document.readyState") == "complete"
