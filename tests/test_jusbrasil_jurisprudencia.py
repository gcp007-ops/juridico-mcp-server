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


def test_montar_url_ordenar_recente_usa_o_data():
    # Filtro de ordenacao confirmado ao vivo: o=data -> mais recente primeiro.
    assert "o=data" in jur._montar_url("x", 1, "recente")


def test_montar_url_ordenar_relevancia_e_default_sem_param():
    assert "o=" not in jur._montar_url("x", 1, "relevancia")


def test_buscar_passa_ordenar_recente(monkeypatch):
    cap = {}
    monkeypatch.setattr(jb, "abrir_dom", lambda url, js, **k: cap.update(url=url) or [])
    jur.buscar("x", ordenar="recente")
    assert "o=data" in cap["url"]


def test_montar_url_periodo_ano_usa_l_365dias():
    # Filtro de data confirmado ao vivo: l=365dias -> ultimo ano.
    assert "l=365dias" in jur._montar_url("x", 1, "relevancia", periodo="ano")


def test_montar_url_periodo_qualquer_e_default_sem_l():
    assert "l=" not in jur._montar_url("x", 1, "relevancia")
    assert "l=" not in jur._montar_url("x", 1, "relevancia", periodo="qualquer")


def test_montar_url_periodo_aceita_token_cru():
    assert "l=1825dias" in jur._montar_url("x", 1, "relevancia", periodo="1825dias")


def test_montar_url_combina_ordenar_e_periodo():
    u = jur._montar_url("x", 1, "recente", periodo="5anos")
    assert "o=data" in u and "l=1825dias" in u


def test_buscar_passa_periodo(monkeypatch):
    cap = {}
    monkeypatch.setattr(jb, "abrir_dom", lambda url, js, **k: cap.update(url=url) or [])
    jur.buscar("x", periodo="mes")
    assert "l=30dias" in cap["url"]


# --- Filtro de tribunal (param tribunal=<sigla minuscula>) confirmado ao vivo ---

def test_montar_url_tribunal_stj_usa_sigla_minuscula():
    # Chrome recon: selecionar STJ na pagina de resultados gera tribunal=stj.
    assert "tribunal=stj" in jur._montar_url("x", 1, tribunal="STJ")


def test_montar_url_tribunal_aceita_minuscula_na_entrada():
    assert "tribunal=tst" in jur._montar_url("x", 1, tribunal="tst")


def test_montar_url_tribunal_qualquer_e_default_sem_param():
    assert "tribunal=" not in jur._montar_url("x", 1)
    assert "tribunal=" not in jur._montar_url("x", 1, tribunal="qualquer")
    assert "tribunal=" not in jur._montar_url("x", 1, tribunal="")


def test_montar_url_tribunal_desconhecido_levanta():
    # Sigla fora do conjunto-familia observado: erro explicito, nao busca sem filtro.
    import pytest
    with pytest.raises(ValueError):
        jur._montar_url("x", 1, tribunal="TJBA")  # TJBA e slug, nao familia; familia e TJ


def test_buscar_passa_tribunal(monkeypatch):
    cap = {}
    monkeypatch.setattr(jb, "abrir_dom", lambda url, js, **k: cap.update(url=url) or [])
    jur.buscar("x", tribunal="STF")
    assert "tribunal=stf" in cap["url"]


# --- Filtro de tipo de julgado (param jurisType=<token>) ---

def test_montar_url_tipo_acordao_usa_juristype_acordao():
    # Confirmado ao vivo: Acordaos -> jurisType=acordao.
    assert "jurisType=acordao" in jur._montar_url("x", 1, tipo="acordao")


def test_montar_url_tipo_aceita_acento_e_sumula():
    # Confirmado ao vivo: Sumulas -> jurisType=sumula. Entrada com acento normaliza.
    assert "jurisType=sumula" in jur._montar_url("x", 1, tipo="Súmula")
    assert "jurisType=acordao" in jur._montar_url("x", 1, tipo="Acórdão")


def test_montar_url_tipo_todos_e_default_sem_param():
    assert "jurisType=" not in jur._montar_url("x", 1)
    assert "jurisType=" not in jur._montar_url("x", 1, tipo="todos")
    assert "jurisType=" not in jur._montar_url("x", 1, tipo="")


def test_montar_url_tipo_demais_opcoes_confirmadas():
    # Recon 2026-06-24: decisao/sentenca/despacho confirmados ao vivo (singular
    # minusculo sem acento), incl. formas plurais/acentuadas do menu.
    assert "jurisType=decisao" in jur._montar_url("x", 1, tipo="Decisões")
    assert "jurisType=sentenca" in jur._montar_url("x", 1, tipo="Sentenças")
    assert "jurisType=despacho" in jur._montar_url("x", 1, tipo="Despachos")


def test_montar_url_tipo_token_cru_e_valvula_seguranca():
    # Token alfabetico fora do mapa ainda passa como token cru (valvula de
    # seguranca para tipos futuros), igual ao passthrough de periodo.
    assert "jurisType=xyz" in jur._montar_url("x", 1, tipo="xyz")


def test_montar_url_combina_tribunal_e_tipo():
    u = jur._montar_url("x", 1, tribunal="STJ", tipo="acordao")
    assert "tribunal=stj" in u and "jurisType=acordao" in u


def test_buscar_passa_tipo(monkeypatch):
    cap = {}
    monkeypatch.setattr(jb, "abrir_dom", lambda url, js, **k: cap.update(url=url) or [])
    jur.buscar("x", tipo="acordao")
    assert "jurisType=acordao" in cap["url"]
