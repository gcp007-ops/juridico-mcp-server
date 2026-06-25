"""
Utilidades compartilhadas entre os clients de jurisprudencia.
"""

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class ResultadoJuridico:
    """Resultado padronizado de busca juridica."""
    fonte: str
    tipo: str = ""
    numero: str = ""
    orgao: str = ""
    relator: str = ""
    data: str = ""
    ementa: str = ""
    decisao: str = ""
    situacao: str = ""
    url: str = ""
    extras: dict = field(default_factory=dict)


def clampar(n, lo: int = 1, hi: int = 50) -> int:
    """Restringe max_resultados ao intervalo documentado [lo, hi].

    Tolera entrada nao-inteira/negativa (evita slices patologicos do tipo
    lista[:-3] ou tamanhoPagina=0 nos clients que nao clampavam).
    """
    try:
        n = int(n)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(n, hi))


def truncar(texto: str, max_chars: int = 20000) -> str:
    """Trunca texto preservando ultimo ponto."""
    if not texto or len(texto) <= max_chars:
        return (texto or "").strip()
    truncado = texto[:max_chars]
    ultimo_ponto = truncado.rfind(".")
    if ultimo_ponto > max_chars * 0.8:
        truncado = truncado[:ultimo_ponto + 1]
    return truncado.strip() + " [...]"


def limpar_html(texto: str) -> str:
    """Remove tags HTML e normaliza espacos."""
    if not texto:
        return ""
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"&[a-zA-Z]+;", " ", texto)
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def formatar_resultados_texto(
    resultados: List[ResultadoJuridico],
    titulo: str = "Resultados",
    total: int | None = None,
) -> str:
    """Formata lista de resultados como texto legivel."""
    if not resultados:
        return f"{titulo}: Nenhum resultado encontrado."

    total_str = f" (total: {total})" if total else ""
    linhas = [f"{titulo} — {len(resultados)} exibidos{total_str}", ""]

    for i, r in enumerate(resultados, 1):
        linhas.append(f"{'='*60}")
        linhas.append(f"{i}. {r.tipo} | {r.numero}" if r.numero else f"{i}. {r.tipo}")
        if r.orgao:
            linhas.append(f"   Orgao: {r.orgao}")
        if r.relator:
            linhas.append(f"   Relator: {r.relator}")
        if r.data:
            linhas.append(f"   Data: {r.data}")
        if r.situacao:
            linhas.append(f"   Situacao: {r.situacao}")
        if r.ementa:
            linhas.append(f"   Ementa: {truncar(r.ementa, 2000)}")
        if r.decisao:
            linhas.append(f"   Decisao: {truncar(r.decisao, 1000)}")
        if r.url:
            linhas.append(f"   Link: {r.url}")
        for k, v in r.extras.items():
            linhas.append(f"   {k}: {v}")
        linhas.append("")

    return "\n".join(linhas)
