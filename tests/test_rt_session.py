import inspect
import pytest
from juridico_mcp.rt import session as sess
from juridico_mcp.rt.cdp_session import RtSessionExpired
from cdp_scaffold.cdp import CdpError


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


# Fix #5 — CdpError triggers relogin
def test_run_search_form_cdp_error_triggers_relogin(monkeypatch):
    """CdpError on first attempt must trigger relogin and retry, returning HTML."""
    chamadas = {"fetch": 0, "login": 0}

    def fake_fetch(entry, fields, placeholders, cdp_url, timeout):
        chamadas["fetch"] += 1
        if chamadas["fetch"] == 1:
            raise CdpError("js boom")
        return "<html>ok</html>"

    monkeypatch.setattr(sess, "_fetch_html", fake_fetch)
    monkeypatch.setattr(sess, "cdp_url_or_raise", lambda u=None: "http://x")

    import juridico_mcp.rt.auth as auth
    monkeypatch.setattr(
        auth, "login_rt_via_cdp",
        lambda url: chamadas.__setitem__("login", chamadas["login"] + 1),
    )

    out = sess.run_search_form("entry", {"frt": "x"}, placeholders=())
    assert out == "<html>ok</html>"
    assert chamadas["login"] == 1


def test_run_search_form_cdp_error_second_attempt_raises_runtime(monkeypatch):
    """CdpError on both attempts must raise RuntimeError (not propagate CdpError)."""
    def fake_fetch(*a, **k):
        raise CdpError("js boom persistente")

    monkeypatch.setattr(sess, "_fetch_html", fake_fetch)
    monkeypatch.setattr(sess, "cdp_url_or_raise", lambda u=None: "http://x")

    import juridico_mcp.rt.auth as auth
    monkeypatch.setattr(auth, "login_rt_via_cdp", lambda url: None)

    with pytest.raises(RuntimeError, match="sessão segue inválida após relogin"):
        sess.run_search_form("entry", {"frt": "x"}, placeholders=())


# Fix #6 — login timeout default is 60.0
def test_login_rt_via_cdp_default_timeout_is_60():
    import juridico_mcp.rt.auth as auth
    sig = inspect.signature(auth.login_rt_via_cdp)
    assert sig.parameters["timeout"].default == 60.0


# Fix #9 — _auth0_fill_field_js dedup preserves behavior
def test_auth0_fill_identifier_js_contains_required_markers():
    from juridico_mcp.rt.auth import _auth0_fill_identifier_js
    js = _auth0_fill_identifier_js("user@example.com")
    assert "user@example.com" in js
    assert "username_not_found" in js
    assert 'button[type="submit"]' in js or "button[type=\\'submit\\']" in js or 'button[type=\\"submit\\"]' in js
    assert "submitted" in js
    assert "btn_not_found" in js


def test_auth0_fill_password_js_contains_required_markers():
    from juridico_mcp.rt.auth import _auth0_fill_password_js
    js = _auth0_fill_password_js("s3cr3t")
    assert "s3cr3t" in js
    assert "password_not_found" in js
    assert 'button[type="submit"]' in js or 'button[type=\\"submit\\"]' in js
    assert "submitted" in js
    assert "btn_not_found" in js


def test_auth0_fill_identifier_js_submit_selector_present():
    """The exact submit selector must be present in both field JS builders."""
    from juridico_mcp.rt.auth import _auth0_fill_identifier_js, _auth0_fill_password_js
    SUBMIT = 'button[type=\\"submit\\"][name=\\"action\\"]'
    SUBMIT_ALT = "button[type=\"submit\"][name=\"action\"]"
    id_js = _auth0_fill_identifier_js("a@b.com")
    pw_js = _auth0_fill_password_js("pw")
    # At least one representation must appear
    assert (SUBMIT in id_js or SUBMIT_ALT in id_js), f"submit selector missing from identifier JS: {id_js[:200]}"
    assert (SUBMIT in pw_js or SUBMIT_ALT in pw_js), f"submit selector missing from password JS: {pw_js[:200]}"
