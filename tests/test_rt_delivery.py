import pytest

from juridico_mcp.rt import delivery
from juridico_mcp.rt.delivery import _docguid


def test_docguid_extracts_value():
    assert _docguid("https://x/doc?a=1&docguid=I08e8845&b=2") == "I08e8845"


def test_docguid_returns_none_when_absent():
    assert _docguid("https://x/doc?nofield=1") is None


def test_docguid_mismatch_detected():
    pedido = _docguid("https://x/doc?docguid=Aaaa1111")
    entregue = _docguid("https://x/delivery?docguid=Bbbb2222")
    assert pedido and entregue and pedido != entregue


def test_docguid_match_not_mismatched():
    pedido = _docguid("https://x/doc?docguid=I08e8845")
    entregue = _docguid("https://x/delivery?docguid=I08e8845")
    assert pedido == entregue


def test_parse_status_xml():
    assert delivery._parse_status_xml("<response><complete>true</complete><successful>true</successful></response>") == (True, True)
    assert delivery._parse_status_xml("<response><complete>true</complete><successful>false</successful></response>") == (True, False)
    assert delivery._parse_status_xml("<response><complete>false</complete></response>") == (False, False)


def test_parse_status_xml_whitespace_and_case():
    assert delivery._parse_status_xml("<complete> TRUE </complete><successful>true</successful>") == (True, True)


def test_normalizar_filename():
    assert delivery._normalizar_filename("RTDoc x.pdf.pdf", "PDF") == "RTDoc x.pdf"
    assert delivery._normalizar_filename("doc", "PDF") == "doc.pdf"


def test_baixar_documento_html_no_retrieval_levanta_sessao_expirada(monkeypatch):
    """Sessao morta serve a pagina de login (text/html) na URL de retrieval;
    o guard de content-type deve levantar CdpSessionExpired em vez de salvar HTML
    como .pdf."""
    import base64
    import json as _json
    from juridico_mcp.cdp_common import CdpSessionExpired

    DOC = "https://x/maf/app/document?docguid=Iabc123"
    DELIV = "https://x/maf/app/delivery/document?docguid=Iabc123"
    html = b"<html><body>login</body></html>"

    class FakeSession:
        def __init__(self, url, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def navigate(self, url):
            pass

        def wait_ready(self, extra=1.5):
            return True

        def evaluate(self, js, await_promise=False):
            if "saveImage" in js:
                return "ok"
            if "deliveryFormat" in js:
                return _json.dumps({
                    "delivery": DELIV,
                    "retrieveDeliveryUrl": "https://x/get",
                    "progress": "https://x/status",
                })
            if "arrayBuffer" in js:  # _fetch_bin_js: retrieval devolve HTML
                return _json.dumps({
                    "ct": "text/html; charset=utf-8",
                    "cd": "",
                    "b64": base64.b64encode(html).decode(),
                    "bytes": len(html),
                })
            # _fetch_text_js (trigger + poll de status): geracao concluida
            return "<response><complete>true</complete><successful>true</successful></response>"

    monkeypatch.setattr(delivery, "RtCdpSession", FakeSession)
    monkeypatch.setattr(delivery.time, "sleep", lambda *_: None)
    monkeypatch.setenv("RT_CDP_URL", "http://127.0.0.1:9222")

    with pytest.raises(CdpSessionExpired):
        delivery.baixar_documento(DOC, "PDF")
