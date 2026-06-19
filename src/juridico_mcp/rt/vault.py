# src/juridico_mcp/rt/vault.py
"""Escrita de notas 'julgado' na vault ThinkBox. Server-side.

Grava nota schema-conforme (noteType julgado, required tribunal/classe/numero) com
frontmatter YAML válido (escalares escapados). Não invoca skills."""
from __future__ import annotations
import os, re, unicodedata

SUBPASTA = ("Conhecimento", "Fontes", "Julgados", "RT")
_REQUIRED = ("tribunal", "classe", "numero")


def slug_ascii(texto: str, max_len: int = 60) -> str:
    sem = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    sem = re.sub(r"[^a-zA-Z0-9]+", "-", sem).strip("-").lower()
    return (sem[:max_len].rstrip("-")) or "julgado"


def _esc(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"')


def montar_frontmatter(meta: dict, pdf_local: str = "") -> str:
    linhas = ["---", "noteType: julgado", 'fonte: "RT Online"', "status: ativo"]
    for chave, campo in (("tribunal", "tribunal"), ("classe", "classe"), ("numero", "numero"),
                         ("relator", "relator"), ("orgao_julgador", "orgao_julgador"),
                         ("assunto", "assunto")):
        if meta.get(campo):
            linhas.append(f'{chave}: "{_esc(meta[campo])}"')
    if meta.get("data_julgamento"): linhas.append(f'data_julgamento: "{_esc(meta["data_julgamento"])}"')
    if meta.get("data_publicacao"): linhas.append(f'data_publicacao: "{_esc(meta["data_publicacao"])}"')
    if meta.get("jrp"): linhas.append(f'codigo: "{_esc(meta["jrp"])}"')
    if meta.get("url"): linhas.append(f'url: "{_esc(meta["url"])}"')
    if pdf_local: linhas.append(f'pdf_local: "{_esc(pdf_local)}"')
    linhas += ["temas: []", "---", ""]
    return "\n".join(linhas)


def escrever_julgado(meta: dict, corpo_md: str, *, base_path=None, pdf_local: str = "") -> str:
    faltando = [c for c in _REQUIRED if not meta.get(c)]
    if faltando:
        raise ValueError(f"julgado: campos required ausentes: {', '.join(faltando)}")
    base = base_path or os.environ.get("THINKBOX_VAULT_PATH", "")
    pasta = os.path.join(base, *SUBPASTA)
    os.makedirs(pasta, exist_ok=True)
    nome = slug_ascii(meta["numero"])
    path = os.path.join(pasta, f"{nome}.md")
    conteudo = montar_frontmatter(meta, pdf_local=pdf_local) + corpo_md.strip() + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(conteudo)
    return path
