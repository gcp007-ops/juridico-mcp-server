# src/juridico_mcp/jusbrasil/vault.py
"""Escrita de notas 'julgado' (Jusbrasil) na vault ThinkBox. Server-side.

Conforme Template-Julgado canonico: required tribunal/classe/numero, gate
citavel: false + status: pendente_verificacao (jurisprudencia auto-extraida nasce
nao-citavel; so humano promove). A secao "Ementa Integral" preserva itens
numerados escapando o ponto ("1." -> "1\\.") para nao virar lista do Markdown.
Metadados de cabecalho (relator/orgao/data) vao no CORPO, nao no frontmatter,
mantendo o frontmatter alinhado ao schema (sem campos uncatalogued).
Nao invoca skills.
"""
from __future__ import annotations

import datetime
import re

from ..vault_common import (
    esc_yaml as _esc,
    exigir_required,
    escrever_nota,
    slug_ascii as _slug,
)

SUBPASTA = ("Conhecimento", "Fontes", "Julgados", "Jusbrasil")
_REQUIRED = ("tribunal", "classe", "numero")
_ITEM_NUM_RE = re.compile(r"(?m)^(\s*\d+)\.")


def slug_ascii(texto: str, max_len: int = 80) -> str:
    # Jusbrasil preserva o case (lower=False) e usa max_len=80.
    return _slug(texto, max_len, lower=False)


def _escapar_itens_numerados(texto: str) -> str:
    """Escapa "1." -> "1\\." no inicio de linha (gate anti-lista da ementa)."""
    return _ITEM_NUM_RE.sub(r"\1\\.", texto or "")


def montar_frontmatter(meta: dict, *, created: str = "") -> str:
    created = created or datetime.date.today().isoformat()
    linhas = ["---", "noteType: julgado"]
    for campo in ("tribunal", "classe", "numero"):
        linhas.append(f'{campo}: "{_esc(meta.get(campo, ""))}"')
    linhas.append('fonte: "Jusbrasil"')
    if meta.get("url_origem"):
        linhas.append(f'url_origem: "{_esc(meta["url_origem"])}"')
    if meta.get("url_inteiro_teor"):
        linhas.append(f'url_inteiro_teor: "{_esc(meta["url_inteiro_teor"])}"')
    linhas.append("citavel: false")
    linhas.append("status: pendente_verificacao")
    linhas.append(f'created: "{created}"')
    linhas += ["tags:", "- jurisprudencia", "---", ""]
    return "\n".join(linhas)


def montar_corpo(meta: dict) -> str:
    titulo = f'{meta.get("tribunal", "")} — {meta.get("classe", "")} {meta.get("numero", "")}'.strip()
    ementa = _escapar_itens_numerados((meta.get("ementa") or "").strip())
    teor = (meta.get("inteiro_teor") or "").strip()
    blocos = [f"# {titulo}", "", "## Ementa Integral", ""]
    blocos.append("> Auto-extraída do Jusbrasil — pendente de conferência humana (citavel: false).")
    blocos.append("")
    blocos.append(ementa if ementa else "[EMENTA INTEGRAL — extração automática não isolou a ementa; conferir no inteiro teor.]")
    blocos += [
        "",
        "---",
        "",
        "## Referência",
        "",
        "- Fonte: Jusbrasil",
        f'- URL: {meta.get("url_origem", "")}',
        f'- Inteiro teor: {meta.get("url_inteiro_teor", "")}',
        f'- Relator: {meta.get("relator", "")}',
        f'- Órgão julgador: {meta.get("orgao_julgador", "")}',
        f'- Data de julgamento: {meta.get("data_julgamento", "")}',
        "",
        "---",
        "",
        "## Inteiro Teor",
        "",
        teor if teor else "[inteiro teor não capturado]",
        "",
        "---",
        "",
        "## Conferência",
        "",
        "- [ ] A ementa acima foi copiada integralmente da fonte indicada.",
        "- [ ] O texto foi conferido contra a fonte ou o inteiro teor.",
        "- [ ] A seção da ementa não contém resumo, paráfrase ou texto gerado por IA.",
        "",
        "---",
        "",
        "## Pendências",
        "",
        "- [ ] Conferir a ementa integral contra a fonte (extração automática — citavel: false).",
    ]
    return "\n".join(blocos)


def escrever_julgado(meta: dict, *, base_path=None, created: str = "") -> str:
    exigir_required(meta, _REQUIRED)
    nome = slug_ascii(f'{meta["tribunal"]} - {meta["classe"]} {meta["numero"]}')
    conteudo = montar_frontmatter(meta, created=created) + montar_corpo(meta).strip() + "\n"
    return escrever_nota(SUBPASTA, nome, conteudo, base_path=base_path)
