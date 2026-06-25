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
