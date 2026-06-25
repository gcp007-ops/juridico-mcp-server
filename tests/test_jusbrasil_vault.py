import pytest

from juridico_mcp.jusbrasil import vault as jbv


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
    "ementa": "APELAÇÃO CÍVEL - USUCAPIÃO.\n1. requisito um.\n2. requisito dois.\nSENTENÇA MANTIDA.",
    "inteiro_teor": "EMENTA: APELAÇÃO CÍVEL - USUCAPIÃO.\n\nACÓRDÃO\nVistos...",
    "citavel": False,
}


def test_escapar_itens_numerados():
    out = jbv._escapar_itens_numerados("1. primeiro\n2. segundo\ntexto")
    assert "1\\. primeiro" in out
    assert "2\\. segundo" in out
    assert "texto" in out


def test_montar_frontmatter_tem_required_e_gate():
    fm = jbv.montar_frontmatter(PAYLOAD, created="2026-06-24")
    assert fm.startswith("---\n")
    assert "noteType: julgado" in fm
    assert 'tribunal: "TJMG"' in fm
    assert 'classe: "Apelação Cível"' in fm
    assert 'numero: "0151627-76.2005.8.13.0054"' in fm
    assert "citavel: false" in fm
    assert "status: pendente_verificacao" in fm
    assert 'fonte: "Jusbrasil"' in fm
    assert 'created: "2026-06-24"' in fm
    assert "- jurisprudencia" in fm


def test_montar_corpo_tem_secoes_e_escapa_ementa():
    corpo = jbv.montar_corpo(PAYLOAD)
    assert "## Ementa Integral" in corpo
    assert "## Referência" in corpo
    assert "## Conferência" in corpo
    assert "## Pendências" in corpo
    # itens numerados da ementa escapados (gate anti-lista)
    assert "1\\. requisito um" in corpo
    # metadados de cabecalho no corpo (nao no frontmatter)
    assert "Lílian Maciel" in corpo
    assert "Câmaras Cíveis / 20ª CÂMARA CÍVEL" in corpo


def test_escrever_julgado_grava_em_subpasta_jusbrasil(tmp_path):
    path = jbv.escrever_julgado(PAYLOAD, base_path=str(tmp_path), created="2026-06-24")
    assert path.endswith(".md")
    assert "Julgados" in path and "Jusbrasil" in path
    conteudo = open(path, encoding="utf-8").read()
    assert conteudo.startswith("---\n")
    assert "citavel: false" in conteudo
    assert "## Ementa Integral" in conteudo


def test_escrever_julgado_required_ausente_levanta(tmp_path):
    incompleto = dict(PAYLOAD)
    incompleto["numero"] = ""
    with pytest.raises(ValueError, match="numero"):
        jbv.escrever_julgado(incompleto, base_path=str(tmp_path))


def test_escrever_julgado_sem_base_path_levanta(monkeypatch):
    monkeypatch.delenv("THINKBOX_VAULT_PATH", raising=False)
    with pytest.raises(ValueError, match="THINKBOX_VAULT_PATH"):
        jbv.escrever_julgado(PAYLOAD)
