# src/juridico_mcp/jusbrasil/jurisprudencia.py
"""Busca de jurisprudencia agregada do Jusbrasil via DOM da sessao logada. Server-only.

O Jusbrasil renderiza a busca em React; extraimos os resultados do DOM ja
renderizado (in-page JS), nao via HTML cru nem GraphQL (recon E1 dispensou o
GraphQL). Seletores parciais ([class*=...]) porque as classes sao hash-sufixadas.
"""
from __future__ import annotations

import re
import unicodedata
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


# Filtros -> parametros de URL Next.js confirmados ao vivo (pagina de resultados
# /jurisprudencia/busca; na landing /jurisprudencia/ os filtros so existem apos
# uma busca). Recon Claude in Chrome 2026-06-24 confirmou que tribunal/tipo SIM
# refletem como param GET na pagina de resultados (refuta a hipotese E1 de que
# eram multi-select sem param). Ver recon na INI JusbrasilMCP.
#   ordenacao: o=data (mais recente); relevancia = default (sem param).
#   periodo:   l=<N>dias (recorte por data); qualquer = default (sem param).
#   tribunal:  tribunal=<sigla minuscula> (familia: stj, tj, trf, trt...).
#   tipo:      jurisType=<token> (acordao, sumula confirmados).
_ORDEM_PARAM = {"recente": "data", "relevancia": ""}
_PERIODO_L = {
    "qualquer": "", "mes": "30dias", "ano": "365dias",
    "2anos": "730dias", "3anos": "1095dias", "5anos": "1825dias",
}
_TOKEN_DIAS_RE = re.compile(r"^\d+dias$")

# Siglas-familia aceitas pelo filtro de tribunal, observadas no menu "Tribunal"
# da pagina de resultados. A URL usa a sigla minuscula (tribunal=stj). O filtro e
# por familia (ex. STJ agrupa 13 orgaos; TJ agrupa todos os TJs estaduais), nao
# pelo slug granular (tj-ba) usado nos resultados.
_TRIBUNAL_FILTRO = frozenset({
    "STF", "STJ", "TST", "TSE", "STM", "TCU", "TNU", "TRU",
    "CNJ", "CARF", "TJ", "TRF", "TRT", "TRE", "TJM", "TCE",
})

# Tipo de julgado -> token jurisType. Todas as 6 opcoes do menu confirmadas ao
# vivo (recon Claude in Chrome 2026-06-24): a forma e sempre o singular minusculo
# sem acento do tipo. "todos" = default (sem param). Token alfabetico fora do mapa
# ainda passa como token cru (valvula de seguranca, igual ao passthrough Ndias).
_JURISTYPE_TOKEN = {
    "todos": "", "qualquer": "",
    "acordao": "acordao", "acordaos": "acordao",
    "sumula": "sumula", "sumulas": "sumula",
    "decisao": "decisao", "decisoes": "decisao",
    "sentenca": "sentenca", "sentencas": "sentenca",
    "despacho": "despacho", "despachos": "despacho",
}
_JURISTYPE_CRU_RE = re.compile(r"^[a-z]+$")


def _sem_acento(s: str) -> str:
    """Normaliza para minuscula ASCII (remove acentos), preservando o resto."""
    s = (s or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _periodo_l(periodo: str) -> str:
    """Resolve o token l= a partir de um apelido amigavel ou de um token cru Ndias."""
    p = (periodo or "qualquer").lower()
    if p in _PERIODO_L:
        return _PERIODO_L[p]
    return p if _TOKEN_DIAS_RE.match(p) else ""


def _tribunal_param(tribunal: str) -> str:
    """Resolve o token tribunal= a partir de uma sigla-familia. Vazio/qualquer =
    sem filtro. Sigla fora do conjunto observado levanta ValueError (nao busca
    sem filtro silenciosamente)."""
    t = (tribunal or "").strip().upper()
    if not t or t in ("QUALQUER", "TODOS"):
        return ""
    if t in _TRIBUNAL_FILTRO:
        return t.lower()
    raise ValueError(
        f"tribunal desconhecido: {tribunal!r}. Use uma sigla-familia: "
        + ", ".join(sorted(_TRIBUNAL_FILTRO))
    )


def _juris_type(tipo: str) -> str:
    """Resolve o token jurisType= a partir de um apelido amigavel (acordao/sumula)
    ou token cru. Vazio/todos = sem filtro."""
    t = _sem_acento(tipo or "todos")
    if t in _JURISTYPE_TOKEN:
        return _JURISTYPE_TOKEN[t]
    return t if _JURISTYPE_CRU_RE.match(t) else ""


def _montar_url(termo: str, pagina: int, ordenar: str = "relevancia",
                periodo: str = "qualquer", tribunal: str = "",
                tipo: str = "todos") -> str:
    url = f"{BASE_HOST}/jurisprudencia/busca?q={quote(termo)}"
    if pagina and pagina > 1:
        url += f"&p={pagina}"
    ordem = _ORDEM_PARAM.get((ordenar or "relevancia").lower(), "")
    if ordem:
        url += f"&o={ordem}"
    el = _periodo_l(periodo)
    if el:
        url += f"&l={el}"
    trib = _tribunal_param(tribunal)
    if trib:
        url += f"&tribunal={trib}"
    jtype = _juris_type(tipo)
    if jtype:
        url += f"&jurisType={jtype}"
    return url


def buscar(termo: str, *, pagina: int = 1, max_resultados: int = 10,
           ordenar: str = "relevancia", periodo: str = "qualquer",
           tribunal: str = "", tipo: str = "todos", cdp_url=None) -> List[dict]:
    """Busca jurisprudencia agregada no Jusbrasil (sessao logada via CDP).

    ordenar: "relevancia" (default) ou "recente" (mais novos primeiro).
    periodo: recorte por data — "qualquer" (default), "mes", "ano", "2anos",
             "3anos", "5anos" (ou token cru tipo "365dias").
    tribunal: sigla-familia para filtrar (ex. "STJ", "TJ", "TRF"); "" = todos.
    tipo: tipo de julgado — "todos" (default), "acordao", "sumula", "decisao",
          "sentenca", "despacho" (ou token cru).
    """
    url = _montar_url(termo, pagina, ordenar, periodo, tribunal, tipo)
    records = _session.abrir_dom(url, EXTRACT_JS, cdp_url=cdp_url)
    if not isinstance(records, list):
        return []
    return normalizar(records)[:max_resultados]
