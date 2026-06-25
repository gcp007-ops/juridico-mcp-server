import json as _j

from juridico_mcp import server


PAYLOAD = {
    "fonte": "jusbrasil",
    "url_origem": "https://www.jusbrasil.com.br/jurisprudencia/tj-mg/1373234347",
    "url_inteiro_teor": "https://www.jusbrasil.com.br/jurisprudencia/tj-mg/1373234347/inteiro-teor-1373238664",
    "tribunal": "TJMG",
    "slug": "tj-mg",
    "numero": "0151627-76.2005.8.13.0054",
    "classe": "Apelação Cível",
    "relator": "Lílian Maciel",
    "orgao_julgador": "Câmaras Cíveis / 20ª CÂMARA CÍVEL",
    "data_julgamento": "02/02/2022",
    "ementa": "APELAÇÃO CÍVEL - USUCAPIÃO. SENTENÇA MANTIDA.",
    "inteiro_teor": "EMENTA: APELAÇÃO CÍVEL - USUCAPIÃO.\n\nACÓRDÃO\nVistos...",
    "citavel": False,
}


def test_inteiro_teor_sem_doc_url():
    out = server.jusbrasil_inteiro_teor("")
    assert "invalido" in out.lower()


def test_inteiro_teor_gravar_false_retorna_payload(monkeypatch):
    monkeypatch.setattr(server.jb_it, "extrair_inteiro_teor", lambda doc, **k: PAYLOAD)
    out = _j.loads(server.jusbrasil_inteiro_teor("https://x/jurisprudencia/tj-mg/1373234347", gravar=False))
    assert out["status"] == "ok"
    assert out["tribunal"] == "TJMG"
    assert out["numero"] == "0151627-76.2005.8.13.0054"
    assert out["citavel"] is False
    assert out["inteiro_teor"].startswith("EMENTA:")


def test_inteiro_teor_gravar_true_grava(monkeypatch, tmp_path):
    monkeypatch.setattr(server.jb_it, "extrair_inteiro_teor", lambda doc, **k: PAYLOAD)
    monkeypatch.setattr(server.jb_vault, "escrever_julgado",
                        lambda meta, **k: str(tmp_path / "nota.md"))
    out = _j.loads(server.jusbrasil_inteiro_teor("https://x/jurisprudencia/tj-mg/1373234347", gravar=True))
    assert out["status"] == "ok"
    assert out["path"].endswith(".md")


def test_inteiro_teor_gravar_required_ausente_preserva_conteudo(monkeypatch):
    monkeypatch.setattr(server.jb_it, "extrair_inteiro_teor", lambda doc, **k: PAYLOAD)

    def _raise(meta, **k):
        raise ValueError("julgado: campos required ausentes: numero")

    monkeypatch.setattr(server.jb_vault, "escrever_julgado", _raise)
    out = _j.loads(server.jusbrasil_inteiro_teor("https://x/jurisprudencia/tj-mg/1373234347", gravar=True))
    assert out["status"] == "ok_sem_gravacao"
    assert "aviso" in out
    assert out["inteiro_teor"].startswith("EMENTA:")


def test_inteiro_teor_propaga_erro_extracao(monkeypatch):
    def boom(doc, **k):
        raise RuntimeError("CDP caiu")
    monkeypatch.setattr(server.jb_it, "extrair_inteiro_teor", boom)
    out = _j.loads(server.jusbrasil_inteiro_teor("https://x/jurisprudencia/tj-mg/1"))
    assert out["status"] == "erro"
    assert "CDP caiu" in out["mensagem"]
