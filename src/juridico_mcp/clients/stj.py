"""
Client: STJ SCON (Sistema de Consulta de Jurisprudencia)
Fonte: https://scon.stj.jus.br/SCON/
Tecnica: Browser automation via nodriver (Cloudflare protege o site)
Dados: Acordaos, decisoes monocraticas, inteiro teor

Referencia: pacote R jjesusfilho/stj (estrategia de 2 passos AJAX+toc.jsp).
O STJ esta atras de Cloudflare managed challenge, entao usamos nodriver
para resolver o challenge e submeter o formulario via browser real.
"""

import re
import unicodedata
import asyncio
from bs4 import BeautifulSoup
from typing import List, Optional
from ..shared import ResultadoJuridico, limpar_html

STJ_BASE = "https://scon.stj.jus.br/SCON"

# Timeouts de POLLING (segundos): aguarda a condicao em vez de sleep fixo.
# Sleeps fixos curtos capturavam a pagina ainda em branco -> "0 resultados".
_CF_WAIT = 15      # ate o form de busca aparecer (Cloudflare/JS)
_RESULT_WAIT = 20  # ate os resultados (div.documento) carregarem


async def _poll(page, expr_js: str, timeout: float, intervalo: float = 0.5):
    """Polla expr_js ate retornar truthy ou estourar o timeout; devolve o ultimo valor.

    Robustez sobre sleep fixo: encerra assim que a condicao e satisfeita (rapido
    quando pronto) e tem teto previsivel quando nao ha resultado."""
    ultimo = None
    import asyncio as _asyncio
    for _ in range(max(1, int(timeout / intervalo))):
        try:
            ultimo = await page.evaluate(expr_js)
        except Exception:
            ultimo = None
        if ultimo:
            return ultimo
        await _asyncio.sleep(intervalo)
    return ultimo


def _normalizar_busca(texto: str) -> str:
    """Normaliza termo de busca: MAIUSCULO e sem acentos (padrao do STJ/SCON)."""
    # Remover acentos
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return sem_acento.upper()


class STJClient:
    """Client para STJ SCON jurisprudencia via browser."""

    def buscar(
        self,
        busca: str,
        base: str = "ACOR",
        data_inicial: str = "",
        data_final: str = "",
        max_resultados: int = 10,
    ) -> List[ResultadoJuridico]:
        """
        Busca jurisprudencia no STJ SCON (sync wrapper).
        Use buscar_async() quando ja estiver dentro de um event loop.
        """
        return asyncio.run(
            self.buscar_async(busca, base, data_inicial, data_final, max_resultados)
        )

    async def buscar_async(
        self,
        busca: str,
        base: str = "ACOR",
        data_inicial: str = "",
        data_final: str = "",
        max_resultados: int = 10,
    ) -> List[ResultadoJuridico]:
        """
        Busca jurisprudencia no STJ SCON (async, para uso dentro de event loop).

        Args:
            busca: Termo de busca livre
            base: ACOR (acordaos) ou MONO (monocraticas)
            data_inicial: Formato DD/MM/AAAA
            data_final: Formato DD/MM/AAAA
            max_resultados: Limite de resultados
        """
        return await self._buscar_async(busca, base, data_inicial, data_final, max_resultados)

    async def _buscar_async(
        self,
        busca: str,
        base: str,
        data_inicial: str,
        data_final: str,
        max_resultados: int,
    ) -> List[ResultadoJuridico]:
        """Busca via browser para bypass de Cloudflare."""
        import nodriver as uc

        base_upper = base.upper()
        b_param = "DTXT" if base_upper == "MONO" else base_upper

        # Normalizar busca: MAIUSCULO sem acentos (padrao SCON, ref: pacote R)
        busca_normalizada = _normalizar_busca(busca)

        # Montar filtro de data
        data_filtro = ""
        if data_inicial or data_final:
            di = re.sub(r"\D", "", data_inicial) if data_inicial else ""
            df = re.sub(r"\D", "", data_final) if data_final else ""
            partes = []
            if di:
                partes.append(f"@DTPB >= {di}")
            if df:
                partes.append(f"@DTPB <= {df}")
            data_filtro = " E ".join(partes)

        browser = await uc.start(headless=False)
        try:
            # Navegar para a pagina principal (resolve Cloudflare)
            page = await browser.get(f"{STJ_BASE}/")
            # Polling do form (em vez de sleep fixo): so prossegue quando o campo existe.
            tem_form = await _poll(
                page,
                "!!document.getElementById('frmConsulta') "
                "&& !!document.querySelector('input[name=\"livre\"]')",
                _CF_WAIT,
            )
            if not tem_form:
                raise RuntimeError(
                    "STJ SCON: formulario de busca nao carregou (Cloudflare/layout/timeout)."
                )

            # Preencher formulario e submeter via JavaScript
            # O form frmConsulta tem campos hidden: livre, b, data, etc.
            js_busca = busca_normalizada.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            js_data = data_filtro.replace("\\", "\\\\").replace("'", "\\'")
            num_docs = min(max_resultados, 50)

            await page.evaluate(f'''
                (function() {{
                    var form = document.getElementById('frmConsulta');
                    form.querySelector('input[name="livre"]').value = '{js_busca}';
                    // Campos de data (dtpb1, dtpb2) para filtro
                    var dtpb1 = form.querySelector('input[name="dtpb1"]');
                    var dtpb2 = form.querySelector('input[name="dtpb2"]');
                    if (dtpb1) dtpb1.value = '{data_inicial.replace("'", "")}';
                    if (dtpb2) dtpb2.value = '{data_final.replace("'", "")}';
                    form.submit();
                }})();
            ''')
            # Polling dos resultados: encerra quando div.documento aparece OU quando a
            # pagina sinaliza busca sem resultados (evita capturar a pagina em branco).
            await _poll(
                page,
                "document.querySelectorAll('div.documento').length > 0 "
                "|| /n[ãa]o encontrou|nenhum documento|0 documento/i.test("
                "document.body ? document.body.innerText : '')",
                _RESULT_WAIT,
            )

            # Obter HTML da pagina de resultados
            content = await page.get_content()

            return self._parse_resultados(content, base_upper, max_resultados)
        finally:
            browser.stop()

    def _parse_resultados(
        self, html_text: str, base: str, max_resultados: int,
    ) -> List[ResultadoJuridico]:
        """Parseia HTML de resultados do STJ."""
        resultados: List[ResultadoJuridico] = []
        soup = BeautifulSoup(html_text, "html.parser")

        # Blocos de resultado: div.documento
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

        # Extrair campos via div.paragrafoBRS > docTitulo + docTexto
        paragrafos = item.find_all(class_="paragrafoBRS")
        for p in paragrafos:
            titulo_el = p.find(class_="docTitulo")
            texto_el = p.find(class_="docTexto")
            if not texto_el:
                continue

            titulo = titulo_el.get_text(strip=True) if titulo_el else ""
            texto = texto_el.get_text(strip=True)

            if "Processo" in titulo or (not titulo and not resultado.numero):
                # Extrair classe e numero do processo
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
                    # Extrair data do texto (ex: "DJe 17/03/2021")
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
