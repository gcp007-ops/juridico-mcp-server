import pathlib
from juridico_mcp.rt import captura_md
from juridico_mcp.rt import jurisprudencia as j

FIX = pathlib.Path(__file__).parent / "fixtures" / "rt_juris_doc.html"


def test_limpar_corpo_remove_relationship():
    md = captura_md.html_para_md(captura_md._limpar_corpo(FIX.read_text(encoding="utf-8")))
    assert "RECORRENTE" in md
    assert "Jurisprudência (3)" not in md


def test_meta_do_corpo_extrai_campos_de_julgado():
    meta = j._meta_do_corpo(FIX.read_text(encoding="utf-8"))
    assert meta["numero"] == "0010198-10.2024.5.03.0079"
    assert meta["classe"] == "Recurso Ordinário em Rito Sumaríssimo"
    assert meta["relator"] == "José Murilo de Morais"
    assert meta["data_julgamento"] == "8/10/2024"
    assert "Trabalho" in meta["assunto"]
    assert meta["orgao_julgador"] == "6.ª Turma"
    assert meta["data_publicacao"] == "10/10/2024"


def test_meta_do_corpo_camara():
    """Regex _HEADER_TURMA deve casar Câmara além de Turma."""
    html = "<div id=\"docContent\"><p>TJ-SP - Apelação 1234567-89.2023.8.26.0000 - 1.ª Câmara de Direito Privado - j. 5/3/2024 - julgado por João Silva - DJ 10/3/2024 - Área do Direito: Civil</p></div>"
    meta = j._meta_do_corpo(html)
    assert "Câmara" in meta["orgao_julgador"]
    assert meta["data_publicacao"] == "10/3/2024"
