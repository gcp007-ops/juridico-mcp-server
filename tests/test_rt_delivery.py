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
