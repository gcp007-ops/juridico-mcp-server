"""Conversão do corpo HTML de um documento RT em Markdown (sem parser binário)."""
from __future__ import annotations

from lxml import html as lhtml
from markdownify import markdownify as _md


def _limpar_corpo(html: str) -> str:
    """Remove elementos com classe contendo 'relationship' via lxml."""
    tree = lhtml.fromstring(html or "")
    for el in tree.xpath('//*[contains(@class, "relationship")]'):
        el.getparent().remove(el)
    return lhtml.tostring(tree, encoding="unicode")


def html_para_md(html: str) -> str:
    md = _md(html or "", heading_style="ATX", strip=["script", "style"])
    linhas = [ln.rstrip() for ln in md.splitlines()]
    # colapsa linhas em branco múltiplas
    out, vazia = [], False
    for ln in linhas:
        if not ln:
            if not vazia:
                out.append("")
            vazia = True
        else:
            out.append(ln)
            vazia = False
    return "\n".join(out).strip()
