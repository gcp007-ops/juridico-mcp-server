"""
Client: STJ SCON (Sistema de Consulta de Jurisprudencia)
Fonte: https://scon.stj.jus.br/SCON/
Tecnica: aba de fundo no Chrome dedicado via CDP (server-only). O SCON esta atras
de Cloudflare managed challenge; o navegador real (logado, :9222) resolve o
challenge sozinho em ~poucos segundos — por isso NAO abrimos uma janela nodriver
(o pop atrapalhava o trabalho na maquina). Mesma plumbing de RT/Jusbrasil.
Dados: Acordaos, decisoes monocraticas.

Referencia: pacote R jjesusfilho/stj (estrategia AJAX+toc.jsp).
"""

import json
import re
import time
import unicodedata
from bs4 import BeautifulSoup
from typing import List, Optional

from ..shared import ResultadoJuridico, limpar_html
from ..cdp_common import CdpSession, cdp_url_or_raise, DEFAULT_TIMEOUT

STJ_BASE = "https://scon.stj.jus.br/SCON"
STJ_CDP_ENV = "STJ_CDP_URL"
STJ_CDP_DEFAULT = "http://127.0.0.1:9222"  # mesmo Chrome dedicado de RT/Jusbrasil

# Timeouts de POLLING (segundos): aguarda a condicao em vez de sleep fixo.
_CF_WAIT = 20      # ate o form aparecer (Cloudflare auto-resolve em ~6s no browser real)
_RESULT_WAIT = 20  # ate os resultados (div.documento) carregarem

_FORM_PRONTO_JS = (
    "!!document.getElementById('frmConsulta') "
    "&& !!document.querySelector('input[name=\"livre\"]')"
)
_RESULTADO_PRONTO_JS = (
    "document.querySelectorAll('div.documento').length > 0 "
    "|| /n[ãa]o encontrou|nenhum documento|0 documento/i.test("
    "document.body ? document.body.innerText : '')"
)
_OUTER_HTML_JS = "document.documentElement.outerHTML"


def _poll(session, expr_js: str, timeout: float, intervalo: float = 0.5):
    """Polla expr_js (via session.evaluate) ate truthy ou timeout; devolve o ultimo
    valor. Encerra assim que a condicao e satisfeita (rapido quando pronto) e tem
    teto previsivel quando nao ha resultado — robustez sobre sleep fixo."""
    ultimo = None
    for _ in range(max(1, int(timeout / intervalo))):
        try:
            ultimo = session.evaluate(expr_js)
        except Exception:
            ultimo = None
        if ultimo:
            return ultimo
        time.sleep(intervalo)
    return ultimo


def _normalizar_busca(texto: str) -> str:
    """Normaliza termo de busca: MAIUSCULO e sem acentos (padrao do STJ/SCON)."""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.upper()


def _submit_js(livre: str, b: str, data_inicial: str, data_final: str) -> str:
    """JS que preenche o frmConsulta (livre/base/datas) e submete. Valores via
    json.dumps (escape seguro)."""
    return f"""(function(){{
      var f=document.getElementById('frmConsulta');
      var L=f.querySelector('input[name="livre"]'); if(L) L.value={json.dumps(livre)};
      var B=f.querySelector('[name="b"]'); if(B) B.value={json.dumps(b)};
      var d1=f.querySelector('input[name="dtpb1"]'); if(d1) d1.value={json.dumps(data_inicial)};
      var d2=f.querySelector('input[name="dtpb2"]'); if(d2) d2.value={json.dumps(data_final)};
      f.submit();
    }})()"""


class STJClient:
    """Client para STJ SCON jurisprudencia via aba de fundo CDP (sem janela)."""

    def buscar(
        self,
        busca: str,
        base: str = "ACOR",
        data_inicial: str = "",
        data_final: str = "",
        max_resultados: int = 10,
    ) -> List[ResultadoJuridico]:
        """Busca jurisprudencia no STJ SCON via aba de fundo no Chrome dedicado.

        Args:
            busca: Termo de busca livre.
            base: ACOR (acordaos) ou MONO (monocraticas).
            data_inicial/data_final: DD/MM/AAAA (filtro por data de julgamento).
            max_resultados: Limite de resultados.
        """
        base_upper = base.upper()
        b_param = "DTXT" if base_upper == "MONO" else base_upper
        busca_norm = _normalizar_busca(busca)
        cdp_url = cdp_url_or_raise(env_var=STJ_CDP_ENV, default=STJ_CDP_DEFAULT, fonte="STJ")

        with CdpSession(cdp_url, timeout=DEFAULT_TIMEOUT) as s:
            s.navigate(f"{STJ_BASE}/")
            # Polla o form (Cloudflare auto-resolve no browser real) em vez de sleep fixo.
            if not _poll(s, _FORM_PRONTO_JS, _CF_WAIT):
                raise RuntimeError(
                    "STJ SCON: formulario de busca nao carregou "
                    "(Cloudflare/sessao/timeout no Chrome dedicado)."
                )
            s.evaluate(_submit_js(busca_norm, b_param, data_inicial, data_final))
            # Polla os resultados; encerra cedo se a pagina sinalizar busca vazia.
            _poll(s, _RESULTADO_PRONTO_JS, _RESULT_WAIT)
            html_text = s.evaluate(_OUTER_HTML_JS)

        if not isinstance(html_text, str):
            return []
        return self._parse_resultados(html_text, base_upper, max_resultados)

    async def buscar_async(
        self,
        busca: str,
        base: str = "ACOR",
        data_inicial: str = "",
        data_final: str = "",
        max_resultados: int = 10,
    ) -> List[ResultadoJuridico]:
        """Wrapper async: roda o fluxo CDP (bloqueante) numa thread para nao travar
        o event loop do servidor MCP."""
        import asyncio
        return await asyncio.to_thread(
            self.buscar, busca, base, data_inicial, data_final, max_resultados
        )

    def _parse_resultados(
        self, html_text: str, base: str, max_resultados: int,
    ) -> List[ResultadoJuridico]:
        """Parseia HTML de resultados do STJ."""
        resultados: List[ResultadoJuridico] = []
        soup = BeautifulSoup(html_text, "html.parser")

        items = soup.find_all("div", class_="documento")
        for item in items[:max_resultados]:
            try:
                r = self._parse_item(item, base)
                if r and (r.ementa or r.numero):
                    resultados.append(r)
            except Exception:
                continue
        return resultados

    def _parse_item(self, item: BeautifulSoup, base: str) -> Optional[ResultadoJuridico]:
        """Parseia um bloco div.documento do STJ."""
        resultado = ResultadoJuridico(
            fonte="STJ",
            tipo="Acordao" if base == "ACOR" else "Decisao Monocratica",
        )

        paragrafos = item.find_all(class_="paragrafoBRS")
        for p in paragrafos:
            titulo_el = p.find(class_="docTitulo")
            texto_el = p.find(class_="docTexto")
            if not texto_el:
                continue

            titulo = titulo_el.get_text(strip=True) if titulo_el else ""
            texto = texto_el.get_text(strip=True)

            if "Processo" in titulo or (not titulo and not resultado.numero):
                proc_match = re.search(
                    r'((?:REsp|AgRg|AREsp|RHC|HC|RMS|CC|EDcl|AgInt|Pet|RvCr|'
                    r'EREsp|MS|Rcl|AR|SD|IDC|MI|IF|SE|CR|EAREsp|RCD)\s+[\d/.]+)',
                    texto,
                )
                if proc_match:
                    resultado.numero = proc_match.group(1).strip()
                else:
                    cnj_match = re.search(r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}', texto)
                    if cnj_match:
                        resultado.numero = cnj_match.group()
                    elif texto and not resultado.numero:
                        resultado.numero = texto[:80]

            elif "Relator" in titulo:
                resultado.relator = texto

            elif "rgão Julgador" in titulo or "Orgão" in titulo or "Órgão" in titulo:
                resultado.orgao = texto

            elif "Data do Julgamento" in titulo:
                resultado.data = texto

            elif "Data da Publicação" in titulo or "Data da Publica" in titulo:
                if not resultado.data:
                    data_match = re.search(r'\d{2}/\d{2}/\d{4}', texto)
                    resultado.data = data_match.group() if data_match else texto

            elif "Ementa" in titulo:
                resultado.ementa = limpar_html(texto)

            elif "Acórdão" in titulo or "Acordão" in titulo:
                if not resultado.ementa:
                    resultado.ementa = limpar_html(texto)

        return resultado


# Singleton
_client: Optional[STJClient] = None


def get_client() -> STJClient:
    global _client
    if _client is None:
        _client = STJClient()
    return _client
