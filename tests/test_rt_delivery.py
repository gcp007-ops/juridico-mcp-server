from juridico_mcp.rt import delivery


def test_parse_status_xml():
    assert delivery._parse_status_xml("<response><complete>true</complete><successful>true</successful></response>") == (True, True)
    assert delivery._parse_status_xml("<response><complete>true</complete><successful>false</successful></response>") == (True, False)
    assert delivery._parse_status_xml("<response><complete>false</complete></response>") == (False, False)


def test_normalizar_filename():
    assert delivery._normalizar_filename("RTDoc x.pdf.pdf", "PDF") == "RTDoc x.pdf"
    assert delivery._normalizar_filename("doc", "PDF") == "doc.pdf"
