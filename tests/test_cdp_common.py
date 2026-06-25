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
