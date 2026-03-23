"""
Client: BNP (Banco Nacional de Precedentes) via Pangea frontend
Fonte: https://pangeabnp.pdpj.jus.br/api/v1/precedentes
Tecnica: API publica POST JSON (sem autenticacao)
Dados: Precedentes qualificados com tese firmada

Baseado em georgemarmelstein/bnp-api (licenca MIT).
"""

import httpx
from tenacity import retry, wait_exponential, stop_after_attempt
from typing import List, Optional
from ..shared import ResultadoJuridico

BNP_API_URL = "https://pangeabnp.pdpj.jus.br/api/v1/precedentes"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

TIPOS_PRECEDENTES = {
    "RG": "Repercussao Geral",
    "RR": "Recurso Repetitivo",
    "SV": "Sumula Vinculante",
    "SUM": "Sumula",
    "IRDR": "Incidente de Resolucao de Demandas Repetitivas",
    "IAC": "Incidente de Assuncao de Competencia",
    "PUIL": "Pedido de Uniformizacao de Interpretacao de Lei",
}

# Sintaxe BNP: +termo (AND), -termo (NOT), "frase" (exata)
# NAO funcionam: E, OU, NAO, AND, OR, NOT, ADJ, PROX


class BNPClient:
    """Client para API publica do Pangea/BNP."""

    def __init__(self) -> None:
        self._client = httpx.Client(
            headers=HEADERS,
            timeout=30.0,
        )

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def buscar(
        self,
        busca: str,
        orgaos: str = "STF,STJ",
        tipos: str = "RG,RR,SV,SUM",
        max_resultados: int = 10,
    ) -> tuple[List[ResultadoJuridico], int]:
        """
        Busca precedentes no BNP.

        Args:
            busca: Query com sintaxe BNP (+termo, -termo, "frase")
            orgaos: Orgaos separados por virgula
            tipos: Tipos de precedente (RG,RR,SV,SUM,IRDR,IAC,PUIL)
            max_resultados: Limite (1-50)

        Returns:
            Tupla (resultados, total)
        """
        lista_orgaos = [o.strip().upper() for o in orgaos.split(",") if o.strip()]
        lista_tipos = [t.strip().upper() for t in tipos.split(",") if t.strip()]

        filtro = {
            "buscaGeral": busca,
            "todasPalavras": "",
            "quaisquerPalavras": "",
            "semPalavras": "",
            "trechoExato": "",
            "atualizacaoDesde": "",
            "atualizacaoAte": "",
            "cancelados": False,
            "ordenacao": "Text",
            "nr": "",
            "pagina": 1,
            "tamanhoPagina": min(max_resultados, 50),
            "orgaos": lista_orgaos,
            "tipos": lista_tipos,
        }

        resp = self._client.post(BNP_API_URL, json={"filtro": filtro})
        resp.raise_for_status()
        data = resp.json()

        total = data.get("total", 0)
        resultados = self._parse_resultados(data)
        return resultados, total

    def _parse_resultados(self, data: dict) -> List[ResultadoJuridico]:
        """Converte resposta BNP em ResultadoJuridico."""
        resultados: List[ResultadoJuridico] = []

        for r in data.get("resultados", []):
            partes_ementa = []

            questao = r.get("questao", "")
            if questao:
                partes_ementa.append(f"QUESTAO JURIDICA: {questao}")

            tese = r.get("tese", "")
            if tese:
                partes_ementa.append(f"TESE: {tese}")

            paradigmas = r.get("processosParadigma", [])
            procs = [p.get("numero", "") for p in paradigmas if p.get("numero")]
            if procs:
                partes_ementa.append(f"PROCESSOS PARADIGMA: {', '.join(procs)}")

            url = ""
            if paradigmas and paradigmas[0].get("link"):
                url = paradigmas[0]["link"]

            resultado = ResultadoJuridico(
                fonte="BNP/Pangea",
                tipo=TIPOS_PRECEDENTES.get(r.get("tipo", ""), r.get("tipo", "")),
                numero=f"{r.get('tipo', '')} {r.get('nr', '')}".strip(),
                orgao=r.get("orgao", ""),
                situacao=r.get("situacao", ""),
                data=r.get("ultimaAtualizacao", ""),
                ementa="\n\n".join(partes_ementa),
                url=url,
            )
            resultados.append(resultado)

        return resultados


# Singleton
_client: Optional[BNPClient] = None


def get_client() -> BNPClient:
    global _client
    if _client is None:
        _client = BNPClient()
    return _client
