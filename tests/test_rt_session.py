import pytest
from juridico_mcp.rt import session as sess
from juridico_mcp.rt.cdp_session import RtSessionExpired


def test_run_search_form_relogin_retry_succeeds(monkeypatch):
    chamadas = {"fetch": 0, "login": 0}
    def fake_fetch(entry, fields, placeholders, cdp_url, timeout):
        chamadas["fetch"] += 1
        if chamadas["fetch"] == 1:
            raise RtSessionExpired("expirou")
        return "<html>ok</html>"
    monkeypatch.setattr(sess, "_fetch_html", fake_fetch)
    monkeypatch.setattr(sess, "cdp_url_or_raise", lambda u=None: "http://x")
    import juridico_mcp.rt.auth as auth
    monkeypatch.setattr(auth, "login_rt_via_cdp", lambda url: chamadas.__setitem__("login", chamadas["login"] + 1))
    out = sess.run_search_form("entry", {"frt": "x"}, placeholders=())
    assert out == "<html>ok</html>" and chamadas["login"] == 1


def test_run_search_form_relogin_falha_levanta_runtime(monkeypatch):
    def fake_fetch(*a, **k): raise RtSessionExpired("sempre")
    monkeypatch.setattr(sess, "_fetch_html", fake_fetch)
    monkeypatch.setattr(sess, "cdp_url_or_raise", lambda u=None: "http://x")
    import juridico_mcp.rt.auth as auth
    monkeypatch.setattr(auth, "login_rt_via_cdp", lambda url: None)
    with pytest.raises(RuntimeError):
        sess.run_search_form("entry", {"frt": "x"}, placeholders=())
