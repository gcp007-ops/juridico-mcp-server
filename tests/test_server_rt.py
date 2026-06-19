import pytest
from juridico_mcp import server
import json as _j


def test_rt_baixar_pdf_grava(monkeypatch, tmp_path):
    monkeypatch.setattr(server.rt_delivery, "baixar_documento",
                        lambda doc, formato="PDF", **k: (b"%PDF-1.3 x", "julgado.pdf"))
    import json as _j
    out = _j.loads(server.rt_baixar_pdf("https://rt/doc?docguid=X", destino=str(tmp_path)))
    assert out["bytes"] == len(b"%PDF-1.3 x")
    assert (tmp_path / "julgado.pdf").read_bytes().startswith(b"%PDF")


def test_rt_baixar_pdf_vazio():
    assert "invalido" in server.rt_baixar_pdf("").lower()


@pytest.mark.asyncio
async def test_rt_jurisprudencia_buscar_formata(monkeypatch):
    async def fake_buscar(**kw):
        return [{"numero_processo": "0010198-10.2024.5.03.0079", "relator": "Morais",
                 "data_julgamento": "08/10/2024", "tribunal": "TRT-3",
                 "veiculo": "DEJT", "data_publicacao": "Out/2024", "jrp": "JRP\\2024\\1",
                 "url": "https://rt/doc?docguid=X"}]
    monkeypatch.setattr(server.rt_juris, "buscar", fake_buscar)
    out = await server.rt_jurisprudencia_buscar(livre="dano moral")
    assert "0010198-10.2024.5.03.0079" in out and isinstance(out, str)


@pytest.mark.asyncio
async def test_rt_jurisprudencia_buscar_sem_parametro():
    out = await server.rt_jurisprudencia_buscar()
    assert "invalido" in out.lower()


def test_rt_capturar_md_retorna_markdown(monkeypatch):
    monkeypatch.setattr(server.rt_juris, "extrair_documento", lambda doc, **k: {
        "url": doc, "tribunal": "TRT-3", "numero": "001", "classe": "RO",
        "relator": "Morais", "data_julgamento": "8/10/2024", "data_publicacao": "",
        "orgao_julgador": "6.ª Turma", "assunto": "Trabalho", "jrp": "JRP\\2024\\1",
        "html_corpo": "<div id='docContent'><p>acórdão <b>x</b></p></div>"})
    out = _j.loads(server.rt_capturar_md("https://rt/doc?docguid=X", gravar=False))
    assert "**x**" in out["markdown"]


def test_rt_capturar_md_grava(monkeypatch, tmp_path):
    monkeypatch.setattr(server.rt_juris, "extrair_documento", lambda doc, **k: {
        "url": doc, "tribunal": "TRT-3", "numero": "0010198-10.2024.5.03.0079", "classe": "RO",
        "relator": "Morais", "data_julgamento": "8/10/2024", "data_publicacao": "",
        "orgao_julgador": "6.ª Turma", "assunto": "Trabalho", "jrp": "JRP\\2024\\1",
        "html_corpo": "<div id='docContent'><p>acórdão</p></div>"})
    monkeypatch.setenv("THINKBOX_VAULT_PATH", str(tmp_path))
    import json as _j
    out = _j.loads(server.rt_capturar_md("https://rt/doc?docguid=X", gravar=True))
    assert out["status"] == "ok" and out["path"].endswith(".md")
    import pathlib
    assert pathlib.Path(out["path"]).read_text(encoding="utf-8").startswith("---\n")
