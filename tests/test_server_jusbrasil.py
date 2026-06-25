from juridico_mcp import server


NORMALIZADO = [
    {
        "titulo": "TJ-MG - Apelação Cível: AC 10054050151627001 Barão de Cocais",
        "url": "https://www.jusbrasil.com.br/jurisprudencia/tj-mg/1373234347",
        "doc_id": "1373234347",
        "slug": "tj-mg",
        "tribunal": "TJMG",
        "tipo": "Acórdão",
        "data_publicacao": "08/02/2022",
        "ementa": "EMENTA: APELAÇÃO CÍVEL - USUCAPIÃO EXTRAORDINÁRIA - POSSE MANSA",
    },
]


def test_jusbrasil_buscar_formata(monkeypatch):
    monkeypatch.setattr(server.jb_juris, "buscar", lambda termo, **k: NORMALIZADO)
    out = server.jusbrasil_jurisprudencia_buscar(termo="usucapião")
    assert isinstance(out, str)
    assert "TJMG" in out
    assert "USUCAPIÃO EXTRAORDINÁRIA" in out
    assert "https://www.jusbrasil.com.br/jurisprudencia/tj-mg/1373234347" in out


def test_jusbrasil_buscar_sem_termo():
    out = server.jusbrasil_jurisprudencia_buscar(termo="")
    assert "invalido" in out.lower()


def test_jusbrasil_buscar_propaga_erro(monkeypatch):
    def boom(termo, **k):
        raise RuntimeError("CDP caiu")
    monkeypatch.setattr(server.jb_juris, "buscar", boom)
    out = server.jusbrasil_jurisprudencia_buscar(termo="x")
    assert "Erro" in out and "CDP caiu" in out
