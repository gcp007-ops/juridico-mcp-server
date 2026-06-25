# src/juridico_mcp/jusbrasil/inteiro_teor.py
"""Inteiro teor de julgado do Jusbrasil via DOM da sessao logada. Server-only.

Recon E1/E4: o seletor de metadados [class*=detailsText] sofreu drift (null), mas
os dados estao no texto renderizado do <main> (numero/orgao/relator/data) — por
isso parseamos por regex sobre o texto, nao por classe hash-fragil. O inteiro teor
e obtido clicando a aba "Inteiro Teor" (a URL vira /inteiro-teor-{teorId}, teorId
NAO derivavel do docId) e lendo o texto renderizado do container (~27k chars).

Gate de seguranca: jurisprudencia auto-extraida nasce citavel=False (so humano
promove). Nunca marcar True aqui.
"""
from __future__ import annotations

import re
import time
from typing import Optional

from .session import JusbrasilCdpSession, cdp_url_or_raise, DEFAULT_TIMEOUT, _throttle
from . import jurisprudencia as _jur

# Numero CNJ (NNNNNNN-DD.AAAA.J.TR.OOOO).
_CNJ_RE = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}")
_RELATOR_RE = re.compile(r"Relator(?:\(a\))?\s*·\s*(.+)")
_JULGADO_RE = re.compile(r"Julgado em\s*(\d{2}/\d{2}/\d{4})")
_ORGAO_RE = re.compile(r"·\s*(.+)")
# classe na linha de titulo: "TJ-MG - Apelação Cível: AC ..."
_CLASSE_RE = re.compile(r"[A-Z]{2,4}-[A-Z]{2}\s*-\s*([^:·\n]+?)\s*:")

# Abas/labels de navegacao que prefixam o texto do container de inteiro teor.
_TAB_LABELS = {"resumo", "inteiro teor", "fatos", "documentos", "jurisprudência semelhante"}

# Metadados: numero (lawsuitLabel) + bloco de cabecalho (texto do topo do main).
META_JS = r"""
(() => {
  const lbl = document.querySelector('[class*="lawsuitLabel"]');
  const main = document.querySelector('main');
  return {
    lawsuitLabel: lbl ? (lbl.innerText || '').trim() : '',
    topText: main ? (main.innerText || '').trim().slice(0, 1200) : '',
  };
})()
"""

# Clica a aba "Inteiro Teor" (um <a>/<button>/[role=tab] com esse texto).
CLICK_JS = r"""
(() => {
  const cand = [...document.querySelectorAll('[class*="tabs-trigger"], [role="tab"], button, a')]
    .find(e => /inteiro teor/i.test((e.innerText || '')));
  if (!cand) return '__NO_TAB__';
  cand.click();
  return 'clicked:' + cand.tagName;
})()
"""

# Le a URL atual + texto do container de inteiro teor.
AFTER_JS = r"""
(() => {
  const main = document.querySelector('main');
  const cont = document.querySelector('[class*="juris-document_tabs"]') || main;
  const txt = cont ? (cont.innerText || '').trim() : '';
  return { url: location.href, text: txt };
})()
"""


def _parse_metadata(lawsuit_label: str, top_text: str) -> dict:
    fonte_num = lawsuit_label or top_text or ""
    m_cnj = _CNJ_RE.search(fonte_num)
    m_rel = _RELATOR_RE.search(top_text or "")
    m_julg = _JULGADO_RE.search(top_text or "")
    m_classe = _CLASSE_RE.search(top_text or "")
    # orgao: primeira linha com "·" que nao seja a do Relator
    orgao = ""
    for linha in (top_text or "").split("\n"):
        if "·" in linha and not linha.strip().startswith("Relator"):
            mo = _ORGAO_RE.search(linha)
            if mo:
                orgao = mo.group(1).strip()
                break
    return {
        "numero": m_cnj.group(0) if m_cnj else "",
        "classe": m_classe.group(1).strip() if m_classe else "",
        "relator": m_rel.group(1).strip() if m_rel else "",
        "orgao_julgador": orgao,
        "data_julgamento": m_julg.group(1) if m_julg else "",
    }


def _limpar_inteiro_teor(raw: str) -> str:
    """Remove o prefixo de labels de aba (Resumo/Inteiro Teor/Fatos/...) e espacos."""
    linhas = (raw or "").split("\n")
    i = 0
    while i < len(linhas) and (
        linhas[i].strip() == "" or linhas[i].strip().lower() in _TAB_LABELS
    ):
        i += 1
    return "\n".join(linhas[i:]).strip()


def _extrair_ementa(inteiro_teor: str) -> str:
    """Best-effort: bloco iniciado por EMENTA ate o proximo marco (ACORDAO/RELATORIO/VOTO)."""
    m = re.search(
        r"EMENTA:?\s*(.+?)(?:\n\s*\n|AC[ÓO]RD[ÃA]O|RELAT[ÓO]RIO|\bVOTO\b)",
        inteiro_teor or "",
        re.IGNORECASE | re.DOTALL,
    )
    return m.group(1).strip() if m else ""


def extrair_inteiro_teor(doc_url: str, *, cdp_url: Optional[str] = None,
                         timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Abre o julgado, le metadados, clica a aba Inteiro Teor e extrai o texto.

    Retorna payload com gate citavel=False (jurisprudencia auto-extraida).
    """
    url = cdp_url_or_raise(cdp_url)
    slug = _jur._slug_from_href(doc_url)
    _throttle()
    with JusbrasilCdpSession(url, timeout=timeout) as s:
        s.navigate(doc_url)
        s.wait_ready(extra=2.0)
        meta_raw = s.evaluate(META_JS)
        s.evaluate(CLICK_JS)
        # Aba carrega via SPA (readyState ja 'complete'); poll por conteudo.
        after = {}
        for _ in range(12):
            time.sleep(0.5)
            after = s.evaluate(AFTER_JS) or {}
            if isinstance(after, dict) and len(after.get("text", "")) > 2000:
                break
    if not isinstance(meta_raw, dict):
        meta_raw = {}
    meta = _parse_metadata(meta_raw.get("lawsuitLabel", ""), meta_raw.get("topText", ""))
    teor = _limpar_inteiro_teor(after.get("text", "") if isinstance(after, dict) else "")
    return {
        "fonte": "jusbrasil",
        "url_origem": doc_url,
        "url_inteiro_teor": after.get("url", "") if isinstance(after, dict) else "",
        "tribunal": _jur.tribunal_do_slug(slug),
        "slug": slug,
        "numero": meta["numero"],
        "classe": meta["classe"],
        "relator": meta["relator"],
        "orgao_julgador": meta["orgao_julgador"],
        "data_julgamento": meta["data_julgamento"],
        "ementa": _extrair_ementa(teor),
        "inteiro_teor": teor,
        "citavel": False,
    }
