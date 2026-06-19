# src/juridico_mcp/rt/session.py
"""Submissão genérica de #searchForm da RT via CDP, com relogin reativo. Server-only."""
from __future__ import annotations
from typing import Optional
from .cdp_session import RtCdpSession, RtSessionExpired, build_fetch_js, cdp_url_or_raise, DEFAULT_TIMEOUT
from cdp_scaffold.cdp import CdpError


def _fetch_html(entry_url, fields, placeholders, cdp_url, timeout):
    with RtCdpSession(cdp_url, timeout=timeout) as s:
        s.navigate(entry_url)
        s.wait_ready()
        html = s.evaluate(build_fetch_js(fields, placeholders), await_promise=True)
    if html == "__NO_FORM__":
        raise RtSessionExpired("CDP RT: #searchForm ausente (sessão expirada ou layout).")
    if not isinstance(html, str):
        raise RtSessionExpired("CDP RT: fetch in-page não retornou HTML (sessão expirada?).")
    return html


def run_search_form(entry_url, fields, *, placeholders, cdp_url: Optional[str] = None,
                    timeout: float = DEFAULT_TIMEOUT) -> str:
    url = cdp_url_or_raise(cdp_url)
    try:
        return _fetch_html(entry_url, fields, placeholders, url, timeout)
    except (RtSessionExpired, CdpError):
        from . import auth
        auth.login_rt_via_cdp(url)
        try:
            return _fetch_html(entry_url, fields, placeholders, url, timeout)
        except (RtSessionExpired, CdpError) as exc:
            raise RuntimeError(f"RT: sessão segue inválida após relogin OnePass ({exc}).") from exc
