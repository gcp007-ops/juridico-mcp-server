import pathlib
from juridico_mcp.rt import jurisprudencia as j

FIX = pathlib.Path(__file__).parent / "fixtures" / "rt_juris_resultados.html"


def test_parse_resultados_extrai_campos():
    out = j.parse_resultados(FIX.read_text(encoding="utf-8"))
    assert len(out) == 2
    r = out[0]
    assert r["numero_processo"] == "0010198-10.2024.5.03.0079"
    assert r["relator"] == "José Murilo de Morais"
    assert r["data_julgamento"] == "08/10/2024"
    assert r["tribunal"] == "Tribunal Regional do Trabalho da 3.ª Região"
    assert r["jrp"] == "JRP\\2024\\1935245"
    assert "docguid=I08e88450884d11ef8abe8cec937cf41c" in r["url"]


def test_montar_campos_ano_e_intervalo():
    c1 = j.montar_campos(livre="dano", ano="2024")
    assert c1["frt"] == "dano" and c1["dateType"] == "year" and c1["ano"] == "2024"
    c2 = j.montar_campos(livre="dano", data_de="01/01/2024", data_ate="31/12/2024")
    assert c2["dateType"] == "between" and c2["fromDate"] == "01/01/2024" and c2["toDate"] == "31/12/2024"
    c3 = j.montar_campos(numero="0010198-10.2024.5.03.0079", relator="Morais")
    assert c3["num"].startswith("0010198") and c3["jud"] == "Morais"
