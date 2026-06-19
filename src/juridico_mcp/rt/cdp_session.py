# src/juridico_mcp/rt/cdp_session.py
"""Camada CDP da RT sobre cdp-scaffold. Server-only."""
from __future__ import annotations

import json
import os
import time
from typing import Optional
from urllib.parse import urlparse

import cdp_scaffold.cdp as _cdp

DEFAULT_TIMEOUT = 45.0


class RtSessionExpired(RuntimeError):
    """Sessao RT no Chrome dedicado expirou (escalavel via relogin)."""


def _parse_host_port(cdp_url: str) -> tuple[str, int]:
    """Extrai (host, port) de uma URL como http://127.0.0.1:9222."""
    parsed = urlparse(cdp_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9222
    return host, port


def cdp_url_or_raise(cdp_url: Optional[str] = None) -> str:
    url = cdp_url or os.environ.get("RT_CDP_URL")
    if not url:
        raise RuntimeError(
            "RT_CDP_URL nao configurada: a RT usa o Chrome dedicado via CDP (server-only). "
            "Defina RT_CDP_URL (ex.: http://127.0.0.1:9222) no host."
        )
    return url


class RtCdpSession:
    """Aba de fundo + websocket CDP via cdp-scaffold, com navigate/evaluate.

    Assinaturas cdp-scaffold reais (anotadas em Task 1):
      open_background_tab(host, port, timeout) -> (target_id, ws_url)
      connect(ws_url, timeout) -> websocket
      cdp_call(ws, method, params, msg_id, recv_timeout) -> dict (resposta completa CDP)
      cdp_eval(ws, expression, msg_id) -> valor desembrulhado (awaitPromise=True fixo)
      close_target(host, port, target_id) -> None
    """

    def __init__(self, cdp_url: str, timeout: float = DEFAULT_TIMEOUT):
        self.cdp_url = cdp_url.rstrip("/")
        self.timeout = timeout
        self._host, self._port = _parse_host_port(self.cdp_url)
        self._ws = None
        self._tid: Optional[str] = None
        self._seq = 0

    def __enter__(self) -> "RtCdpSession":
        self._tid, ws_url = _cdp.open_background_tab(
            self._host, self._port, self.timeout
        )
        self._ws = _cdp.connect(ws_url, self.timeout)
        self._cmd("Page.enable")
        return self

    def __exit__(self, *exc):
        try:
            if self._ws:
                self._ws.close()
        finally:
            if self._tid:
                _cdp.close_target(self._host, self._port, self._tid)

    def _cmd(self, method: str, params: dict | None = None) -> dict:
        """Envia comando CDP e retorna a resposta completa."""
        self._seq += 1
        return _cdp.cdp_call(self._ws, method, params or {}, self._seq)

    def evaluate(self, expr: str, await_promise: bool = False):
        """Avalia JS na pagina e retorna o valor desembrulhado.

        Se await_promise=True, usa cdp_eval (que ja fixa awaitPromise=True em cdp-scaffold).
        Se await_promise=False, usa Runtime.evaluate direto via _cmd.
        """
        if await_promise:
            self._seq += 1
            return _cdp.cdp_eval(self._ws, expr, self._seq)
        else:
            r = self._cmd(
                "Runtime.evaluate",
                {"expression": expr, "returnByValue": True, "awaitPromise": False},
            )
            return r.get("result", {}).get("result", {}).get("value")

    def navigate(self, url: str) -> None:
        self._cmd("Page.navigate", {"url": url})

    def wait_ready(self, extra: float = 1.5) -> bool:
        for _ in range(int(self.timeout * 2)):
            time.sleep(0.5)
            if self.evaluate("document.readyState") == "complete":
                time.sleep(extra)
                return True
        return False


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
