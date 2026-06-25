# src/juridico_mcp/rt/cdp_session.py
"""Camada CDP da RT sobre o nucleo neutro cdp_common. Server-only.

A plumbing generica (abrir aba, websocket, evaluate/navigate/wait_ready) vive em
juridico_mcp.cdp_common.CdpSession. Aqui ficam apenas os pontos especificos da RT:
- env var RT_CDP_URL (via cdp_url_or_raise);
- o fetch in-page do #searchForm (build_fetch_js).
"""
from __future__ import annotations

import json
from typing import Optional

from ..cdp_common import (
    DEFAULT_TIMEOUT,
    CdpSession,
    CdpSessionExpired,
    _parse_host_port,  # re-exportado para back-compat
)
from ..cdp_common import cdp_url_or_raise as _cdp_url_or_raise

# Back-compat: nome historico da excecao usado em session.py/auth.py/testes.
RtSessionExpired = CdpSessionExpired


class RtCdpSession(CdpSession):
    """Sessao CDP da RT. Identica ao nucleo neutro (sem especializacao extra)."""


def cdp_url_or_raise(cdp_url: Optional[str] = None) -> str:
    """Resolve a URL do CDP da RT (RT_CDP_URL obrigatoria)."""
    return _cdp_url_or_raise(cdp_url, env_var="RT_CDP_URL", fonte="RT")


def build_fetch_js(fields: dict, placeholders: tuple) -> str:
    """JS in-page: seta cada par de fields, zera placeholders, POST do #searchForm."""
    sets = "".join(
        f"fd.set({json.dumps(k)},{json.dumps(str(v))});" for k, v in fields.items()
    )
    ph = json.dumps(list(placeholders))
    return (
        "(async()=>{const f=document.querySelector('#searchForm');"
        "if(!f)return '__NO_FORM__';const fd=new FormData(f);"
        f"{ph}.forEach(k=>fd.set(k,''));{sets}"
        "const body=new URLSearchParams(fd).toString();"
        "const r=await fetch(f.action,{method:'POST',"
        "headers:{'Content-Type':'application/x-www-form-urlencoded'},body,credentials:'include'});"
        "return await r.text();})()"
    )
