# src/juridico_mcp/jusbrasil/jurisprudencia.py
"""Busca de jurisprudencia agregada do Jusbrasil via DOM da sessao logada. Server-only.

O Jusbrasil renderiza a busca em React; extraimos os resultados do DOM ja
renderizado (in-page JS), nao via HTML cru nem GraphQL (recon E1 dispensou o
GraphQL). Seletores parciais ([class*=...]) porque as classes sao hash-sufixadas.
"""
from __future__ import annotations

import re
from typing import List
from urllib.parse import quote, urlparse

from . import session as _session

BASE_HOST = _session.BASE_HOST

# Mapa slug->sigla canonica (porte de CODE-ExtensaoJusBrasil). Slug ausente:
# fallback para sigla derivada do slug (sem inventar tribunal).
TRIBUNAL_POR_SLUG = {
    "stf": "STF", "stj": "STJ", "tst": "TST", "tse": "TSE", "stm": "STM",
    "trf-1": "TRF1", "trf-2": "TRF2", "trf-3": "TRF3", "trf-4": "TRF4",
    "trf-5": "TRF5", "trf-6": "TRF6",
    "tj-ac": "TJAC", "tj-al": "TJAL", "tj-am": "TJAM", "tj-ap": "TJAP",
    "tj-ba": "TJBA", "tj-ce": "TJCE", "tj-df": "TJDFT", "tj-es": "TJES",
    "tj-go": "TJGO", "tj-ma": "TJMA", "tj-mg": "TJMG", "tj-ms": "TJMS",
    "tj-mt": "TJMT", "tj-pa": "TJPA", "tj-pb": "TJPB", "tj-pe": "TJPE",
    "tj-pi": "TJPI", "tj-pr": "TJPR", "tj-rj": "TJRJ", "tj-rn": "TJRN",
    "tj-ro": "TJRO", "tj-rr": "TJRR", "tj-rs": "TJRS", "tj-sc": "TJSC",
    "tj-se": "TJSE", "tj-sp": "TJSP", "tj-to": "TJTO",
}

# Extrator in-page: cada resultado e um <article> dentro de <main>.
EXTRACT_JS = r"""
(() => {
  const arts = [...document.querySelectorAll('main article')];
  return arts.map(a => {
    const link = a.querySelector('h2 a') || a.querySelector('a[href*="/jurisprudencia/"]');
    const cap = a.querySelector('[class*="caption"]');
    const bq = a.querySelector('blockquote');
    return {
      titulo: link ? (link.innerText || '').trim() : '',
      href: link ? link.getAttribute('href') : '',
      caption: cap ? (cap.innerText || '').trim() : '',
      ementa: bq ? (bq.innerText || '').trim() : '',
    };
  }).filter(r => r.href);
})()
"""

_HREF_RE = re.compile(r"/jurisprudencia/([^/?#]+)/(\d+)")
_DATA_RE = re.compile(r"(\d{2}/\d{2}/\d{4})")
_TIPO_RE = re.compile(r"Jurisprud[eê]ncia\s*(.*?)\s*publicado em", re.IGNORECASE)
_EMENTA_PREFIXO = re.compile(r"^\s*Ementa:\s*", re.IGNORECASE)


def _doc_id_from_href(href: str) -> str:
    m = _HREF_RE.search(href or "")
    return m.group(2) if m else ""


def _slug_from_href(href: str) -> str:
    m = _HREF_RE.search(href or "")
    return m.group(1) if m else ""


def tribunal_do_slug(slug: str) -> str:
    if not slug:
        return ""
    return TRIBUNAL_POR_SLUG.get(slug, slug.upper())


def _parse_caption(caption: str) -> dict:
    caption = caption or ""
    m_data = _DATA_RE.search(caption)
    m_tipo = _TIPO_RE.search(caption)
    return {
        "tipo": m_tipo.group(1).strip() if m_tipo else "",
        "data_publicacao": m_data.group(1) if m_data else "",
    }


def _ementa_limpa(ementa: str) -> str:
    """Remove o rotulo redundante 'Ementa:' que o blockquote ja traz no inicio."""
    return _EMENTA_PREFIXO.sub("", ementa or "", count=1).strip()


def normalizar(records: List[dict]) -> List[dict]:
    out = []
    for r in records or []:
        href = r.get("href", "") or ""
        if not href:
            continue
        slug = _slug_from_href(href)
        cap = _parse_caption(r.get("caption", ""))
        out.append({
            "titulo": (r.get("titulo", "") or "").strip(),
            "url": href,
            "doc_id": _doc_id_from_href(href),
            "slug": slug,
            "tribunal": tribunal_do_slug(slug),
            "tipo": cap["tipo"],
            "data_publicacao": cap["data_publicacao"],
            "ementa": _ementa_limpa(r.get("ementa", "")),
        })
    return out


# Ordenacao -> parametro de URL confirmado ao vivo (o=data == mais recente).
# relevancia e o default do Jusbrasil (sem parametro).
_ORDEM_PARAM = {"recente": "o=data", "relevancia": ""}


def _montar_url(termo: str, pagina: int, ordenar: str = "relevancia") -> str:
    url = f"{BASE_HOST}/jurisprudencia/busca?q={quote(termo)}"
    if pagina and pagina > 1:
        url += f"&p={pagina}"
    ordem = _ORDEM_PARAM.get((ordenar or "relevancia").lower(), "")
    if ordem:
        url += f"&{ordem}"
    return url


def buscar(termo: str, *, pagina: int = 1, max_resultados: int = 10,
           ordenar: str = "relevancia", cdp_url=None) -> List[dict]:
    """Busca jurisprudencia agregada no Jusbrasil (sessao logada via CDP).

    ordenar: "relevancia" (default) ou "recente" (mais novos primeiro).
    """
    url = _montar_url(termo, pagina, ordenar)
    records = _session.abrir_dom(url, EXTRACT_JS, cdp_url=cdp_url)
    if not isinstance(records, list):
        return []
    return normalizar(records)[:max_resultados]
