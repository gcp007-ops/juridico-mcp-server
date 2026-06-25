import pytest

from juridico_mcp.cdp_common import CdpSession
from juridico_mcp.jusbrasil import session as jb


def test_cdp_url_or_raise_default_9222(monkeypatch):
    monkeypatch.delenv("JUSBRASIL_CDP_URL", raising=False)
    assert jb.cdp_url_or_raise() == "http://127.0.0.1:9222"


def test_cdp_url_or_raise_env_override(monkeypatch):
    monkeypatch.setenv("JUSBRASIL_CDP_URL", "http://127.0.0.1:7000")
    assert jb.cdp_url_or_raise() == "http://127.0.0.1:7000"


def test_cdp_url_or_raise_arg_explicito_vence(monkeypatch):
    monkeypatch.setenv("JUSBRASIL_CDP_URL", "http://127.0.0.1:7000")
    assert jb.cdp_url_or_raise("http://127.0.0.1:9999") == "http://127.0.0.1:9999"


def test_jusbrasil_session_e_subclasse_neutra():
    assert issubclass(jb.JusbrasilCdpSession, CdpSession)


def test_base_host_e_jusbrasil():
    assert jb.BASE_HOST == "https://www.jusbrasil.com.br"


def test_throttle_primeira_chamada_nao_dorme():
    dormiu = []
    relogio = [100.0]
    jb._last_hit[0] = 0.0
    jb._throttle(now=lambda: relogio[0], sleep=lambda s: dormiu.append(s))
    assert dormiu == []
    assert jb._last_hit[0] == 100.0


def test_throttle_dorme_o_restante_quando_rapido():
    dormiu = []
    relogio = [100.0]
    jb._last_hit[0] = 99.0  # 1s atras (< 2s)
    jb._throttle(now=lambda: relogio[0], sleep=lambda s: dormiu.append(s))
    assert len(dormiu) == 1
    assert abs(dormiu[0] - 1.0) < 1e-6  # dorme o restante ate 2s


def test_throttle_nao_dorme_quando_intervalo_suficiente():
    dormiu = []
    relogio = [100.0]
    jb._last_hit[0] = 97.0  # 3s atras (>= 2s)
    jb._throttle(now=lambda: relogio[0], sleep=lambda s: dormiu.append(s))
    assert dormiu == []


def test_abrir_dom_aplica_throttle(monkeypatch):
    chamou = []
    monkeypatch.setattr(jb, "_throttle", lambda: chamou.append(True))

    class FakeSession:
        def __init__(self, url, timeout=None): pass
        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def navigate(self, url): pass
        def wait_ready(self, extra=1.5): return True
        def evaluate(self, js, await_promise=False): return "x"

    monkeypatch.setattr(jb, "JusbrasilCdpSession", FakeSession)
    monkeypatch.delenv("JUSBRASIL_CDP_URL", raising=False)
    jb.abrir_dom("https://x/y", "document.title")
    assert chamou == [True]


def test_abrir_dom_navega_espera_e_avalia(monkeypatch):
    """abrir_dom abre a sessao, navega, aguarda o DOM e avalia o JS (em ordem)."""
    chamadas = []

    class FakeSession:
        def __init__(self, url, timeout=None):
            chamadas.append(("init", url))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            chamadas.append(("exit", None))
            return False

        def navigate(self, url):
            chamadas.append(("navigate", url))

        def wait_ready(self, extra=1.5):
            chamadas.append(("wait_ready", extra))
            return True

        def evaluate(self, js, await_promise=False):
            chamadas.append(("evaluate", js))
            return "<dom-value>"

    monkeypatch.setattr(jb, "JusbrasilCdpSession", FakeSession)
    monkeypatch.setattr(jb, "_throttle", lambda: None)
    monkeypatch.delenv("JUSBRASIL_CDP_URL", raising=False)

    out = jb.abrir_dom("https://www.jusbrasil.com.br/jurisprudencia/busca?q=x", "document.title")

    assert out == "<dom-value>"
    ordem = [c[0] for c in chamadas]
    assert ordem == ["init", "navigate", "wait_ready", "evaluate", "exit"]
    assert chamadas[0] == ("init", "http://127.0.0.1:9222")
    assert chamadas[1] == ("navigate", "https://www.jusbrasil.com.br/jurisprudencia/busca?q=x")
    assert chamadas[3] == ("evaluate", "document.title")
