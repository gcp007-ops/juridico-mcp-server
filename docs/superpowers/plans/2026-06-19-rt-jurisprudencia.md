# RT Jurisprudência (juridico-mcp-server) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar jurisprudência RT Online (busca avançada + captura PDF/MD→nota `julgado`) ao `juridico-mcp-server` como fonte premium server-only (CDP/OnePass), ao lado das fontes httpx públicas.

**Architecture:** Um subpacote `src/juridico_mcp/rt/` sobre `cdp-scaffold`. Um único adaptador `rt/cdp_session.py` (`RtCdpSession`) encapsula `cdp-scaffold`; auth/session/delivery/captura são portados da implementação JÁ VALIDADA em `busca-academica-mcp` chamando esse adaptador. Parser e captura de jurisprudência são novos (estrutura distinta da Doutrina). 3 tools finas no `server.py`; degradação honesta sem `RT_CDP_URL` (as tools httpx seguem intactas).

**Tech Stack:** Python ≥3.10, FastMCP, `cdp-scaffold[html,mcp]`, `markdownify`, `lxml`, `pytest`+`pytest-asyncio` (novo), `uv`.

## Global Constraints

- Server-only: tools RT exigem `RT_CDP_URL` (Chrome dedicado :9222). Sem rede/Chrome/Keychain/vault real nos testes unitários — stubs/monkeypatch/tmp_path.
- NÃO alterar as tools httpx existentes (CJF/STJ/BNP/TJDFT) além de uma linha em `listar_fontes`.
- Saída de busca em `shared.ResultadoJuridico` + `server.formatar_resultados_texto` (consistência com as demais tools).
- Escopo v1: **jurisprudência** (`tocguid=brjuris`, `infotype=br_juris`). NÃO legislação/súmulas.
- Reuso: `cdp-scaffold` para CDP genérico; bits RT portados de `busca-academica-mcp` (NÃO extrair lib compartilhada).
- Referência de porte (validada, server-only): `/Users/gustavo/Developer/busca-academica-mcp/src/busca_academica_mcp/{rt_cdp,rt_auth,delivery,captura_md}.py`.
- noteType de captura: `julgado` (required `tribunal`,`classe`,`numero`), pasta `Conhecimento/Fontes/Julgados/RT/`, PDFs em `.../RT/_pdf/`, base `THINKBOX_VAULT_PATH`.
- Frontmatter: escalares de texto entre aspas + `_yaml_escape` (nome com `": "` quebra YAML — lição da Doutrina). Encoding: Unicode em valores, ASCII em filename/chaves.
- Erros honestos: nunca fabricar arquivo/resultado; `successful=false` no offload → erro acionável.
- Commit por task, pathspec explícito (NUNCA `git add -A`; há `data/` untracked não relacionado). Branch: `feat/rt-jurisprudencia` (já criada). Co-autoria: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Datas (mapeadas ao vivo): `dateType` ∈ {`year`,`exact`,`between`,`any`}; `fromDate`/`toDate`/`exactDate` formato `dd/mm/aaaa`; `ano` = AAAA.

---

### Task 1: Setup deps + testes + adaptador `RtCdpSession` sobre cdp-scaffold

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`, `tests/conftest.py` (se necessário), `src/juridico_mcp/rt/__init__.py`, `src/juridico_mcp/rt/cdp_session.py`
- Test: `tests/test_rt_cdp_session.py`

**Interfaces:**
- Produces:
  - `rt.cdp_session.RtCdpSession(cdp_url, timeout=45.0)` context manager com `navigate(url)`, `wait_ready(extra=1.5)`, `evaluate(expr, await_promise=False)`.
  - `rt.cdp_session.cdp_url_or_raise(cdp_url=None) -> str`.
  - `rt.cdp_session.build_fetch_js(fields: dict, placeholders: tuple) -> str`.
  - `rt.cdp_session.RtSessionExpired(RuntimeError)`.

- [ ] **Step 1: Add dependencies**

Em `pyproject.toml`, `dependencies` += `"cdp-scaffold[html,mcp]"`, `"markdownify>=0.11.6"`, `"lxml>=5.0.0"`. Adicionar grupo de testes (siga o padrão do repo; se não houver, use `[dependency-groups]` do uv):
```toml
[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
```
IMPORTANTE: leia como `leitor-processual-cdp/pyproject.toml` resolve `cdp-scaffold` (provável `[tool.uv.sources]` apontando para o path local `../cdp-scaffold`) e REPLIQUE essa fonte aqui. Rode `uv sync`.

- [ ] **Step 2: Verify cdp-scaffold imports**

Run: `cd /Users/gustavo/Developer/juridico-mcp-server && uv run python -c "import cdp_scaffold.cdp as c; print([n for n in dir(c) if not n.startswith('__')][:20])"`
Expected: lista inclui `open_background_tab`, `connect`, `cdp_call`, `cdp_eval`, `close_target`. ANOTE as assinaturas exatas dessas funções (você vai usá-las no adaptador). Se a resolução de `cdp-scaffold` falhar, PARE e reporte (problema de sourcing, não de código).

- [ ] **Step 3: Write failing test for adapter + build_fetch_js**

```python
# tests/test_rt_cdp_session.py
from juridico_mcp.rt import cdp_session


def test_build_fetch_js_seta_campos_e_zera_placeholders():
    js = cdp_session.build_fetch_js({"frt": 'dano "moral"', "num": "123"}, ("jud", "tribunais"))
    assert "#searchForm" in js
    assert "123" in js and "jud" in js and "tribunais" in js
    assert "fetch(f.action" in js


def test_cdp_url_or_raise_sem_env(monkeypatch):
    monkeypatch.delenv("RT_CDP_URL", raising=False)
    import pytest
    with pytest.raises(RuntimeError, match="RT_CDP_URL"):
        cdp_session.cdp_url_or_raise()
```

- [ ] **Step 4: Run to verify fail**

Run: `uv run pytest tests/test_rt_cdp_session.py -q`
Expected: FAIL (módulo inexistente).

- [ ] **Step 5: Implement `rt/cdp_session.py`**

Porte a estrutura de `busca-academica-mcp/src/busca_academica_mcp/rt_cdp.py`, mas implemente os métodos de CDP sobre `cdp-scaffold` (use as assinaturas anotadas no Step 2). Estrutura-alvo:

```python
# src/juridico_mcp/rt/cdp_session.py
"""Camada CDP da RT sobre cdp-scaffold. Server-only."""
from __future__ import annotations
import json, os, time
from typing import Optional

import cdp_scaffold.cdp as _cdp

DEFAULT_TIMEOUT = 45.0


class RtSessionExpired(RuntimeError):
    """Sessão RT no Chrome dedicado expirou (escalável via relogin)."""


def cdp_url_or_raise(cdp_url: Optional[str] = None) -> str:
    url = cdp_url or os.environ.get("RT_CDP_URL")
    if not url:
        raise RuntimeError(
            "RT_CDP_URL não configurada: a RT usa o Chrome dedicado via CDP (server-only). "
            "Defina RT_CDP_URL (ex.: http://127.0.0.1:9222) no host."
        )
    return url


class RtCdpSession:
    """Aba de fundo + websocket CDP via cdp-scaffold, com navigate/evaluate."""
    def __init__(self, cdp_url: str, timeout: float = DEFAULT_TIMEOUT):
        self.cdp_url = cdp_url.rstrip("/")
        self.timeout = timeout
        self._ws = None
        self._tid = None
        self._seq = 0

    def __enter__(self):
        # use cdp_scaffold.open_background_tab(...) -> (target_id, ws_url) e connect(ws_url)
        self._tid, ws_url = _cdp.open_background_tab(self.cdp_url, timeout=self.timeout)
        self._ws = _cdp.connect(ws_url, timeout=self.timeout)
        self._cmd("Page.enable")
        return self

    def __exit__(self, *exc):
        try:
            if self._ws: self._ws.close()
        finally:
            _cdp.close_target(self.cdp_url, self._tid)

    def _cmd(self, method, params=None):
        # use cdp_scaffold.cdp_call(self._ws, method, params, msg_id) conforme assinatura anotada
        self._seq += 1
        return _cdp.cdp_call(self._ws, method, params or {}, self._seq)

    def evaluate(self, expr, await_promise=False):
        # cdp_scaffold.cdp_eval pode não suportar awaitPromise; se não, use _cmd("Runtime.evaluate", {...})
        self._seq += 1
        r = self._cmd("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True, "awaitPromise": await_promise})
        return r.get("result", {}).get("result", {}).get("value")

    def navigate(self, url):
        self._cmd("Page.navigate", {"url": url})

    def wait_ready(self, extra: float = 1.5):
        for _ in range(int(self.timeout * 2)):
            time.sleep(0.5)
            if self.evaluate("document.readyState") == "complete":
                time.sleep(extra); return True
        return False


def build_fetch_js(fields: dict, placeholders: tuple) -> str:
    sets = "".join(f"fd.set({json.dumps(k)},{json.dumps(str(v))});" for k, v in fields.items())
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
```
> ADAPTE `_cmd`/`evaluate`/`__enter__` às assinaturas REAIS de cdp-scaffold anotadas no Step 2. Se `cdp_scaffold` expõe um helper de eval que já faz returnByValue/awaitPromise, use-o; caso contrário, fale CDP cru pelo ws (como acima). Garanta que `evaluate(..., await_promise=True)` funciona (necessário para fetch in-page).

- [ ] **Step 6: Run to verify pass**

Run: `uv run pytest tests/test_rt_cdp_session.py -q`
Expected: PASS (os 2 testes; são puros, não tocam CDP).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock tests/__init__.py tests/test_rt_cdp_session.py src/juridico_mcp/rt/__init__.py src/juridico_mcp/rt/cdp_session.py
git commit -m "feat(rt): adaptador RtCdpSession sobre cdp-scaffold + deps

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `rt/auth.py` (OnePass) + `rt/session.py` (run_search_form + relogin)

**Files:**
- Create: `src/juridico_mcp/rt/auth.py`, `src/juridico_mcp/rt/session.py`
- Test: `tests/test_rt_session.py`

**Interfaces:**
- Consumes: `rt.cdp_session.{RtCdpSession, RtSessionExpired, build_fetch_js, cdp_url_or_raise}`.
- Produces:
  - `rt.auth.login_rt_via_cdp(cdp_url, email=None, senha=None, timeout=60.0) -> dict` (`{ok, final_url, used}`); `rt.auth.RtInteractiveLoginRequired`.
  - `rt.session.run_search_form(entry_url, fields, *, placeholders, cdp_url=None, timeout=45.0) -> str` (HTML), com relogin reativo 1x.

- [ ] **Step 1: Port `rt/auth.py`**

Porte `busca-academica-mcp/src/busca_academica_mcp/rt_auth.py` praticamente verbatim, com estas adaptações:
- Trocar o websocket/`_cmd`/`_eval` hand-rolled pelo uso de `RtCdpSession` (de `rt.cdp_session`) — abra a sessão e use `s.navigate`/`s.evaluate`/`s.wait_ready`. A lógica das 2 telas Auth0 (identifier→password), Keychain (`KEYCHAIN_SERVICE="novajus-keepalive"`), `RT_LOGIN`, detecção MFA/captcha → `RtInteractiveLoginRequired` permanece IDÊNTICA.
- Mantenha `RT_ENTRY` apontando para a Doutrina (`tocguid=brdoct`) — o warm de sessão é por IdP, serve para qualquer coleção.

- [ ] **Step 2: Write failing test for run_search_form relogin**

```python
# tests/test_rt_session.py
import pytest
from juridico_mcp.rt import session as sess
from juridico_mcp.rt.cdp_session import RtSessionExpired


def test_run_search_form_relogin_retry_succeeds(monkeypatch):
    chamadas = {"fetch": 0, "login": 0}
    def fake_fetch(entry, fields, placeholders, cdp_url, timeout):
        chamadas["fetch"] += 1
        if chamadas["fetch"] == 1:
            raise RtSessionExpired("expirou")
        return "<html>ok</html>"
    monkeypatch.setattr(sess, "_fetch_html", fake_fetch)
    monkeypatch.setattr(sess, "cdp_url_or_raise", lambda u=None: "http://x")
    import juridico_mcp.rt.auth as auth
    monkeypatch.setattr(auth, "login_rt_via_cdp", lambda url: chamadas.__setitem__("login", chamadas["login"] + 1))
    out = sess.run_search_form("entry", {"frt": "x"}, placeholders=())
    assert out == "<html>ok</html>" and chamadas["login"] == 1


def test_run_search_form_relogin_falha_levanta_runtime(monkeypatch):
    def fake_fetch(*a, **k): raise RtSessionExpired("sempre")
    monkeypatch.setattr(sess, "_fetch_html", fake_fetch)
    monkeypatch.setattr(sess, "cdp_url_or_raise", lambda u=None: "http://x")
    import juridico_mcp.rt.auth as auth
    monkeypatch.setattr(auth, "login_rt_via_cdp", lambda url: None)
    with pytest.raises(RuntimeError):
        sess.run_search_form("entry", {"frt": "x"}, placeholders=())
```

- [ ] **Step 3: Run to verify fail**

Run: `uv run pytest tests/test_rt_session.py -q`
Expected: FAIL (`session` inexistente).

- [ ] **Step 4: Implement `rt/session.py`**

```python
# src/juridico_mcp/rt/session.py
"""Submissão genérica de #searchForm da RT via CDP, com relogin reativo. Server-only."""
from __future__ import annotations
from typing import Optional
from .cdp_session import RtCdpSession, RtSessionExpired, build_fetch_js, cdp_url_or_raise, DEFAULT_TIMEOUT


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
    except RtSessionExpired:
        from . import auth
        auth.login_rt_via_cdp(url)
        try:
            return _fetch_html(entry_url, fields, placeholders, url, timeout)
        except RtSessionExpired as exc:
            raise RuntimeError(f"RT: sessão segue inválida após relogin OnePass ({exc}).") from exc
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_rt_session.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/juridico_mcp/rt/auth.py src/juridico_mcp/rt/session.py tests/test_rt_session.py
git commit -m "feat(rt): auth OnePass + run_search_form (porte sobre cdp-scaffold)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `rt/jurisprudencia.py` (busca + parser) + tool `rt_jurisprudencia_buscar`

**Files:**
- Create: `src/juridico_mcp/rt/jurisprudencia.py`
- Modify: `src/juridico_mcp/server.py`
- Test: `tests/test_rt_jurisprudencia.py`, `tests/test_server_rt.py`, `tests/fixtures/rt_juris_resultados.html`

**Interfaces:**
- Consumes: `rt.session.run_search_form`; `shared.ResultadoJuridico`; `server.formatar_resultados_texto`.
- Produces:
  - `rt.jurisprudencia.{ENTRY, PLACEHOLDERS, montar_campos(...), parse_resultados(html)->list[dict], buscar(...)->list[dict]}`.
  - `server.rt_jurisprudencia_buscar(livre="", numero="", relator="", tribunais="", ano="", data_de="", data_ate="", max_resultados=10) -> str`.

- [ ] **Step 1: Create fixture from real structure**

`tests/fixtures/rt_juris_resultados.html` (estrutura real mapeada ao vivo):
```html
<div class="result">
  <div class="deliveryInput"><input class="documentSelection" value="1" type="checkbox"></div>
  <div class="resultTitle">
    <a href="/maf/app/resultList/document?&src=rl&docguid=I08e88450884d11ef8abe8cec937cf41c&hitguid=x&spos=1" class="documentLink">
      0010198-10.2024.5.03.0079 - José Murilo de Morais - Data de Julgamento 08/10/2024
    </a>
    <p class="subTitle">Tribunal Regional do Trabalho da 3.ª Região</p>
    <p class="subTitle">Diário Eletrônico da Justiça do Trabalho | Out / 2024 | JRP\2024\1935245</p>
  </div>
</div>
<div class="result">
  <div class="resultTitle">
    <a href="/maf/app/resultList/document?&docguid=Iabc123&spos=2" class="documentLink">
      1234567-00.2023.8.26.0100 - Maria Souza - Data de Julgamento 01/02/2023
    </a>
    <p class="subTitle">Tribunal de Justiça de São Paulo</p>
    <p class="subTitle">Revista dos Tribunais | Fev / 2023 | JRP\2023\555</p>
  </div>
</div>
```

- [ ] **Step 2: Write failing tests (parser + montar_campos)**

```python
# tests/test_rt_jurisprudencia.py
import pathlib
from juridico_mcp.rt import jurisprudencia as j

FIX = pathlib.Path(__file__).parent / "fixtures" / "rt_juris_resultados.html"


def test_parse_resultados_extrai_campos():
    out = j.parse_resultados(FIX.read_text(encoding="utf-8"))
    assert len(out) == 2
    r = out[0]
    assert r["numero_processo"] == "0010198-10.2024.5.03.0079"
    assert r["relator"] == "José Murilo de Morais"
    assert r["data_julgamento"] == "08/10/2024"
    assert r["tribunal"] == "Tribunal Regional do Trabalho da 3.ª Região"
    assert r["jrp"] == "JRP\\2024\\1935245"
    assert "docguid=I08e88450884d11ef8abe8cec937cf41c" in r["url"]


def test_montar_campos_ano_e_intervalo():
    c1 = j.montar_campos(livre="dano", ano="2024")
    assert c1["frt"] == "dano" and c1["dateType"] == "year" and c1["ano"] == "2024"
    c2 = j.montar_campos(livre="dano", data_de="01/01/2024", data_ate="31/12/2024")
    assert c2["dateType"] == "between" and c2["fromDate"] == "01/01/2024" and c2["toDate"] == "31/12/2024"
    c3 = j.montar_campos(numero="0010198-10.2024.5.03.0079", relator="Morais")
    assert c3["num"].startswith("0010198") and c3["jud"] == "Morais"
```

- [ ] **Step 3: Run to verify fail**

Run: `uv run pytest tests/test_rt_jurisprudencia.py -q`
Expected: FAIL (módulo inexistente).

- [ ] **Step 4: Implement `rt/jurisprudencia.py`**

```python
# src/juridico_mcp/rt/jurisprudencia.py
"""Jurisprudência RT Online via CDP. Parser próprio (subTitle/JRP). Server-only."""
from __future__ import annotations
import re
from typing import List
from lxml import html as lhtml
from . import session as _session

BASE_HOST = "https://www.revistadostribunais.com.br"
ENTRY = f"{BASE_HOST}/maf/api/tocectory?tocguid=brjuris&stnew=true&oss=true&ndd=1"
PLACEHOLDERS = ("IWglobal1", "IWglobal2", "num", "jud", "tribunais", "revistas", "volume", "pageNum")

_JRP_RE = re.compile(r"JRP\\\d{4}\\\d+")
_DATA_JULG_RE = re.compile(r"Data de Julgamento\s+(\d{2}/\d{2}/\d{4})")
_NUM_RE = re.compile(r"^\s*([\d.\-/]+)\s*-")


def montar_campos(livre="", numero="", relator="", tribunais="", ano="",
                  data_de="", data_ate="") -> dict:
    campos: dict = {}
    if livre: campos["frt"] = livre
    if numero: campos["num"] = numero
    if relator: campos["jud"] = relator
    if tribunais: campos["tribunais"] = tribunais
    if ano:
        campos["dateType"] = "year"; campos["ano"] = str(ano)
    elif data_de or data_ate:
        campos["dateType"] = "between"
        if data_de: campos["fromDate"] = data_de
        if data_ate: campos["toDate"] = data_ate
    return campos


def _txt(node) -> str:
    return " ".join("".join(node.itertext()).split()).strip()


def _parse_um(div):
    links = div.xpath('.//a[contains(@class,"documentLink")]')
    if not links:
        return None
    a = links[0]
    titulo = _txt(a)
    href = a.get("href", "")
    url = href if href.startswith("http") else f"{BASE_HOST}{href}"
    m_num = _NUM_RE.search(titulo)
    m_data = _DATA_JULG_RE.search(titulo)
    relator = ""
    partes = [p.strip() for p in titulo.split(" - ")]
    if len(partes) >= 2:
        relator = partes[1]
    subs = [_txt(p) for p in div.xpath('.//p[contains(@class,"subTitle")]')]
    tribunal = subs[0] if subs else ""
    veiculo, data_pub, jrp = "", "", ""
    if len(subs) >= 2:
        seg = [s.strip() for s in subs[1].split("|")]
        veiculo = seg[0] if seg else ""
        if len(seg) >= 2: data_pub = seg[1]
        m_jrp = _JRP_RE.search(subs[1])
        if m_jrp: jrp = m_jrp.group(0)
    return {
        "numero_processo": m_num.group(1) if m_num else "",
        "relator": relator,
        "data_julgamento": m_data.group(1) if m_data else "",
        "tribunal": tribunal,
        "veiculo": veiculo,
        "data_publicacao": data_pub,
        "jrp": jrp or None,
        "url": url,
    }


def parse_resultados(html_text: str) -> List[dict]:
    tree = lhtml.fromstring(html_text)
    out = []
    for div in tree.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " result ")]'):
        item = _parse_um(div)
        if item and item["url"]:
            out.append(item)
    return out


async def buscar(livre="", numero="", relator="", tribunais="", ano="",
                 data_de="", data_ate="", max_resultados=10) -> List[dict]:
    import asyncio
    campos = montar_campos(livre=livre, numero=numero, relator=relator, tribunais=tribunais,
                           ano=ano, data_de=data_de, data_ate=data_ate)
    html_text = await asyncio.to_thread(
        _session.run_search_form, ENTRY, campos, placeholders=PLACEHOLDERS
    )
    return parse_resultados(html_text)[:max_resultados]
```

- [ ] **Step 5: Write failing test for tool (stub)**

```python
# tests/test_server_rt.py
import pytest
from juridico_mcp import server


@pytest.mark.asyncio
async def test_rt_jurisprudencia_buscar_formata(monkeypatch):
    async def fake_buscar(**kw):
        return [{"numero_processo": "0010198-10.2024.5.03.0079", "relator": "Morais",
                 "data_julgamento": "08/10/2024", "tribunal": "TRT-3",
                 "veiculo": "DEJT", "data_publicacao": "Out/2024", "jrp": "JRP\\2024\\1",
                 "url": "https://rt/doc?docguid=X"}]
    monkeypatch.setattr(server.rt_juris, "buscar", fake_buscar)
    out = await server.rt_jurisprudencia_buscar(livre="dano moral")
    assert "0010198-10.2024.5.03.0079" in out and isinstance(out, str)


@pytest.mark.asyncio
async def test_rt_jurisprudencia_buscar_sem_parametro():
    out = await server.rt_jurisprudencia_buscar()
    assert "invalido" in out.lower()
```

- [ ] **Step 6: Run to verify fail**

Run: `uv run pytest tests/test_server_rt.py -q`
Expected: FAIL (`rt_jurisprudencia_buscar`/`server.rt_juris` ausentes).

- [ ] **Step 7: Implement tool in `server.py`**

Adicionar imports e a tool (mapeia dicts → `ResultadoJuridico` p/ usar o formatador existente):
```python
from .rt import jurisprudencia as rt_juris
from .shared import ResultadoJuridico

@mcp.tool()
async def rt_jurisprudencia_buscar(livre: str = "", numero: str = "", relator: str = "",
                                   tribunais: str = "", ano: str = "", data_de: str = "",
                                   data_ate: str = "", max_resultados: int = 10) -> str:
    """Busca jurisprudência premium na RT Online (server-only via Chrome dedicado/CDP).

    Pelo menos um de livre/numero/relator é obrigatório. Ano único OU intervalo
    (data_de/data_ate em dd/mm/aaaa, data de julgamento). Requer RT_CDP_URL.
    """
    if not any(s.strip() for s in (livre, numero, relator)):
        return "Parametro invalido: informe ao menos livre, numero ou relator."
    try:
        regs = await rt_juris.buscar(livre=livre.strip(), numero=numero.strip(),
                                     relator=relator.strip(), tribunais=tribunais.strip(),
                                     ano=ano.strip(), data_de=data_de.strip(),
                                     data_ate=data_ate.strip(),
                                     max_resultados=max(1, min(int(max_resultados), 50)))
    except Exception as e:
        return f"Erro na busca RT jurisprudencia: {e}"
    resultados = [ResultadoJuridico(
        fonte="rt", tipo="acordao", numero=r["numero_processo"], orgao=r["tribunal"],
        relator=r["relator"], data=r["data_julgamento"], url=r["url"],
        extras={"jrp": r.get("jrp"), "veiculo": r.get("veiculo"), "data_publicacao": r.get("data_publicacao")},
    ) for r in regs]
    return formatar_resultados_texto(resultados, titulo="RT Online — Jurisprudência")
```
(Confirme o nome exato `formatar_resultados_texto` em `server.py` e reuse-o.)

- [ ] **Step 8: Run to verify pass**

Run: `uv run pytest tests/test_rt_jurisprudencia.py tests/test_server_rt.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/juridico_mcp/rt/jurisprudencia.py src/juridico_mcp/server.py tests/test_rt_jurisprudencia.py tests/test_server_rt.py tests/fixtures/rt_juris_resultados.html
git commit -m "feat(rt): busca avançada de jurisprudência + tool rt_jurisprudencia_buscar

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `rt/delivery.py` (offload, porte) + tool `rt_baixar_pdf`

**Files:**
- Create: `src/juridico_mcp/rt/delivery.py`
- Modify: `src/juridico_mcp/server.py`
- Test: `tests/test_rt_delivery.py`, `tests/test_server_rt.py`

**Interfaces:**
- Consumes: `rt.cdp_session.{RtCdpSession, cdp_url_or_raise}`.
- Produces:
  - `rt.delivery.{_parse_status_xml(xml)->(bool,bool), _normalizar_filename(name, formato)->str, baixar_documento(doc_url, formato="PDF", *, cdp_url=None, timeout=90.0)->(bytes,str)}`.
  - `server.rt_baixar_pdf(doc_url, destino="") -> str` (JSON).

- [ ] **Step 1: Port `rt/delivery.py`**

Porte `busca-academica-mcp/src/busca_academica_mcp/delivery.py` VERBATIM, trocando apenas o import da sessão para `from .cdp_session import RtCdpSession, cdp_url_or_raise`. A lógica (click `#saveImage` → POST `deliveryFormat` → extrair vars `progress`/`delivery`/`retrieveDeliveryUrl` → GET retrieval → poll `offload/status` até `<complete>true</complete><successful>true</successful>` → GET `offload/get` → base64) é COLLECTION-AGNOSTIC e vale para `br_juris` sem mudança. Inclui `_parse_status_xml` e `_normalizar_filename` (com a correção de `.pdf.pdf`).

- [ ] **Step 2: Write failing tests (port unit tests)**

```python
# tests/test_rt_delivery.py
from juridico_mcp.rt import delivery


def test_parse_status_xml():
    assert delivery._parse_status_xml("<response><complete>true</complete><successful>true</successful></response>") == (True, True)
    assert delivery._parse_status_xml("<response><complete>true</complete><successful>false</successful></response>") == (True, False)
    assert delivery._parse_status_xml("<response><complete>false</complete></response>") == (False, False)


def test_normalizar_filename():
    assert delivery._normalizar_filename("RTDoc x.pdf.pdf", "PDF") == "RTDoc x.pdf"
    assert delivery._normalizar_filename("doc", "PDF") == "doc.pdf"
```

- [ ] **Step 3: Run to verify fail**

Run: `uv run pytest tests/test_rt_delivery.py -q`
Expected: FAIL (módulo inexistente).

- [ ] **Step 4: Verify pass (after port)**

Run: `uv run pytest tests/test_rt_delivery.py -q` e `uv run python -c "from juridico_mcp.rt import delivery; print('ok')"`
Expected: PASS + import ok.

- [ ] **Step 5: Write failing test for tool**

```python
# tests/test_server_rt.py — adicionar
def test_rt_baixar_pdf_grava(monkeypatch, tmp_path):
    monkeypatch.setattr(server.rt_delivery, "baixar_documento",
                        lambda doc, formato="PDF", **k: (b"%PDF-1.3 x", "julgado.pdf"))
    import json as _j
    out = _j.loads(server.rt_baixar_pdf("https://rt/doc?docguid=X", destino=str(tmp_path)))
    assert out["bytes"] == len(b"%PDF-1.3 x")
    assert (tmp_path / "julgado.pdf").read_bytes().startswith(b"%PDF")


def test_rt_baixar_pdf_vazio():
    assert "invalido" in server.rt_baixar_pdf("").lower()
```

- [ ] **Step 6: Run to verify fail**

Run: `uv run pytest tests/test_server_rt.py -q`
Expected: FAIL.

- [ ] **Step 7: Implement tool in `server.py`**

```python
from .rt import delivery as rt_delivery

@mcp.tool()
def rt_baixar_pdf(doc_url: str, destino: str = "") -> str:
    """Baixa o PDF de um julgado RT (use a URL de rt_jurisprudencia_buscar)."""
    import os as _os, json as _json
    doc_url = (doc_url or "").strip()
    if not doc_url:
        return "Parametro invalido: doc_url obrigatoria."
    try:
        data, filename = rt_delivery.baixar_documento(doc_url, "PDF")
    except Exception as e:
        return _json.dumps({"status": "erro", "mensagem": str(e)}, ensure_ascii=False)
    pasta = destino.strip() or _os.path.join(
        _os.environ.get("THINKBOX_VAULT_PATH", ""), "Conhecimento", "Fontes", "Julgados", "RT", "_pdf")
    _os.makedirs(pasta, exist_ok=True)
    path = _os.path.join(pasta, filename)
    with open(path, "wb") as fh:
        fh.write(data)
    return _json.dumps({"status": "ok", "path": path, "bytes": len(data), "filename": filename}, ensure_ascii=False)
```

- [ ] **Step 8: Run to verify pass**

Run: `uv run pytest tests/test_rt_delivery.py tests/test_server_rt.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/juridico_mcp/rt/delivery.py src/juridico_mcp/server.py tests/test_rt_delivery.py tests/test_server_rt.py
git commit -m "feat(rt): rt_baixar_pdf via pipeline offload (porte, collection-agnostic)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `rt/captura_md.py` (porte) + `extrair_documento` (parser de julgado) + tool `rt_capturar_md` (sem gravação)

**Files:**
- Create: `src/juridico_mcp/rt/captura_md.py`
- Modify: `src/juridico_mcp/rt/jurisprudencia.py`, `src/juridico_mcp/server.py`
- Test: `tests/test_rt_captura.py`, `tests/test_server_rt.py`, `tests/fixtures/rt_juris_doc.html`

**Interfaces:**
- Consumes: `rt.cdp_session.RtCdpSession`; `markdownify`; `lxml`.
- Produces:
  - `rt.captura_md.{html_para_md(html)->str, _limpar_corpo(html)->str}`.
  - `rt.jurisprudencia.{_meta_do_corpo(html_corpo)->dict, extrair_documento(doc_url, *, cdp_url=None, timeout=45.0)->dict}` com `tribunal,classe,numero,relator,data_julgamento,data_publicacao,orgao_julgador,assunto,jrp,url,html_corpo`.
  - `server.rt_capturar_md(doc_url, gravar=True) -> str` (NESTA task `gravar` ignorado; sempre `{markdown}`).

- [ ] **Step 1: Port `rt/captura_md.py`**

Porte `busca-academica-mcp/src/busca_academica_mcp/captura_md.py`: `html_para_md(html)` (markdownify ATX, strip script/style, colapsa linhas) e `_limpar_corpo(html)` (lxml, remove elementos com classe contendo `relationship`). Reuse verbatim.

- [ ] **Step 2: Create fixture for julgado header**

`tests/fixtures/rt_juris_doc.html` (cabeçalho real mapeado ao vivo):
```html
<div id="docContent">
  <div class="content">
    <p>TRT-3.ª Reg. - Recurso Ordinário em Rito Sumaríssimo 0010198-10.2024.5.03.0079 - 6.ª Turma - j. 8/10/2024 - julgado por José Murilo de Morais - DEJT 10/10/2024 - Área do Direito: Trabalho</p>
    <div class="relationshipsTabs">Jurisprudência (3) Índice Vide</div>
    <p>RECORRENTE: SOL ... acórdão ...</p>
  </div>
</div>
```

- [ ] **Step 3: Write failing tests (parser de julgado + limpeza)**

```python
# tests/test_rt_captura.py
import pathlib
from juridico_mcp.rt import captura_md
from juridico_mcp.rt import jurisprudencia as j

FIX = pathlib.Path(__file__).parent / "fixtures" / "rt_juris_doc.html"


def test_limpar_corpo_remove_relationship():
    md = captura_md.html_para_md(captura_md._limpar_corpo(FIX.read_text(encoding="utf-8")))
    assert "RECORRENTE" in md
    assert "Jurisprudência (3)" not in md


def test_meta_do_corpo_extrai_campos_de_julgado():
    meta = j._meta_do_corpo(FIX.read_text(encoding="utf-8"))
    assert meta["numero"] == "0010198-10.2024.5.03.0079"
    assert meta["classe"] == "Recurso Ordinário em Rito Sumaríssimo"
    assert meta["relator"] == "José Murilo de Morais"
    assert meta["data_julgamento"] == "8/10/2024"
    assert "Trabalho" in meta["assunto"]
    assert meta["orgao_julgador"] == "6.ª Turma"
```

- [ ] **Step 4: Run to verify fail**

Run: `uv run pytest tests/test_rt_captura.py -q`
Expected: FAIL.

- [ ] **Step 5: Implement `_meta_do_corpo` + `extrair_documento` in `jurisprudencia.py`**

```python
# adicionar a rt/jurisprudencia.py
from .cdp_session import RtCdpSession, cdp_url_or_raise
from . import captura_md as _cap

_HEADER_NUM = re.compile(r"([\d.\-/]{11,})")
_HEADER_DATA = re.compile(r"j\.\s*(\d{1,2}/\d{1,2}/\d{4})")
_HEADER_RELATOR = re.compile(r"julgado por\s+([^-]+?)\s*-")
_HEADER_TURMA = re.compile(r"-\s*([^-]*?Turma)\s*-")
_HEADER_AREA = re.compile(r"Área do Direito:\s*([^-\n]+)")
_DOCCONTENT_JS = "(()=>{const e=document.querySelector('#docContent');return e?e.innerHTML:'__NO_DOC__';})()"
_TRIBUNAL_JS = "(()=>{const h=document.querySelector('h1.hTitle');return h?h.textContent.trim():'';})()"


def _meta_do_corpo(html_corpo: str) -> dict:
    texto = _cap.html_para_md(_cap._limpar_corpo(html_corpo))
    primeira = next((l for l in texto.splitlines() if l.strip()), "")
    numero = (_HEADER_NUM.search(primeira) or _re_none()).group(1) if _HEADER_NUM.search(primeira) else ""
    # classe = trecho entre o tribunal-abrev e o número
    classe = ""
    if numero:
        antes = primeira.split(numero)[0]
        partes = antes.split(" - ")
        if len(partes) >= 2:
            classe = partes[-1].strip(" -")
    m_data = _HEADER_DATA.search(primeira)
    m_rel = _HEADER_RELATOR.search(primeira)
    m_turma = _HEADER_TURMA.search(primeira)
    m_area = _HEADER_AREA.search(primeira)
    return {
        "numero": numero,
        "classe": classe,
        "relator": m_rel.group(1).strip() if m_rel else "",
        "data_julgamento": m_data.group(1) if m_data else "",
        "orgao_julgador": m_turma.group(1).strip() if m_turma else "",
        "assunto": m_area.group(1).strip() if m_area else "",
    }


def extrair_documento(doc_url, *, cdp_url=None, timeout=45.0) -> dict:
    url = cdp_url_or_raise(cdp_url)
    with RtCdpSession(url, timeout=timeout) as s:
        s.navigate(doc_url); s.wait_ready(extra=2.0)
        corpo = s.evaluate(_DOCCONTENT_JS)
        tribunal = s.evaluate(_TRIBUNAL_JS) or ""
    if corpo == "__NO_DOC__" or not isinstance(corpo, str):
        raise RuntimeError("RT: #docContent ausente (layout mudou ou doc sem corpo).")
    import urllib.parse as _u
    qs = _u.parse_qs(_u.urlparse(doc_url).query)
    corpo_limpo = _cap._limpar_corpo(corpo)
    meta = _meta_do_corpo(corpo)
    return {
        "url": doc_url, "tribunal": tribunal, "jrp": (qs.get("jrp") or [None])[0],
        "html_corpo": corpo_limpo, **meta,
    }
```
> Não use `_re_none` — substitua a linha de `numero` por:
> ```python
> m_num = _HEADER_NUM.search(primeira); numero = m_num.group(1) if m_num else ""
> ```
> (Remova o helper inexistente; o teste exige `numero == "0010198-10.2024.5.03.0079"`.)

- [ ] **Step 6: Run to verify pass (captura + meta)**

Run: `uv run pytest tests/test_rt_captura.py -q`
Expected: PASS.

- [ ] **Step 7: Write failing test for tool (no-write)**

```python
# tests/test_server_rt.py — adicionar
def test_rt_capturar_md_retorna_markdown(monkeypatch):
    monkeypatch.setattr(server.rt_juris, "extrair_documento", lambda doc, **k: {
        "url": doc, "tribunal": "TRT-3", "numero": "001", "classe": "RO",
        "relator": "Morais", "data_julgamento": "8/10/2024", "data_publicacao": "",
        "orgao_julgador": "6.ª Turma", "assunto": "Trabalho", "jrp": "JRP\\2024\\1",
        "html_corpo": "<div id='docContent'><p>acórdão <b>x</b></p></div>"})
    import json as _j
    out = _j.loads(server.rt_capturar_md("https://rt/doc?docguid=X", gravar=False))
    assert "**x**" in out["markdown"]
```

- [ ] **Step 8: Run to verify fail**

Run: `uv run pytest tests/test_server_rt.py -q`
Expected: FAIL.

- [ ] **Step 9: Implement tool (no-write) in `server.py`**

```python
@mcp.tool()
def rt_capturar_md(doc_url: str, gravar: bool = True) -> str:
    """Captura um julgado RT como Markdown (a partir do HTML do documento)."""
    import json as _json
    doc_url = (doc_url or "").strip()
    if not doc_url:
        return "Parametro invalido: doc_url obrigatoria."
    try:
        doc = rt_juris.extrair_documento(doc_url)
        from .rt import captura_md as _cap
        corpo_md = _cap.html_para_md(doc["html_corpo"])
        markdown = corpo_md  # montagem final/gravação entram na Task 6
    except Exception as e:
        return _json.dumps({"status": "erro", "mensagem": str(e)}, ensure_ascii=False)
    return _json.dumps({"status": "ok", "markdown": markdown}, ensure_ascii=False)
```

- [ ] **Step 10: Run to verify pass**

Run: `uv run pytest tests/test_rt_captura.py tests/test_server_rt.py -q`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add src/juridico_mcp/rt/captura_md.py src/juridico_mcp/rt/jurisprudencia.py src/juridico_mcp/server.py tests/test_rt_captura.py tests/test_server_rt.py tests/fixtures/rt_juris_doc.html
git commit -m "feat(rt): captura de julgado (HTML->MD) + parser de cabeçalho

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `rt/vault.py` (nota `julgado`) + ligar `rt_capturar_md(gravar=True)`

**Files:**
- Create: `src/juridico_mcp/rt/vault.py`
- Modify: `src/juridico_mcp/server.py`
- Test: `tests/test_rt_vault.py`, `tests/test_server_rt.py`

**Interfaces:**
- Consumes: `rt.captura_md.html_para_md`.
- Produces:
  - `rt.vault.{slug_ascii(s, max_len=60)->str, montar_frontmatter(meta)->str, escrever_julgado(meta, corpo_md, *, base_path=None, pdf_local="")->str}`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_rt_vault.py
import pathlib
from juridico_mcp.rt import vault


def test_slug_ascii():
    assert vault.slug_ascii("0010198-10.2024.5.03.0079") == "0010198-10-2024-5-03-0079"


def test_montar_frontmatter_julgado_required_e_escape():
    fm = vault.montar_frontmatter({"tribunal": "TRT: 3", "classe": "RO", "numero": "001",
                                   "relator": "Morais", "data_julgamento": "8/10/2024",
                                   "assunto": "Trabalho", "jrp": "JRP\\2024\\1", "url": "https://rt/x"})
    assert "noteType: julgado" in fm
    assert 'tribunal: "TRT: 3"' in fm   # escapado/aspas (não quebra YAML)
    assert "classe:" in fm and "numero:" in fm
    assert 'fonte: "RT Online"' in fm


def test_escrever_julgado_required_ausente_levanta(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        vault.escrever_julgado({"tribunal": "", "classe": "", "numero": ""}, "corpo", base_path=str(tmp_path))


def test_escrever_julgado_grava(tmp_path):
    p = pathlib.Path(vault.escrever_julgado(
        {"tribunal": "TRT-3", "classe": "RO", "numero": "0010198-10.2024.5.03.0079",
         "relator": "Morais", "data_julgamento": "8/10/2024", "url": "https://rt/x", "jrp": "JRP\\2024\\1"},
        "corpo md", base_path=str(tmp_path)))
    assert p.exists() and p.parent.as_posix().endswith("Conhecimento/Fontes/Julgados/RT")
    txt = p.read_text(encoding="utf-8")
    assert txt.startswith("---\n") and "noteType: julgado" in txt and "corpo md" in txt
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_rt_vault.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `rt/vault.py`**

```python
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
    return str(v).replace('"', '\\"')


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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_rt_vault.py -q`
Expected: PASS.

- [ ] **Step 5: Write failing test wiring gravar=True**

```python
# tests/test_server_rt.py — adicionar
def test_rt_capturar_md_grava(monkeypatch, tmp_path):
    monkeypatch.setattr(server.rt_juris, "extrair_documento", lambda doc, **k: {
        "url": doc, "tribunal": "TRT-3", "numero": "0010198-10.2024.5.03.0079", "classe": "RO",
        "relator": "Morais", "data_julgamento": "8/10/2024", "data_publicacao": "",
        "orgao_julgador": "6.ª Turma", "assunto": "Trabalho", "jrp": "JRP\\2024\\1",
        "html_corpo": "<div id='docContent'><p>acórdão</p></div>"})
    monkeypatch.setenv("THINKBOX_VAULT_PATH", str(tmp_path))
    import json as _j
    out = _j.loads(server.rt_capturar_md("https://rt/doc?docguid=X", gravar=True))
    assert out["status"] == "ok" and out["path"].endswith(".md")
    import pathlib
    assert pathlib.Path(out["path"]).read_text(encoding="utf-8").startswith("---\n")
```

- [ ] **Step 6: Run to verify fail**

Run: `uv run pytest tests/test_server_rt.py -q`
Expected: FAIL (gravar=True ainda retorna markdown).

- [ ] **Step 7: Wire gravação in `rt_capturar_md`**

Em `server.py`, substituir o retorno final de `rt_capturar_md`:
```python
        if not gravar:
            return _json.dumps({"status": "ok", "markdown": markdown}, ensure_ascii=False)
        from .rt import vault as rt_vault
        try:
            path = rt_vault.escrever_julgado(doc, corpo_md)
        except Exception as e:
            return _json.dumps({"status": "erro", "mensagem": f"falha ao gravar nota: {e}"}, ensure_ascii=False)
        return _json.dumps({"status": "ok", "path": path}, ensure_ascii=False)
```

- [ ] **Step 8: Run to verify pass**

Run: `uv run pytest tests/test_rt_vault.py tests/test_server_rt.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/juridico_mcp/rt/vault.py src/juridico_mcp/server.py tests/test_rt_vault.py tests/test_server_rt.py
git commit -m "feat(rt): grava julgado capturado como nota na vault

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: `listar_fontes` + README + env

**Files:**
- Modify: `src/juridico_mcp/server.py`, `README.md`
- Test: `tests/test_server_rt.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_server_rt.py — adicionar
def test_listar_fontes_menciona_rt():
    txt = server.listar_fontes()
    assert "rt_jurisprudencia_buscar" in txt and "rt_capturar_md" in txt and "rt_baixar_pdf" in txt
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_server_rt.py::test_listar_fontes_menciona_rt -q`
Expected: FAIL.

- [ ] **Step 3: Update `listar_fontes`**

Adicionar ao texto de `listar_fontes` uma seção RT (server-only): lista `rt_jurisprudencia_buscar(livre/numero/relator/tribunais/ano/data_de/data_ate)`, `rt_baixar_pdf(doc_url)`, `rt_capturar_md(doc_url, gravar)`, e a nota de que exigem `RT_CDP_URL` (Chrome dedicado) + `THINKBOX_VAULT_PATH` (captura), cobrindo Jurisprudência RT premium.

- [ ] **Step 4: Update README**

Documentar as 3 tools RT, params, `RT_CDP_URL`/`THINKBOX_VAULT_PATH` server-side, escopo Jurisprudência (legislação/súmulas depois), e a natureza server-only (degradam sem CDP; httpx intactas).

- [ ] **Step 5: Full suite**

Run: `uv run pytest -q`
Expected: PASS (suíte inteira).

- [ ] **Step 6: Commit**

```bash
git add src/juridico_mcp/server.py README.md tests/test_server_rt.py
git commit -m "docs(rt): documenta tools RT jurisprudência + env

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Smoke ao vivo (server-only)

**Files:** nenhum (validação).

- [ ] **Step 1: busca avançada**

```bash
cd /Users/gustavo/Developer/juridico-mcp-server
RT_CDP_URL=http://127.0.0.1:9222 uv run python -c "
import asyncio
from juridico_mcp import server
print(asyncio.run(server.rt_jurisprudencia_buscar(livre='dano moral', ano='2024'))[:600])
"
```
Expected: ≥1 julgado com número/tribunal/relator/data.

- [ ] **Step 2: PDF + captura de um doc_url real**

```bash
RT_CDP_URL=http://127.0.0.1:9222 THINKBOX_VAULT_PATH=/tmp/vaultjuris uv run python -c "
import asyncio, re
from juridico_mcp import server
out = asyncio.run(server.rt_jurisprudencia_buscar(livre='dano moral', ano='2024'))
doc = re.search(r'(https://\S+docguid=\S+)', out).group(1)
print(server.rt_baixar_pdf(doc, destino='/tmp'))
print(server.rt_capturar_md(doc, gravar=True))
"
file /tmp/*.pdf; find /tmp/vaultjuris -name '*.md' -exec head -14 {} \;
```
Expected: PDF válido; nota `julgado` em `.../Julgados/RT/` com frontmatter (tribunal/classe/numero) e corpo limpo. AJUSTAR parser se o cabeçalho real divergir da fixture (lição da Doutrina: o smoke pega o que fixtures sintéticas não veem).

- [ ] **Step 3: Epílogo** — registrar resultado; se verde, finalizar branch (PR).

---

## Self-Review (preenchido)

**Cobertura do spec:** busca avançada → Task 3; PDF → Task 4; captura MD→julgado → Tasks 5-6; camada CDP sobre cdp-scaffold → Task 1; auth/session → Task 2; pouso `julgado` → Task 6; docs/env → Task 7; smoke → Task 8. Datas (year/exact/between, dd/mm/aaaa) em `montar_campos` (Task 3). Legislação/súmulas e filtros de corte/GR-RR: fora de escopo (Global Constraints).

**Placeholders:** sem "TBD/TODO"; código real em cada passo. Ports apontam o arquivo-fonte validado + delta de adaptação. Único ponto a confirmar ao vivo: assinaturas exatas de cdp-scaffold (Task 1 Step 2 instrui anotar antes de implementar) e o cabeçalho real do julgado (Task 8 ajusta o parser se divergir).

**Consistência de tipos:** `RtCdpSession`/`build_fetch_js`/`cdp_url_or_raise`/`RtSessionExpired` (Task 1) usados em 2/4/5; `run_search_form` (2) em 3; `parse_resultados`/`montar_campos`/`buscar`/`extrair_documento`/`_meta_do_corpo` (3,5); `delivery.baixar_documento`/`_parse_status_xml`/`_normalizar_filename` (4); `captura_md.html_para_md`/`_limpar_corpo` (5); `vault.escrever_julgado` (6); `server.rt_juris`/`rt_delivery` aliases consistentes.
