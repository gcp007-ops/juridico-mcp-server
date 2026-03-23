"""
Client: CJF Jurisprudencia Unificada
Fonte: https://jurisprudencia.cjf.jus.br/unificada/
Tecnica: Scraping JSF (ViewState) via POST
Dados: Acordaos STF, STJ, TRF1-TRF5, TNU
"""

import re
import html
import httpx
from urllib.parse import urlencode
from tenacity import retry, wait_exponential, stop_after_attempt
from typing import List, Optional
from ..shared import ResultadoJuridico, limpar_html

CJF_URL = "https://jurisprudencia.cjf.jus.br/unificada/index.xhtml"

HEADERS_GET = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

HEADERS_POST = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Faces-Request": "partial/ajax",
    "X-Requested-With": "XMLHttpRequest",
}

BASES_CJF = {
    "STF": "Supremo Tribunal Federal",
    "STJ": "Superior Tribunal de Justica",
    "TNU": "Turma Nacional de Uniformizacao",
    "TRF1": "Tribunal Regional Federal da 1a Regiao",
    "TRF2": "Tribunal Regional Federal da 2a Regiao",
    "TRF3": "Tribunal Regional Federal da 3a Regiao",
    "TRF4": "Tribunal Regional Federal da 4a Regiao",
    "TRF5": "Tribunal Regional Federal da 5a Regiao",
}


class CJFClient:
    """Client para portal CJF Jurisprudencia Unificada."""

    def __init__(self) -> None:
        self._client = httpx.Client(
            headers=HEADERS_GET,
            timeout=30.0,
            follow_redirects=True,
        )
        self._viewstate: Optional[str] = None

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def _obter_viewstate(self) -> str:
        """Obtem ViewState da pagina inicial JSF."""
        resp = self._client.get(CJF_URL)
        resp.raise_for_status()

        match = re.search(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', resp.text)
        if match:
            self._viewstate = match.group(1)
            return self._viewstate

        match = re.search(r'ViewState:([^"]+)"', resp.text)
        if match:
            self._viewstate = match.group(1)
            return self._viewstate

        raise RuntimeError("ViewState nao encontrado na pagina CJF")

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def buscar(
        self,
        busca: str,
        bases: str = "STJ",
        max_resultados: int = 10,
    ) -> List[ResultadoJuridico]:
        """
        Busca jurisprudencia no portal CJF.

        Args:
            busca: Termo de busca (sintaxe CJF: E, OU, NAO, ADJ, PROX)
            bases: Tribunais separados por virgula (STF,STJ,TNU,TRF1..TRF5)
            max_resultados: Limite de resultados (1-50)
        """
        if not self._viewstate:
            self._obter_viewstate()

        lista_bases = [b.strip().upper() for b in bases.split(",")]

        # Montar form data JSF — usa lista de tuplas para suportar
        # multiplos valores de formulario:j_idt51 (tribunais)
        form_data = [
            ("javax.faces.partial.ajax", "true"),
            ("javax.faces.source", "formulario:actPesquisar"),
            ("javax.faces.partial.execute", "@all"),
            ("javax.faces.partial.render", "formulario:resultado"),
            ("formulario:actPesquisar", "formulario:actPesquisar"),
            ("formulario", "formulario"),
            ("formulario:textoLivre", busca),
        ]

        # Adicionar bases selecionadas (multiplos valores)
        for base in lista_bases:
            if base in BASES_CJF:
                form_data.append(("formulario:j_idt51", base))

        form_data.append(("javax.faces.ViewState", self._viewstate or ""))

        # Usar urlencode para suportar chaves duplicadas
        encoded = urlencode(form_data)
        resp = self._client.post(
            CJF_URL,
            content=encoded.encode("utf-8"),
            headers=HEADERS_POST,
        )
        resp.raise_for_status()

        # Atualizar ViewState da resposta
        match = re.search(r'ViewState[^>]*>([^<]+)<', resp.text)
        if match:
            self._viewstate = match.group(1)

        return self._parse_resultados(resp.text, max_resultados)

    def _parse_resultados(self, xml_text: str, max_resultados: int) -> List[ResultadoJuridico]:
        """Parseia resposta AJAX JSF usando padrao tabelaDocumentos."""
        resultados: List[ResultadoJuridico] = []

        content = html.unescape(xml_text)

        # Extrair CDATA do XML JSF
        cdata_matches = re.findall(r'<!\[CDATA\[(.*?)\]\]>', content, re.DOTALL)
        if not cdata_matches:
            return resultados

        content = "".join(cdata_matches)

        # Encontrar indices de documentos (tabelaDocumentos:N:...)
        doc_indices = sorted(set(re.findall(r'tabelaDocumentos:(\d+):', content)), key=int)

        for idx in doc_indices[:max_resultados]:
            doc = self._extrair_documento(content, idx)
            if doc and (doc.ementa or doc.numero):
                resultados.append(doc)

        return resultados

    def _extrair_campo(self, content: str, idx: str, label_re: str) -> str:
        """Extrai valor de um campo pelo label regex dentro de um documento."""
        pattern = (
            rf'tabelaDocumentos:{idx}:.*?'
            rf'label_pontilhada[^>]*>\s*{label_re}\s*</span>'
            rf'.*?<td[^>]*>(.*?)</td>'
        )
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            return ""
        valor = re.sub(r'<[^>]+>', '', match.group(1)).strip()
        valor = re.sub(r'\s+', ' ', valor)
        return valor

    def _extrair_documento(self, content: str, idx: str) -> Optional[ResultadoJuridico]:
        """Extrai campos de um documento individual pelo indice."""
        resultado = ResultadoJuridico(fonte="CJF")

        # Campos com label_pontilhada — labels flexiveis para acentos/variantes
        campos = [
            ("numero",   [r"N[uú]mero", r"Processo"]),
            ("classe",   [r"Classe"]),
            ("relator",  [r"Relator(?:\(a\))?", r"Relator"]),
            ("orgao",    [r"[OÓ]rg[aã]o\s+[Jj]ulgador", r"[OÓ]rg[aã]o"]),
            ("data",     [r"Data(?!\s+da\s+publica)"]),
            ("data_pub", [r"Data\s+da\s+publica[cç][aã]o"]),
        ]

        for campo, label_variants in campos:
            valor = ""
            for label_re in label_variants:
                valor = self._extrair_campo(content, idx, label_re)
                if valor:
                    break

            if not valor:
                continue

            if campo == "numero":
                resultado.numero = valor
            elif campo == "classe":
                resultado.tipo = valor
            elif campo == "relator":
                resultado.relator = valor
            elif campo == "orgao":
                resultado.orgao = valor
            elif campo == "data":
                resultado.data = valor
            elif campo == "data_pub" and not resultado.data:
                resultado.data = valor

        # Decisao
        decisao = self._extrair_campo(content, idx, r"Decis[aã]o")
        if decisao:
            resultado.decisao = decisao

        # Ementa (painel_ementa)
        ementa_pattern = re.compile(
            rf'painel_ementa-[^"]*tabelaDocumentos:{idx}[^"]*"[^>]*>(.*?)</div>',
            re.DOTALL,
        )
        ementa_match = ementa_pattern.search(content)
        if not ementa_match:
            # Fallback: ementas por ordem de indice
            ementa_all = re.findall(r'painel_ementa-([^"]+)"[^>]*>(.*?)</div>', content, re.DOTALL)
            idx_int = int(idx)
            if idx_int < len(ementa_all):
                ementa_raw = ementa_all[idx_int][1]
                ementa = re.sub(r'<[^>]+>', '', ementa_raw).strip()
                ementa = re.sub(r'\s+', ' ', ementa)
                if len(ementa) > 50:
                    resultado.ementa = ementa
        else:
            ementa_raw = ementa_match.group(1)
            ementa = re.sub(r'<[^>]+>', '', ementa_raw).strip()
            ementa = re.sub(r'\s+', ' ', ementa)
            resultado.ementa = ementa

        if not resultado.tipo:
            resultado.tipo = "Jurisprudencia CJF"

        return resultado


# Singleton
_client: Optional[CJFClient] = None


def get_client() -> CJFClient:
    global _client
    if _client is None:
        _client = CJFClient()
    return _client
