# src/juridico_mcp/jusbrasil/session.py
"""Sessao CDP do Jusbrasil sobre o nucleo neutro cdp_common. Server-only.

O Jusbrasil agregado e dirigido por uma aba Chrome dedicada logada (mesmo :9222
do RT, cookies por-origem coexistem). Diferente da RT, o Jusbrasil NAO usa o
truque de POST do #searchForm: navega para a URL e le o DOM renderizado (React).
Por isso a primitiva aqui e abrir_dom (navigate -> wait_ready -> evaluate), que
E3 (busca) e E4 (inteiro teor) reutilizam.
"""
from __future__ import annotations

from typing import Optional

from ..cdp_common import DEFAULT_TIMEOUT, CdpSession
from ..cdp_common import cdp_url_or_raise as _cdp_url_or_raise

BASE_HOST = "https://www.jusbrasil.com.br"

# Recon E1: a aba logada do :9222 dirige o Jusbrasil sem Cloudflare/paywall.
# Diferente da RT, o CDP url e opcional (default :9222); JUSBRASIL_CDP_URL sobrescreve.
DEFAULT_CDP_URL = "http://127.0.0.1:9222"


class JusbrasilCdpSession(CdpSession):
    """Sessao CDP do Jusbrasil. Identica ao nucleo neutro (sem especializacao extra)."""


def cdp_url_or_raise(cdp_url: Optional[str] = None) -> str:
    """Resolve a URL do CDP do Jusbrasil (arg > JUSBRASIL_CDP_URL > default :9222)."""
    return _cdp_url_or_raise(
        cdp_url, env_var="JUSBRASIL_CDP_URL", default=DEFAULT_CDP_URL, fonte="Jusbrasil"
    )


def abrir_dom(
    url: str,
    js: str,
    *,
    await_promise: bool = False,
    cdp_url: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
    extra_wait: float = 1.5,
):
    """Navega para url na aba logada, aguarda o DOM e avalia js, retornando o valor.

    Primitiva compartilhada por E3/E4. Resolve o CDP url (default :9222), abre uma
    aba de fundo, navega, espera readyState=complete e avalia o JS.
    """
    resolved = cdp_url_or_raise(cdp_url)
    with JusbrasilCdpSession(resolved, timeout=timeout) as s:
        s.navigate(url)
        s.wait_ready(extra=extra_wait)
        return s.evaluate(js, await_promise=await_promise)
