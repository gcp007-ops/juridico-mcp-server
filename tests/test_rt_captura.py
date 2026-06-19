import pathlib
from juridico_mcp.rt import captura_md
from juridico_mcp.rt import jurisprudencia as j

FIX = pathlib.Path(__file__).parent / "fixtures" / "rt_juris_doc.html"


def _fix_limpo():
    """Retorna o fixture já passado por _limpar_corpo (como extrair_documento faz)."""
    return captura_md._limpar_corpo(FIX.read_text(encoding="utf-8"))


def test_limpar_corpo_remove_relationship():
    md = captura_md.html_para_md(_fix_limpo())
    assert "RECORRENTE" in md
    assert "Jurisprudência (3)" not in md


def test_meta_do_corpo_extrai_campos_de_julgado():
    # _meta_do_corpo recebe HTML já limpo (Fix #8: sem double-clean)
    meta = j._meta_do_corpo(_fix_limpo())
    assert meta["numero"] == "0010198-10.2024.5.03.0079"
    assert meta["classe"] == "Recurso Ordinário em Rito Sumaríssimo"
    assert meta["relator"] == "José Murilo de Morais"
    assert meta["data_julgamento"] == "8/10/2024"
    assert "Trabalho" in meta["assunto"]
    assert meta["orgao_julgador"] == "6.ª Turma"
    assert meta["data_publicacao"] == "10/10/2024"


def test_meta_do_corpo_camara():
    """Regex _HEADER_TURMA deve casar Câmara além de Turma."""
    raw = "<div id=\"docContent\"><p>TJ-SP - Apelação 1234567-89.2023.8.26.0000 - 1.ª Câmara de Direito Privado - j. 5/3/2024 - julgado por João Silva - DJ 10/3/2024 - Área do Direito: Civil</p></div>"
    html = captura_md._limpar_corpo(raw)
    meta = j._meta_do_corpo(html)
    assert "Câmara" in meta["orgao_julgador"]
    assert meta["data_publicacao"] == "10/3/2024"


# ── Fix #1: broadened regexes (Rel./Min./Seção/Corte Especial) ──────────────


def test_meta_do_corpo_stj_rel_min():
    """Regex _HEADER_RELATOR deve casar 'Rel. Min.' (lead-in STJ/STF)."""
    raw = "<p>STJ - REsp 123456 - Terceira Turma - Rel. Min. Fulano de Tal - j. 1/1/2024 - DJe 2/1/2024</p>"
    html = captura_md._limpar_corpo(raw)
    meta = j._meta_do_corpo(html)
    assert "Fulano de Tal" in meta["relator"], f"relator={meta['relator']!r}"
    assert "Terceira Turma" in meta["orgao_julgador"], f"orgao={meta['orgao_julgador']!r}"


def test_meta_do_corpo_corte_especial():
    """Regex _HEADER_TURMA deve casar 'Corte Especial'."""
    raw = "<p>STJ - EREsp 9999 - Corte Especial - Rel. Min. Beltrana - j. 5/5/2024 - DJe 6/5/2024</p>"
    html = captura_md._limpar_corpo(raw)
    meta = j._meta_do_corpo(html)
    assert "Corte Especial" in meta["orgao_julgador"], f"orgao={meta['orgao_julgador']!r}"


def test_meta_do_corpo_secao():
    """Regex _HEADER_TURMA deve casar 'Seção'."""
    raw = "<p>STJ - MS 12345 - Primeira Seção - Rel. Min. Ciclano - j. 10/2/2024 - DJe 11/2/2024</p>"
    html = captura_md._limpar_corpo(raw)
    meta = j._meta_do_corpo(html)
    assert "Seção" in meta["orgao_julgador"], f"orgao={meta['orgao_julgador']!r}"
