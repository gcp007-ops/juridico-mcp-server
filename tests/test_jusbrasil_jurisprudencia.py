from juridico_mcp.jusbrasil import jurisprudencia as jur
from juridico_mcp.jusbrasil import session as jb


# Registros com o formato REAL capturado ao vivo (busca usucapiao extraordinaria).
SAMPLE = [
    {
        "titulo": "TJ-MG - Apelação Cível: AC 10054050151627001 Barão de Cocais",
        "href": "https://www.jusbrasil.com.br/jurisprudencia/tj-mg/1373234347",
        "caption": "JurisprudênciaAcórdãopublicado em 08/02/2022",
        "ementa": "Ementa: EMENTA: APELAÇÃO CÍVEL - USUCAPIÃO EXTRAORDINÁRIA - POSSE MANSA",
    },
    {
        "titulo": "TJ-GO - Apelação Cível 52036748620178090100 LUZIÂNIA",
        "href": "https://www.jusbrasil.com.br/jurisprudencia/tj-go/2228592448",
        "caption": "JurisprudênciaAcórdãopublicado em 13/03/2024",
        "ementa": "Ementa: PODER JUDICIÁRIO Tribunal de Justiça do Estado de Goiás",
    },
]


def test_doc_id_from_href_pega_segmento_numerico_final():
    assert jur._doc_id_from_href("https://www.jusbrasil.com.br/jurisprudencia/tj-mg/1373234347") == "1373234347"
    assert jur._doc_id_from_href("/jurisprudencia/stj/1101102738") == "1101102738"


def test_doc_id_from_href_sem_doc_retorna_vazio():
    assert jur._doc_id_from_href("https://www.jusbrasil.com.br/jurisprudencia/busca?q=x") == ""
    assert jur._doc_id_from_href("") == ""


def test_slug_from_href():
    assert jur._slug_from_href("https://www.jusbrasil.com.br/jurisprudencia/tj-mg/1373234347") == "tj-mg"
    assert jur._slug_from_href("/jurisprudencia/stj/1101102738") == "stj"


def test_tribunal_do_slug_mapeado_e_fallback():
    assert jur.tribunal_do_slug("stj") == "STJ"
    assert jur.tribunal_do_slug("tj-df") == "TJDFT"
    assert jur.tribunal_do_slug("tj-mg") == "TJMG"
    # slug desconhecido: fallback para sigla derivada, sem inventar
    assert jur.tribunal_do_slug("tj-zz") == "TJ-ZZ"


def test_parse_caption_extrai_tipo_e_data():
    out = jur._parse_caption("JurisprudênciaAcórdãopublicado em 08/02/2022")
    assert out["tipo"] == "Acórdão"
    assert out["data_publicacao"] == "08/02/2022"


def test_parse_caption_sem_data_nao_inventa():
    out = jur._parse_caption("Jurisprudência")
    assert out["data_publicacao"] == ""


def test_ementa_limpa_remove_prefixo_redundante():
    assert jur._ementa_limpa("Ementa: EMENTA: APELAÇÃO").startswith("EMENTA: APELAÇÃO")
    assert jur._ementa_limpa("texto sem prefixo") == "texto sem prefixo"


def test_normalizar_produz_campos_esperados():
    out = jur.normalizar(SAMPLE)
    assert len(out) == 2
    r0 = out[0]
    assert r0["doc_id"] == "1373234347"
    assert r0["slug"] == "tj-mg"
    assert r0["tribunal"] == "TJMG"
    assert r0["tipo"] == "Acórdão"
    assert r0["data_publicacao"] == "08/02/2022"
    assert r0["url"] == "https://www.jusbrasil.com.br/jurisprudencia/tj-mg/1373234347"
    assert r0["titulo"] == "TJ-MG - Apelação Cível: AC 10054050151627001 Barão de Cocais"
    assert r0["ementa"].startswith("EMENTA: APELAÇÃO")


def test_normalizar_descarta_sem_href():
    out = jur.normalizar([{"titulo": "x", "href": "", "caption": "", "ementa": ""}])
    assert out == []


def test_buscar_monta_url_e_normaliza(monkeypatch):
    capturado = {}

    def fake_abrir_dom(url, js, **kwargs):
        capturado["url"] = url
        capturado["js"] = js
        return SAMPLE

    monkeypatch.setattr(jb, "abrir_dom", fake_abrir_dom)

    out = jur.buscar("usucapião extraordinária", max_resultados=10)

    assert "jurisprudencia/busca" in capturado["url"]
    assert "usucapi" in capturado["url"]  # termo url-encoded
    assert len(out) == 2
    assert out[0]["tribunal"] == "TJMG"


def test_buscar_pagina_acrescenta_p(monkeypatch):
    capturado = {}
    monkeypatch.setattr(jb, "abrir_dom", lambda url, js, **k: capturado.update(url=url) or [])
    jur.buscar("x", pagina=3)
    assert "p=3" in capturado["url"]


def test_buscar_respeita_max_resultados(monkeypatch):
    monkeypatch.setattr(jb, "abrir_dom", lambda url, js, **k: SAMPLE)
    out = jur.buscar("x", max_resultados=1)
    assert len(out) == 1
