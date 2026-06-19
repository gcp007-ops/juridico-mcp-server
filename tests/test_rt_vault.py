import pathlib
import pytest
from juridico_mcp.rt import vault


def test_slug_ascii():
    assert vault.slug_ascii("0010198-10.2024.5.03.0079") == "0010198-10-2024-5-03-0079"


def test_montar_frontmatter_julgado_required_e_escape():
    fm = vault.montar_frontmatter({"tribunal": "TRT: 3", "classe": "RO", "numero": "001",
                                   "relator": "Morais", "data_julgamento": "8/10/2024",
                                   "assunto": "Trabalho", "jrp": "JRP\\2024\\1", "url": "https://rt/x"})
    assert "noteType: julgado" in fm
    assert 'tribunal: "TRT: 3"' in fm   # escapado/aspas (não quebra YAML)
    assert "classe:" in fm and "numero:" in fm
    assert 'fonte: "RT Online"' in fm


def test_escrever_julgado_required_ausente_levanta(tmp_path):
    with pytest.raises(ValueError):
        vault.escrever_julgado({"tribunal": "", "classe": "", "numero": ""}, "corpo", base_path=str(tmp_path))


def test_escrever_julgado_grava(tmp_path):
    p = pathlib.Path(vault.escrever_julgado(
        {"tribunal": "TRT-3", "classe": "RO", "numero": "0010198-10.2024.5.03.0079",
         "relator": "Morais", "data_julgamento": "8/10/2024", "url": "https://rt/x", "jrp": "JRP\\2024\\1"},
        "corpo md", base_path=str(tmp_path)))
    assert p.exists() and p.parent.as_posix().endswith("Conhecimento/Fontes/Julgados/RT")
    txt = p.read_text(encoding="utf-8")
    assert txt.startswith("---\n") and "noteType: julgado" in txt and "corpo md" in txt
