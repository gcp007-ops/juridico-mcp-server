# src/juridico_mcp/rt/jurisprudencia.py
"""Jurisprudência RT Online via CDP. Parser próprio (subTitle/JRP). Server-only."""
from __future__ import annotations
import re
from typing import List
from lxml import html as lhtml
from . import session as _session

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


async def buscar(livre="", numero="", relator="", tribunais="", ano="",
                 data_de="", data_ate="", max_resultados=10) -> List[dict]:
    import asyncio
    campos = montar_campos(livre=livre, numero=numero, relator=relator, tribunais=tribunais,
                           ano=ano, data_de=data_de, data_ate=data_ate)
    html_text = await asyncio.to_thread(
        _session.run_search_form, ENTRY, campos, placeholders=PLACEHOLDERS
    )
    return parse_resultados(html_text)[:max_resultados]
