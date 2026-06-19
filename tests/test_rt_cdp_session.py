from juridico_mcp.rt import cdp_session


def test_build_fetch_js_seta_campos_e_zera_placeholders():
    js = cdp_session.build_fetch_js({"frt": 'dano "moral"', "num": "123"}, ("jud", "tribunais"))
    assert "#searchForm" in js
    assert "123" in js and "jud" in js and "tribunais" in js
    assert "fetch(f.action" in js


def test_cdp_url_or_raise_sem_env(monkeypatch):
    monkeypatch.delenv("RT_CDP_URL", raising=False)
    import pytest
    with pytest.raises(RuntimeError, match="RT_CDP_URL"):
        cdp_session.cdp_url_or_raise()
