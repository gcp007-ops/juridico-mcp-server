"""Download de documento RT (PDF/RTF) via pipeline offload no Chrome dedicado. Server-only.

Mecânica validada ao vivo (2026-06-19): POST /maf/app/delivery/document ->
GET retrieval (dispara) -> poll /maf/app/delivery/offload/status (XML) ->
GET /maf/app/delivery/offload/get (binário). Tudo in-page (credentials:include).
"""
from __future__ import annotations

import base64
import json
import re
import time
from typing import Optional, Tuple

from .cdp_session import RtCdpSession, cdp_url_or_raise

_FMT = {"PDF": "PDF", "RTF": "RTF"}
_FILENAME_RE = re.compile(r'filename\s*=\s*"?([^";]+)"?', re.I)

_COMPLETE_RE = re.compile(r"<complete>\s*true\s*</complete>", re.I)
_SUCCESS_RE = re.compile(r"<successful>\s*true\s*</successful>", re.I)
_DOCGUID_RE = re.compile(r"docguid=([A-Za-z0-9]+)")


def _docguid(url: str) -> str | None:
    m = _DOCGUID_RE.search(url or "")
    return m.group(1) if m else None


def _parse_status_xml(xml: str) -> Tuple[bool, bool]:
    x = xml or ""
    return (bool(_COMPLETE_RE.search(x)), bool(_SUCCESS_RE.search(x)))


def _click_save_js() -> str:
    return ("(()=>{const s=document.getElementById('saveImage');"
            "if(!s)return '__NO_SAVE__';s.click();return 'ok';})()")


def _post_delivery_js(formato: str) -> str:
    return (
        "(async()=>{const r=document.querySelector('input[name=\"deliveryFormat\"]');"
        "if(!r)return '__NO_OPTFORM__';let f=r;while(f&&f.tagName!=='FORM')f=f.parentElement;"
        "const fd=new FormData(f);fd.set('deliveryFormat'," + json.dumps(formato) + ");"
        "const body=new URLSearchParams([...fd.entries()].filter(([k])=>k!=='cancel')).toString();"
        "const resp=await fetch(f.action,{method:'POST',"
        "headers:{'Content-Type':'application/x-www-form-urlencoded'},body,credentials:'include'});"
        "const t=await resp.text();"
        "const g=(n)=>{const m=t.match(new RegExp('var\\\\s+'+n+'\\\\s*=\\\\s*\"([^\"]+)\"'));return m?m[1]:null;};"
        "return JSON.stringify({progress:g('progress'),delivery:g('delivery'),"
        "retrieveDeliveryUrl:g('retrieveDeliveryUrl')});})()"
    )


def _fetch_text_js(url: str) -> str:
    return (f"(async()=>{{const r=await fetch({json.dumps(url)},{{credentials:'include'}});"
            "return await r.text();})()")


def _fetch_bin_js(url: str) -> str:
    # NOTE: transfers the PDF byte-by-byte via btoa over CDP; hits the CDP
    # message-size ceiling (~100 MB) for very large documents — known limitation.
    return (
        f"(async()=>{{const r=await fetch({json.dumps(url)},{{credentials:'include'}});"
        "const cd=r.headers.get('content-disposition')||'';"
        "const ct=r.headers.get('content-type')||'';"
        "const u=new Uint8Array(await r.arrayBuffer());let s='';"
        "for(let i=0;i<u.length;i++)s+=String.fromCharCode(u[i]);"
        "return JSON.stringify({ct,cd,b64:btoa(s),bytes:u.length});})()"
    )


def _normalizar_filename(name: str, formato: str) -> str:
    """Colapsa extensão duplicada e garante extensão correta para o formato.

    Exemplos:
      "RTDoc x.pdf.pdf", "PDF" -> "RTDoc x.pdf"
      "doc",             "PDF" -> "doc.pdf"
      "doc.rtf.rtf",    "RTF" -> "doc.rtf"
    """
    ext = f".{formato.lower()}"
    # Remove duplicata trailing: "x.pdf.pdf" -> "x.pdf"
    double = ext + ext
    while name.lower().endswith(double):
        name = name[: len(name) - len(ext)]
    # Garante extensão única correta
    if not name.lower().endswith(ext):
        name = name + ext
    return name


def baixar_documento(doc_url: str, formato: str = "PDF", *,
                     cdp_url: Optional[str] = None, timeout: float = 90.0) -> Tuple[bytes, str]:
    formato = _FMT.get((formato or "PDF").upper())
    if not formato:
        raise ValueError("formato deve ser 'PDF' ou 'RTF'.")
    url = cdp_url_or_raise(cdp_url)
    with RtCdpSession(url, timeout=timeout) as s:
        s.navigate(doc_url)
        s.wait_ready(extra=2.0)
        if s.evaluate(_click_save_js()) == "__NO_SAVE__":
            raise RuntimeError("RT delivery: botão Salvar (#saveImage) ausente — sessão/layout.")
        s.wait_ready(extra=2.0)
        raw = s.evaluate(_post_delivery_js(formato), await_promise=True)
        if raw in ("__NO_OPTFORM__", None):
            raise RuntimeError("RT delivery: formulário de opções ausente após Salvar.")
        vars_ = json.loads(raw)
        if not vars_.get("delivery") or not vars_.get("retrieveDeliveryUrl") or not vars_.get("progress"):
            raise RuntimeError("RT delivery: vars de offload ausentes na resposta.")
        pedido = _docguid(doc_url)
        entregue = _docguid(vars_["delivery"])
        if pedido and entregue and pedido != entregue:
            raise RuntimeError(
                f"RT delivery: docguid divergente (pedido {pedido} != entregue {entregue}) "
                "— sessao serviu documento cruzado; abortado."
            )
        s.evaluate(_fetch_text_js(vars_["delivery"]), await_promise=True)  # dispara geração
        deadline = time.time() + timeout
        ok = False
        while time.time() < deadline:
            xml = s.evaluate(_fetch_text_js(vars_["progress"]), await_promise=True) or ""
            complete, successful = _parse_status_xml(xml)
            if complete:
                ok = successful
                break
            time.sleep(1.0)
        if not ok:
            raise RuntimeError("RT delivery: geração não concluiu com sucesso (assinatura/limite?).")
        _bin_raw = s.evaluate(_fetch_bin_js(vars_["retrieveDeliveryUrl"]), await_promise=True)
        if not _bin_raw:
            raise RuntimeError("RT delivery: download nao retornou dados (documento grande ou sessao expirada)")
        meta = json.loads(_bin_raw)
    data = base64.b64decode(meta["b64"]) if meta.get("b64") else b""
    if not data:
        raise RuntimeError("RT delivery: binário vazio retornado.")
    m = _FILENAME_RE.search(meta.get("cd", ""))
    filename = m.group(1).strip() if m else f"rt-documento.{formato.lower()}"
    filename = _normalizar_filename(filename, formato)
    return data, filename
