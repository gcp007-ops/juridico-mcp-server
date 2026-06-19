# src/juridico_mcp/rt/auth.py
"""Login RT Online via Chrome dedicado (CDP) — fluxo OnePass Auth0 (2 telas).

Porte de busca-academica-mcp/rt_auth.py adaptado para usar RtCdpSession
(cdp-scaffold) em vez do websocket/cmd/eval hand-rolled.

A RT compartilha o Chrome dedicado e a conta dedicada de automacao com o L1;
o IdP OnePass e compartilhado, entao o warm costuma ser silencioso (sem form).
Credenciais sao FALLBACK, so usadas quando o Auth0 exige o form.

SERVER-ONLY: depende do Chrome dedicado (RT_CDP_URL).
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from typing import Literal, Optional

from .cdp_session import RtCdpSession, DEFAULT_TIMEOUT

__all__ = ["RtInteractiveLoginRequired", "login_rt_via_cdp"]


class RtInteractiveLoginRequired(RuntimeError):
    """A RT/OnePass exige uma etapa humana, como MFA ou captcha."""


RT_HOST = "revistadostribunais.com.br"
RT_ENTRY = ("https://www.revistadostribunais.com.br/maf/api/tocectory"
            "?tocguid=brdoct&stnew=true&oss=true&ndd=2")
KEYCHAIN_SERVICE = "novajus-keepalive"  # mesma conta dedicada do L1


def _on_rt(url: str) -> bool:
    """True se a URL esta NO host da RT. Usa o hostname (nao substring) — a
    pagina do signon traz o host da RT no parametro `returnto`, e um match por
    substring faria o signon parecer 'ja na RT' (bug: o login nunca preenchia
    o e-mail e travava no signon)."""
    host = urllib.parse.urlparse(url).hostname or ""
    return host == RT_HOST or host.endswith("." + RT_HOST)


def _auth0_page(url: str) -> Optional[Literal["identifier", "password"]]:
    if "/u/login/identifier" in url:
        return "identifier"
    if "/u/login/password" in url:
        return "password"
    return None


def _auth0_fill_identifier_js(email: str) -> str:
    return (
        "(function(){const find=(s)=>document.querySelector(s);"
        "const u=find('#username')||find('input[name=\"username\"]')||find('input[type=\"email\"]');"
        "if(!u) return 'username_not_found';"
        f"u.value={json.dumps(email)};"
        "u.dispatchEvent(new Event('input',{bubbles:true}));"
        "u.dispatchEvent(new Event('change',{bubbles:true}));"
        "const b=find('button[type=\"submit\"][name=\"action\"]')||find('button[type=\"submit\"]');"
        "if(!b) return 'btn_not_found'; b.click(); return 'submitted';})()"
    )


def _auth0_fill_password_js(password: str) -> str:
    return (
        "(function(){const find=(s)=>document.querySelector(s);"
        "const p=find('#password')||find('input[name=\"password\"]')||find('input[type=\"password\"]');"
        "if(!p) return 'password_not_found';"
        f"p.value={json.dumps(password)};"
        "p.dispatchEvent(new Event('input',{bubbles:true}));"
        "p.dispatchEvent(new Event('change',{bubbles:true}));"
        "const b=find('button[type=\"submit\"][name=\"action\"]')||find('button[type=\"submit\"]');"
        "if(!b) return 'btn_not_found'; b.click(); return 'submitted';})()"
    )


def _signon_enter_email_js(email: str) -> str:
    """JS p/ a pagina legada signon.thomsonreuters.com: digita o e-mail no campo
    Username e dispara blur — conta migrada e detectada e o TR redireciona pro
    Auth0. Idempotente."""
    return (
        "(function(){"
        "const u=document.querySelector('input[name=\"Username\"]')||document.querySelector('#userNameInput');"
        "if(!u) return 'no_username';"
        f"u.value={json.dumps(email)};"
        "u.dispatchEvent(new Event('input',{bubbles:true}));"
        "u.dispatchEvent(new Event('change',{bubbles:true}));"
        "u.dispatchEvent(new Event('blur',{bubbles:true}));"
        "return 'email_set';})()"
    )


def _keychain_password(login: str) -> str:
    """Senha da conta dedicada via Keychain do macOS. '' em qualquer falha.

    Nunca loga a senha. Servico = KEYCHAIN_SERVICE, account = login.
    """
    if not login:
        return ""
    import subprocess
    try:
        r = subprocess.run(
            ["/usr/bin/security", "find-generic-password",
             "-s", KEYCHAIN_SERVICE, "-a", login, "-w"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _rt_credentials() -> tuple[str, str]:
    """(email, senha) da conta dedicada. email<-RT_LOGIN; senha<-Keychain.

    ('', '') quando ausente — o warm silencioso (IdP vivo) dispensa credenciais.
    """
    email = os.environ.get("RT_LOGIN", "").strip()
    senha = _keychain_password(email) if email else ""
    return email, senha


def login_rt_via_cdp(cdp_url: str, email: Optional[str] = None,
                     senha: Optional[str] = None, timeout: float = DEFAULT_TIMEOUT,
                     poll_interval: float = 1.0) -> dict:
    """Garante sessao RT autenticada no Chrome dedicado.

    Abre uma aba propria (via RtCdpSession), navega a entrada de Doutrina e:
      - se ja autenticado (#searchForm presente) -> no-op (warm silencioso);
      - se redirecionou ao Auth0 -> dirige as 2 telas (identifier -> password)
        com as credenciais da conta dedicada e espera voltar ao host da RT.

    Returns {ok: True, final_url, used: 'silent_warm'|'auth0_form'}.
    Raises RtInteractiveLoginRequired em captcha/MFA.
    Raises RuntimeError em credencial invalida/timeout/sem form.
    """
    if email is None or senha is None:
        email, senha = _rt_credentials()

    submitted: set[str] = set()
    deadline = time.time() + timeout
    url = ""

    with RtCdpSession(cdp_url, timeout=timeout) as s:
        s.navigate(RT_ENTRY)

        while time.time() < deadline:
            time.sleep(poll_interval)
            if s.evaluate("document.readyState") != "complete":
                continue
            url = s.evaluate("window.location.href") or ""

            if _on_rt(url):
                has_form = s.evaluate("!!document.querySelector('#searchForm')")
                if has_form:
                    used = "auth0_form" if submitted else "silent_warm"
                    return {"ok": True, "final_url": url, "used": used}
                # Na RT mas sem form ainda: SPA/redirect carregando — segue.
                continue

            page = _auth0_page(url)
            if page == "identifier":
                if "identifier" not in submitted:
                    if not email:
                        raise RuntimeError(
                            "RT pediu login Auth0 mas RT_LOGIN/Keychain ausentes "
                            "(IdP OnePass expirou e nao ha credenciais para relogar).")
                    r = s.evaluate(_auth0_fill_identifier_js(email))
                    if r != "submitted":
                        raise RuntimeError(f"RT Auth0 identifier fill falhou: {r} ({url})")
                    submitted.add("identifier")
                continue
            if page == "password":
                if "password" not in submitted:
                    r = s.evaluate(_auth0_fill_password_js(senha))
                    if r != "submitted":
                        raise RuntimeError(f"RT Auth0 password fill falhou: {r} ({url})")
                    submitted.add("password")
                    continue
                txt = (s.evaluate("document.body.innerText.toLowerCase()") or "")
                if any(k in txt for k in ("incorrect", "incorreta", "invalid", "credential")):
                    raise RuntimeError("RT login: credenciais incorretas (rejeitadas pelo Auth0).")
                continue
            if "signon.thomsonreuters.com" in url and page is None:
                if not email:
                    raise RuntimeError(
                        "RT signon pediu identificacao mas RT_LOGIN/Keychain ausentes.")
                r = s.evaluate(_signon_enter_email_js(email))
                if r != "no_username":
                    continue
            if "thomsonreuters.com" in url:
                txt = (s.evaluate("document.body.innerText.toLowerCase()") or "")
                if "captcha" in txt or "verify you are human" in txt:
                    raise RtInteractiveLoginRequired(
                        "RT login requer verificacao humana/captcha no Chrome dedicado."
                    )
                if any(k in txt for k in (
                    "verification code", "two-factor", "multi-factor", "mfa", "2fa",
                    "one-time", "authenticator", "codigo de verificacao",
                    "código de verificação", "duplo fator",
                )):
                    raise RtInteractiveLoginRequired(
                        "RT login requer MFA/duplo fator no Chrome dedicado."
                    )
                continue

        raise RuntimeError(f"RT login timeout — nao autenticou. URL: {url}")
