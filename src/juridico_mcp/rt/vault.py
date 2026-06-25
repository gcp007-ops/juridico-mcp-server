# src/juridico_mcp/rt/vault.py
"""Escrita de notas 'julgado' na vault ThinkBox. Server-side.

Grava nota schema-conforme (noteType julgado, required tribunal/classe/numero) com
frontmatter YAML válido (escalares escapados). Não invoca skills."""
from __future__ import annotations
from ..vault_common import esc_yaml as _esc, exigir_required, escrever_nota, slug_ascii

SUBPASTA = ("Conhecimento", "Fontes", "Julgados", "RT")
_REQUIRED = ("tribunal", "classe", "numero")
# slug_ascii: RT usa o default (max_len=60, lower=True) de vault_common.


def montar_frontmatter(meta: dict, pdf_local: str = "") -> str:
    linhas = ["---", "noteType: julgado", 'fonte: "RT Online"', "status: ativo"]
    for campo in ("tribunal", "classe", "numero", "relator", "orgao_julgador", "assunto"):
        if meta.get(campo):
            linhas.append(f'{campo}: "{_esc(meta[campo])}"')
    if meta.get("data_julgamento"): linhas.append(f'data_julgamento: "{_esc(meta["data_julgamento"])}"')
    if meta.get("data_publicacao"): linhas.append(f'data_publicacao: "{_esc(meta["data_publicacao"])}"')
    if meta.get("jrp"): linhas.append(f'codigo: "{_esc(meta["jrp"])}"')
    if meta.get("url"): linhas.append(f'url: "{_esc(meta["url"])}"')
    if pdf_local: linhas.append(f'pdf_local: "{_esc(pdf_local)}"')
    linhas += ["temas: []", "---", ""]
    return "\n".join(linhas)


def escrever_julgado(meta: dict, corpo_md: str, *, base_path=None, pdf_local: str = "") -> str:
    exigir_required(meta, _REQUIRED)
    conteudo = montar_frontmatter(meta, pdf_local=pdf_local) + corpo_md.strip() + "\n"
    return escrever_nota(SUBPASTA, slug_ascii(meta["numero"]), conteudo, base_path=base_path)
