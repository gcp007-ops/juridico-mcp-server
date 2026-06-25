from juridico_mcp.jusbrasil import inteiro_teor as it
from juridico_mcp.jusbrasil import session as jb


# Texto REAL renderizado no topo do <main> (recon doc tj-mg/1373234347).
TOP_TEXT = (
    "Tribunal de Justiça de Minas Gerais TJ-MG - Apelação Cível: AC 0151627-76.2005.8.13.0054 Barão de Cocais\n\n"
    "Processo AC 0151627-76.2005.8.13.0054 Barão de Cocais\n\n"
    "TJ-MG · Câmaras Cíveis / 20ª CÂMARA CÍVEL\n"
    "Relator · Lílian Maciel\n"
    "Julgado em 02/02/2022\n"
    "Mostrar mais\nEmenta\n"
)
LAWSUIT = "Processo AC 0151627-76.2005.8.13.0054 Barão de Cocais"


def test_parse_metadata_numero_cnj():
    meta = it._parse_metadata(LAWSUIT, TOP_TEXT)
    assert meta["numero"] == "0151627-76.2005.8.13.0054"


def test_parse_metadata_relator_orgao_data():
    meta = it._parse_metadata(LAWSUIT, TOP_TEXT)
    assert meta["relator"] == "Lílian Maciel"
    assert meta["orgao_julgador"] == "Câmaras Cíveis / 20ª CÂMARA CÍVEL"
    assert meta["data_julgamento"] == "02/02/2022"


def test_parse_metadata_classe():
    meta = it._parse_metadata(LAWSUIT, TOP_TEXT)
    assert meta["classe"] == "Apelação Cível"


def test_parse_metadata_vazio_nao_inventa():
    meta = it._parse_metadata("", "")
    assert meta["numero"] == ""
    assert meta["relator"] == ""
    assert meta["data_julgamento"] == ""


# Dados REAIS capturados de doc-pages STJ e STF (recon cross-court).
STJ_TOP = (
    "Superior Tribunal de Justiça STJ - AGRAVO INTERNO NOS EMBARGOS DE DECLARAÇÃO NA RECLAMAÇÃO: AgInt nos EDcl na Rcl 42019 SP 2021/0212311-0\n\n"
    "Processo AgInt nos EDcl na Rcl 42019 SP 2021/0212311-0\n\n"
    "STJ · S2 - SEGUNDA SEÇÃO\n"
    "Relator · Ministro LUIS FELIPE SALOMÃO\n"
    "Julgado em 15/03/2022\n"
)
STJ_LABEL = "Processo AgInt nos EDcl na Rcl 42019 SP 2021/0212311-0"

STF_TOP = (
    "Supremo Tribunal Federal STF - AG.REG. NO RECURSO EXTRAORDINÁRIO COM AGRAVO: ARE 1386809 SP\n\n"
    "Processo ARE 1386809 SP\n\n"
    "STF · Segunda Turma\n"
    "Relator · EDSON FACHIN\n"
    "Julgado em 26/09/2022\n"
)
STF_LABEL = "Processo ARE 1386809 SP"


def test_parse_metadata_stj_numero_e_classe():
    meta = it._parse_metadata(STJ_LABEL, STJ_TOP)
    assert meta["classe"] == "AGRAVO INTERNO NOS EMBARGOS DE DECLARAÇÃO NA RECLAMAÇÃO"
    assert meta["numero"]  # nao vazio (gate required satisfeito)
    assert "Rcl 42019" in meta["numero"]
    assert meta["relator"] == "Ministro LUIS FELIPE SALOMÃO"
    assert meta["orgao_julgador"] == "S2 - SEGUNDA SEÇÃO"
    assert meta["data_julgamento"] == "15/03/2022"


def test_parse_metadata_stf_numero_e_classe():
    meta = it._parse_metadata(STF_LABEL, STF_TOP)
    assert meta["classe"] == "AG.REG. NO RECURSO EXTRAORDINÁRIO COM AGRAVO"
    assert "ARE 1386809" in meta["numero"]
    assert meta["relator"] == "EDSON FACHIN"
    assert meta["orgao_julgador"] == "Segunda Turma"
    assert meta["data_julgamento"] == "26/09/2022"


def test_extrair_inteiro_teor_ignora_stale_e_espera_estabilizar(monkeypatch):
    """Bug do poll: nao pode capturar o conteudo stale pre-clique (2315) nem o 0 transitorio."""
    seqs = iter([
        {"url": "https://x/jurisprudencia/stj/123", "text": "S" * 2315},                 # stale, url sem inteiro-teor
        {"url": "https://x/jurisprudencia/stj/123/inteiro-teor-9", "text": ""},           # rerender (0)
        {"url": "https://x/jurisprudencia/stj/123/inteiro-teor-9", "text": "EMENTA: T\n" + "y" * 18000},  # cheio
        {"url": "https://x/jurisprudencia/stj/123/inteiro-teor-9", "text": "EMENTA: T\n" + "y" * 18000},  # estavel (repeticao)
    ])

    class FakeSession:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def navigate(self, u): pass
        def wait_ready(self, extra=1.5): return True
        def evaluate(self, js, await_promise=False):
            if "lawsuitLabel" in js:
                return {"lawsuitLabel": "Processo X", "topText": "Corte X - Classe Y: N"}
            if ".click()" in js:
                return "ok"
            return next(seqs)

    monkeypatch.setattr(it, "JusbrasilCdpSession", FakeSession)
    monkeypatch.setattr(it, "_throttle", lambda: None)
    monkeypatch.setattr(it.time, "sleep", lambda *_: None)

    out = it.extrair_inteiro_teor("https://x/jurisprudencia/stj/123")
    assert len(out["inteiro_teor"]) > 15000  # pegou o teor cheio, nao o stale 2315
    assert out["url_inteiro_teor"].endswith("inteiro-teor-9")


def test_limpar_inteiro_teor_remove_prefixo_de_abas():
    raw = "Resumo\nInteiro Teor\nFatos\nInteiro Teor\n\n\nEMENTA: APELAÇÃO\nbody aqui"
    out = it._limpar_inteiro_teor(raw)
    assert out.startswith("EMENTA: APELAÇÃO")
    assert "body aqui" in out
    assert "Resumo" not in out.split("\n")[0]


def test_extrair_ementa_pega_bloco_ementa():
    teor = "EMENTA: APELAÇÃO CÍVEL - USUCAPIÃO. SENTENÇA MANTIDA.\n\nACÓRDÃO\nVistos..."
    em = it._extrair_ementa(teor)
    assert em.startswith("APELAÇÃO CÍVEL - USUCAPIÃO")
    assert "ACÓRDÃO" not in em


def test_extrair_ementa_sem_marcador_retorna_vazio():
    assert it._extrair_ementa("texto qualquer sem marcador") == ""


def test_extrair_inteiro_teor_monta_payload(monkeypatch):
    """Driver: navega, le metadados, clica a aba, le o teor e monta payload com gate."""
    passos = []

    class FakeSession:
        def __init__(self, url, timeout=None):
            passos.append("init")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            passos.append("exit")
            return False

        def navigate(self, url):
            passos.append(("navigate", url))

        def wait_ready(self, extra=1.5):
            passos.append("wait")
            return True

        def evaluate(self, js, await_promise=False):
            if "lawsuitLabel" in js:
                return {"lawsuitLabel": LAWSUIT, "topText": TOP_TEXT}
            if ".click()" in js:
                return "clicked:A"
            # AFTER: conteudo da aba inteiro teor
            return {
                "url": "https://www.jusbrasil.com.br/jurisprudencia/tj-mg/1373234347/inteiro-teor-1373238664",
                "text": "Resumo\nInteiro Teor\nFatos\nInteiro Teor\n\n\nEMENTA: APELAÇÃO CÍVEL - USUCAPIÃO. MANTIDA.\n\nACÓRDÃO\nVistos, relatados...",
            }

    monkeypatch.setattr(it, "JusbrasilCdpSession", FakeSession)
    monkeypatch.setattr(it, "_throttle", lambda: None)
    monkeypatch.setattr(it.time, "sleep", lambda *_: None)
    monkeypatch.delenv("JUSBRASIL_CDP_URL", raising=False)

    doc = "https://www.jusbrasil.com.br/jurisprudencia/tj-mg/1373234347"
    out = it.extrair_inteiro_teor(doc)

    assert out["citavel"] is False
    assert out["tribunal"] == "TJMG"
    assert out["numero"] == "0151627-76.2005.8.13.0054"
    assert out["relator"] == "Lílian Maciel"
    assert out["url_origem"] == doc
    assert out["url_inteiro_teor"].endswith("/inteiro-teor-1373238664")
    assert out["inteiro_teor"].startswith("EMENTA: APELAÇÃO CÍVEL")
    assert out["ementa"].startswith("APELAÇÃO CÍVEL - USUCAPIÃO")


def test_extrair_inteiro_teor_nunca_navega_nao_retorna_stale(monkeypatch):
    """Se a aba NUNCA navega para /inteiro-teor-, o teor deve sair vazio — nunca o
    conteudo stale grande da aba anterior (bug do poll antigo)."""

    class FakeSession:
        def __init__(self, url, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def navigate(self, url):
            pass

        def wait_ready(self, extra=1.5):
            return True

        def evaluate(self, js, await_promise=False):
            if "lawsuitLabel" in js:
                return {"lawsuitLabel": LAWSUIT, "topText": TOP_TEXT}
            if ".click()" in js:
                return "__NO_TAB__"  # aba nao encontrada/clique sem efeito
            # AFTER: URL nunca vira /inteiro-teor-; texto stale grande
            return {"url": "https://x/jurisprudencia/tj-mg/123", "text": "S" * 9000}

    monkeypatch.setattr(it, "JusbrasilCdpSession", FakeSession)
    monkeypatch.setattr(it, "_throttle", lambda: None)
    monkeypatch.setattr(it.time, "sleep", lambda *_: None)
    monkeypatch.delenv("JUSBRASIL_CDP_URL", raising=False)

    out = it.extrair_inteiro_teor("https://x/jurisprudencia/tj-mg/123")
    assert out["inteiro_teor"] == ""      # nao retornou o stale de 9000 chars
    assert out["url_inteiro_teor"] == ""  # nunca navegou
    assert out["citavel"] is False
