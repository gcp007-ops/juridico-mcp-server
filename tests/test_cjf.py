"""Testes do client CJF (httpx/JSF). Foco: refresh do ViewState (regressao)."""
from juridico_mcp.clients import cjf


class _FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def _client_sem_parse(monkeypatch):
    c = cjf.CJFClient()
    # nao exercita o parser de resultados; foco e o ViewState
    monkeypatch.setattr(c, "_parse_resultados", lambda *a, **k: [])
    return c


def test_buscar_atualiza_viewstate_do_cdata_partial_ajax(monkeypatch):
    # JSF partial-ajax devolve o novo ViewState dentro de <update><![CDATA[...]]>.
    # A regex antiga nao casava o CDATA -> ViewState ficava velho -> ViewExpired
    # na 2a busca (client e singleton).
    c = _client_sem_parse(monkeypatch)
    c._viewstate = "VS_VELHO"
    resp = _FakeResp(
        '<?xml version="1.0"?><partial-response><changes>'
        '<update id="formulario:resultado"><![CDATA[<div/>]]></update>'
        '<update id="javax.faces.ViewState"><![CDATA[VS_NOVO_123]]></update>'
        '</changes></partial-response>'
    )
    monkeypatch.setattr(c._client, "post", lambda *a, **k: resp)
    c.buscar("dano moral", "STJ", 5)
    assert c._viewstate == "VS_NOVO_123"


def test_descobrir_campo_tribunal_pega_name_do_input_da_sigla():
    html = (
        '<input type="checkbox" name="formulario:j_idt59" value="STJ" />'
        '<input type="checkbox" name="formulario:j_idt59" value="TRF1" />'
    )
    assert cjf._descobrir_campo_tribunal(html) == "formulario:j_idt59"


def test_descobrir_campo_tribunal_independe_da_ordem_dos_atributos():
    html = '<input value="TRF3" name="form:abc" class="x">'
    assert cjf._descobrir_campo_tribunal(html) == "form:abc"


def test_descobrir_campo_tribunal_fallback_quando_ausente():
    assert cjf._descobrir_campo_tribunal("<html>sem tribunais</html>") == cjf._DEFAULT_CAMPO_TRIBUNAL


def test_buscar_usa_campo_tribunal_descoberto_no_post(monkeypatch):
    # Regressao do drift JSF j_idtNN: o name do checkbox vem da pagina, nao hardcoded.
    c = cjf.CJFClient()
    get_html = (
        '<input name="javax.faces.ViewState" value="VS1" />'
        '<input name="formulario:j_idt77" value="STJ" />'
    )
    monkeypatch.setattr(c._client, "get", lambda *a, **k: _FakeResp(get_html))
    captured = {}

    def fake_post(url, content=None, headers=None):
        captured["body"] = content.decode() if isinstance(content, bytes) else content
        return _FakeResp("<partial-response></partial-response>")

    monkeypatch.setattr(c._client, "post", fake_post)
    monkeypatch.setattr(c, "_parse_resultados", lambda *a, **k: [])
    c.buscar("dano moral", "STJ", 5)
    assert c._campo_tribunal == "formulario:j_idt77"
    assert "formulario%3Aj_idt77=STJ" in captured["body"]  # urlencoded


def test_buscar_viewstate_fallback_pagina_cheia(monkeypatch):
    # Se vier a pagina cheia (raro), o fallback name=...value=... ainda funciona.
    c = _client_sem_parse(monkeypatch)
    c._viewstate = "VS_VELHO"
    resp = _FakeResp(
        'algo <input name="javax.faces.ViewState" value="VS_FULL_9" /> mais'
    )
    monkeypatch.setattr(c._client, "post", lambda *a, **k: resp)
    c.buscar("x", "STJ", 5)
    assert c._viewstate == "VS_FULL_9"
