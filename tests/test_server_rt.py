import pytest
from juridico_mcp import server


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
