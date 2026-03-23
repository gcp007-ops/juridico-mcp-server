"""
Client: TJDFT JurisDF
Fonte: https://jurisdf.tjdft.jus.br/api/v1/pesquisa
Tecnica: API REST publica (POST JSON)
Dados: Acordaos, decisoes monocraticas, decisoes da presidencia TJDFT
"""

import httpx
from tenacity import retry, wait_exponential, stop_after_attempt
from typing import List, Optional
from ..shared import ResultadoJuridico, limpar_html

JURISDF_API_URL = "https://jurisdf.tjdft.jus.br/api/v1/pesquisa"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}

BASES_TJDFT = {
    "acordaos": "Acordaos",
    "acordaos-tr": "Acordaos - Turmas Recursais",
    "decisoes-monocraticas": "Decisoes Monocraticas",
    "decisoes-presidencia": "Decisoes da Presidencia",
}


class TJDFTClient:
    """Client para API JurisDF do TJDFT."""

    def __init__(self) -> None:
        self._client = httpx.Client(
            headers=HEADERS,
            timeout=30.0,
        )

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def buscar(
        self,
        busca: str,
        max_resultados: int = 10,
        sinonimos: bool = True,
        pagina: int = 0,
    ) -> tuple[List[ResultadoJuridico], int]:
        """
        Busca jurisprudencia no JurisDF (TJDFT).

        Args:
            busca: Query JurisDF. Operadores: E, OU, NAO, "aspas", $ (wildcard)
            max_resultados: Limite (1-100)
            sinonimos: Expandir busca com sinonimos
            pagina: Pagina de resultados (0-indexed)
        """
        payload = {
            "query": busca,
            "termosAcessorios": [],
            "pagina": pagina,
            "tamanho": min(max_resultados, 100),
            "sinonimos": sinonimos,
            "espelho": True,
            "inteiroTeor": False,
            "retornaInteiroTeor": False,
            "retornaTotalizacao": True,
        }

        resp = self._client.post(JURISDF_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        total = data.get("hits", {}).get("value", 0) if isinstance(data.get("hits"), dict) else data.get("hits", 0)
        resultados = self._parse_resultados(data)
        return resultados, total

    def _parse_resultados(self, data: dict) -> List[ResultadoJuridico]:
        """Converte resposta JurisDF."""
        resultados: List[ResultadoJuridico] = []

        for item in data.get("registros", []):
            ementa = limpar_html(item.get("ementa", ""))
            tipo_label = BASES_TJDFT.get(item.get("base", ""), item.get("base", ""))

            # Formatar data
            data_julg = item.get("dataJulgamento", "")
            if data_julg:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(data_julg.replace("Z", "+00:00"))
                    data_julg = dt.strftime("%d/%m/%Y")
                except Exception:
                    pass

            uuid = item.get("uuid", "")
            url = f"https://jurisdf.tjdft.jus.br/acordaos/{uuid}" if uuid else ""

            resultado = ResultadoJuridico(
                fonte="TJDFT/JurisDF",
                tipo=tipo_label,
                numero=item.get("processo", ""),
                orgao=item.get("descricaoOrgaoJulgador", ""),
                relator=item.get("nomeRelator", ""),
                data=data_julg,
                ementa=ementa,
                decisao=item.get("decisao", ""),
                url=url,
            )
            resultados.append(resultado)

        return resultados


# Singleton
_client: Optional[TJDFTClient] = None


def get_client() -> TJDFTClient:
    global _client
    if _client is None:
        _client = TJDFTClient()
    return _client
