# src/juridico_mcp/rt/jurisprudencia.py
"""Jurisprudência RT Online via CDP. Parser próprio (subTitle/JRP). Server-only."""
from __future__ import annotations
import re
from typing import List
from lxml import html as lhtml
from . import session as _session
from .cdp_session import RtCdpSession, cdp_url_or_raise
from . import captura_md as _cap

BASE_HOST = "https://www.revistadostribunais.com.br"
ENTRY = f"{BASE_HOST}/maf/api/tocectory?tocguid=brjuris&stnew=true&oss=true&ndd=1"
PLACEHOLDERS = ("IWglobal1", "IWglobal2", "num", "jud", "tribunais", "revistas", "volume", "pageNum")

_JRP_RE = re.compile(r"JRP\\\d{4}\\\d+")
_DATA_JULG_RE = re.compile(r"Data de Julgamento\s+(\d{2}/\d{2}/\d{4})")
_NUM_RE = re.compile(r"^\s*([\d.\-/]+)\s*-")


def montar_campos(livre="", numero="", relator="", tribunais="", ano="",
                  data_de="", data_ate="") -> dict:
    campos: dict = {}
    if livre:
        campos["frt"] = livre
    if numero:
        campos["num"] = numero
    if relator:
        campos["jud"] = relator
    if tribunais:
        campos["tribunais"] = tribunais
    if ano:
        campos["dateType"] = "year"
        campos["ano"] = str(ano)
    elif data_de or data_ate:
        campos["dateType"] = "between"
        if data_de:
            campos["fromDate"] = data_de
        if data_ate:
            campos["toDate"] = data_ate
    return campos


def _txt(node) -> str:
    return " ".join("".join(node.itertext()).split()).strip()


def _parse_um(div):
    links = div.xpath('.//a[contains(@class,"documentLink")]')
    if not links:
        return None
    a = links[0]
    titulo = _txt(a)
    href = a.get("href", "")
    url = href if href.startswith("http") else f"{BASE_HOST}{href}"
    m_num = _NUM_RE.search(titulo)
    m_data = _DATA_JULG_RE.search(titulo)
    relator = ""
    partes = [p.strip() for p in titulo.split(" - ")]
    if len(partes) >= 2:
        relator = partes[1]
    subs = [_txt(p) for p in div.xpath('.//p[contains(@class,"subTitle")]')]
    tribunal = subs[0] if subs else ""
    veiculo, data_pub, jrp = "", "", ""
    if len(subs) >= 2:
        seg = [s.strip() for s in subs[1].split("|")]
        veiculo = seg[0] if seg else ""
        if len(seg) >= 2:
            data_pub = seg[1]
        m_jrp = _JRP_RE.search(subs[1])
        if m_jrp:
            jrp = m_jrp.group(0)
    return {
        "numero_processo": m_num.group(1) if m_num else "",
        "relator": relator,
        "data_julgamento": m_data.group(1) if m_data else "",
        "tribunal": tribunal,
        "veiculo": veiculo,
        "data_publicacao": data_pub,
        "jrp": jrp or None,
        "url": url,
    }


def parse_resultados(html_text: str) -> List[dict]:
    tree = lhtml.fromstring(html_text)
    out = []
    for div in tree.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " result ")]'):
        item = _parse_um(div)
        if item and item["url"]:
            out.append(item)
    return out


_HEADER_NUM = re.compile(r"([\d.\-/]{11,})")
_HEADER_DATA = re.compile(r"j\.\s*(\d{1,2}/\d{1,2}/\d{4})")
_HEADER_RELATOR = re.compile(r"julgado por\s+([^-]+?)\s*-")
_HEADER_TURMA = re.compile(r"-\s*([^-]*?(?:Turma|Câmara)[^-]*?)\s*-")
_HEADER_DEJT = re.compile(r"(?:DEJT|DJe|DJ)\s+(\d{1,2}/\d{1,2}/\d{4})")
_HEADER_AREA = re.compile(r"Área do Direito:\s*([^-\n]+)")
_DOCCONTENT_JS = "(()=>{const e=document.querySelector('#docContent');return e?e.innerHTML:'__NO_DOC__';})()"
_TRIBUNAL_JS = (
    "(()=>{const hs=[...document.querySelectorAll('h1.hTitle')]"
    ".map(e=>(e.textContent||'').trim()).filter(t=>t);"
    "return hs.length?hs[0]:'';})()"
)


def _meta_do_corpo(html_corpo: str) -> dict:
    texto = _cap.html_para_md(_cap._limpar_corpo(html_corpo))
    primeira = next((l for l in texto.splitlines() if l.strip()), "")
    m_num = _HEADER_NUM.search(primeira)
    numero = m_num.group(1) if m_num else ""
    # classe = trecho entre o tribunal-abrev e o número
    classe = ""
    if numero:
        antes = primeira.split(numero)[0]
        partes = antes.split(" - ")
        if len(partes) >= 2:
            classe = partes[-1].strip(" -")
    m_data = _HEADER_DATA.search(primeira)
    m_rel = _HEADER_RELATOR.search(primeira)
    m_turma = _HEADER_TURMA.search(primeira)
    m_area = _HEADER_AREA.search(primeira)
    m_dejt = _HEADER_DEJT.search(primeira)
    return {
        "numero": numero,
        "classe": classe,
        "relator": m_rel.group(1).strip() if m_rel else "",
        "data_julgamento": m_data.group(1) if m_data else "",
        "data_publicacao": m_dejt.group(1) if m_dejt else "",
        "orgao_julgador": m_turma.group(1).strip() if m_turma else "",
        "assunto": m_area.group(1).strip() if m_area else "",
    }


def extrair_documento(doc_url: str, *, cdp_url=None, timeout: float = 45.0) -> dict:
    url = cdp_url_or_raise(cdp_url)
    with RtCdpSession(url, timeout=timeout) as s:
        s.navigate(doc_url)
        s.wait_ready(extra=2.0)
        corpo = s.evaluate(_DOCCONTENT_JS)
        tribunal = s.evaluate(_TRIBUNAL_JS) or ""
    if corpo == "__NO_DOC__" or not isinstance(corpo, str):
        raise RuntimeError("RT: #docContent ausente (layout mudou ou doc sem corpo).")
    import urllib.parse as _u
    qs = _u.parse_qs(_u.urlparse(doc_url).query)
    corpo_limpo = _cap._limpar_corpo(corpo)
    meta = _meta_do_corpo(corpo)
    return {
        "url": doc_url,
        "tribunal": tribunal,
        "jrp": (qs.get("jrp") or [None])[0],
        "html_corpo": corpo_limpo,
        **meta,
    }


async def buscar(livre="", numero="", relator="", tribunais="", ano="",
                 data_de="", data_ate="", max_resultados=10) -> List[dict]:
    import asyncio
    campos = montar_campos(livre=livre, numero=numero, relator=relator, tribunais=tribunais,
                           ano=ano, data_de=data_de, data_ate=data_ate)
    html_text = await asyncio.to_thread(
        _session.run_search_form, ENTRY, campos, placeholders=PLACEHOLDERS
    )
    return parse_resultados(html_text)[:max_resultados]
