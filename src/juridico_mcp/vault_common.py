# src/juridico_mcp/vault_common.py
"""Helpers compartilhados de escrita de notas 'julgado' na vault. Server-side.

Extraido da duplicacao entre rt/vault.py e jusbrasil/vault.py. As diferencas de
politica (max_len/lower do slug, status/citavel, subpasta, builder de corpo)
ficam em cada modulo; aqui mora so o esqueleto neutro.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Sequence


def slug_ascii(texto: str, max_len: int = 60, *, lower: bool = True) -> str:
    """Slug ASCII para filename. lower=True (RT) ou False (Jusbrasil); max_len por fonte."""
    sem = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    sem = re.sub(r"[^a-zA-Z0-9]+", "-", sem).strip("-")
    if lower:
        sem = sem.lower()
    return (sem[:max_len].rstrip("-")) or "julgado"


def esc_yaml(v) -> str:
    """Escapa \\ e \" para valores escalares de frontmatter YAML entre aspas."""
    return str(v).replace("\\", "\\\\").replace('"', '\\"')


def exigir_required(meta: dict, required: Sequence[str]) -> None:
    """Levanta ValueError se algum campo required estiver ausente/vazio."""
    faltando = [c for c in required if not meta.get(c)]
    if faltando:
        raise ValueError(f"julgado: campos required ausentes: {', '.join(faltando)}")


def resolver_base(base_path=None) -> str:
    """Resolve a base da vault: arg explicito > THINKBOX_VAULT_PATH; senao levanta."""
    base = base_path or os.environ.get("THINKBOX_VAULT_PATH", "")
    if not base or not base.strip():
        raise ValueError(
            "THINKBOX_VAULT_PATH nao configurado: defina o caminho da vault "
            "(server-side) ou passe base_path"
        )
    return base


def escrever_nota(subpasta: Sequence[str], nome_arquivo: str, conteudo: str,
                  *, base_path=None) -> str:
    """Grava {conteudo} em {base}/{*subpasta}/{nome_arquivo}.md (cria a pasta)."""
    pasta = os.path.join(resolver_base(base_path), *subpasta)
    os.makedirs(pasta, exist_ok=True)
    path = os.path.join(pasta, f"{nome_arquivo}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(conteudo)
    return path
