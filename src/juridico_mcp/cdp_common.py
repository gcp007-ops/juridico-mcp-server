# src/juridico_mcp/cdp_common.py
"""Camada CDP neutra (fonte-agnostica) sobre cdp-scaffold. Server-only.

Plumbing reutilizavel entre fontes que dependem de uma sessao Chrome dedicada
logada via CDP (RT Online, Jusbrasil, ...). Cada fonte adiciona apenas o que e
especifico dela (env var do CDP, parsers, fetch in-page) por cima desta base.
"""
from __future__ import annotations

import os
import time
from typing import Optional
from urllib.parse import urlparse

import cdp_scaffold.cdp as _cdp

DEFAULT_TIMEOUT = 45.0


class CdpSessionExpired(RuntimeError):
    """Sessao no Chrome dedicado expirou (escalavel via relogin da fonte)."""


def _parse_host_port(cdp_url: str) -> tuple[str, int]:
    """Extrai (host, port) de uma URL como http://127.0.0.1:9222."""
    parsed = urlparse(cdp_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9222
    return host, port


def cdp_url_or_raise(
    cdp_url: Optional[str] = None,
    *,
    env_var: str,
    default: Optional[str] = None,
    fonte: str = "",
) -> str:
    """Resolve a URL do CDP: arg explicito > env_var > default; senao levanta.

    Args:
        cdp_url: URL passada explicitamente (tem precedencia).
        env_var: Nome da variavel de ambiente consultada quando cdp_url e None.
        default: Fallback quando nem arg nem env existem (None => obrigatorio).
        fonte: Rotulo da fonte para a mensagem de erro (ex.: "RT", "Jusbrasil").
    """
    url = cdp_url or os.environ.get(env_var) or default
    if not url:
        rotulo = f" {fonte}" if fonte else ""
        raise RuntimeError(
            f"{env_var} nao configurada: a fonte{rotulo} usa o Chrome dedicado "
            f"via CDP (server-only). Defina {env_var} (ex.: http://127.0.0.1:9222) no host."
        )
    return url


class CdpSession:
    """Aba de fundo + websocket CDP via cdp-scaffold, com navigate/evaluate.

    Assinaturas cdp-scaffold reais:
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

    def __enter__(self) -> "CdpSession":
        self._tid, ws_url = _cdp.open_background_tab(
            self._host, self._port, self.timeout
        )
        self._ws = _cdp.connect(ws_url, self.timeout)
        self._cmd("Page.enable")
        return self

    def __exit__(self, *exc):
        try:
            if self._ws:
                try:
                    self._ws.close()
                except Exception:
                    pass
        finally:
            if self._tid:
                _cdp.close_target(self._host, self._port, self._tid)

    def _cmd(self, method: str, params: dict | None = None) -> dict:
        """Envia comando CDP e retorna a resposta completa.

        Passa recv_timeout=self.timeout para que uma pagina "tagarela" (flood de
        eventos) nao bloqueie o recv da resposta indefinidamente. Levanta CdpError
        em erro de protocolo (antes era engolido e virava None silencioso).
        """
        self._seq += 1
        resp = _cdp.cdp_call(self._ws, method, params or {}, self._seq, self.timeout)
        if isinstance(resp, dict) and "error" in resp:
            raise _cdp.CdpError(f"CDP error em {method}: {resp['error']}")
        return resp

    def evaluate(self, expr: str, await_promise: bool = False):
        """Avalia JS na pagina e retorna o valor desembrulhado.

        Se await_promise=True, usa cdp_eval (que ja fixa awaitPromise=True em cdp-scaffold).
        Se await_promise=False, usa Runtime.evaluate direto via _cmd.

        Em ambos os modos, um erro de JS (exception/subtype=="error") levanta
        CdpError em vez de devolver None silencioso — alinhado a cdp_eval.
        """
        if await_promise:
            self._seq += 1
            return _cdp.cdp_eval(self._ws, expr, self._seq)
        r = self._cmd(
            "Runtime.evaluate",
            {"expression": expr, "returnByValue": True, "awaitPromise": False},
        )
        result = r.get("result", {}).get("result", {})
        if result.get("subtype") == "error":
            raise _cdp.CdpError(f"JS error: {result.get('description')}")
        return result.get("value")

    def navigate(self, url: str) -> None:
        self._cmd("Page.navigate", {"url": url})

    def wait_ready(self, extra: float = 1.5) -> bool:
        for _ in range(int(self.timeout * 2)):
            time.sleep(0.5)
            if self.evaluate("document.readyState") == "complete":
                time.sleep(extra)
                return True
        return False
