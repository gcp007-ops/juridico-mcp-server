import pytest
from juridico_mcp import server


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
