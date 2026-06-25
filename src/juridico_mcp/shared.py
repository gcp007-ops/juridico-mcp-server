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


PREVIEW_CHARS = 500


def dedup_resultados(resultados: List[ResultadoJuridico]) -> List[ResultadoJuridico]:
    """Remove duplicatas por numero (mesmo acordao sob bases distintas — ex.: CJF
    consultando STF,STJ,TRF). Resultados sem numero sao preservados (nao ha chave
    confiavel para deduplicar)."""
    visto = set()
    out: List[ResultadoJuridico] = []
    for r in resultados:
        chave = (r.numero or "").strip()
        if chave and chave in visto:
            continue
        if chave:
            visto.add(chave)
        out.append(r)
    return out


def formatar_resultados_texto(
    resultados: List[ResultadoJuridico],
    titulo: str = "Resultados",
    total: int | None = None,
    *,
    completo: bool = False,
) -> str:
    """Formata lista de resultados como texto legivel.

    Por padrao (completo=False) a ementa/decisao saem como PREVIEW curto
    (PREVIEW_CHARS) para economizar tokens — a lista serve para o agente escolher
    o que aprofundar pela URL/numero. completo=True devolve o texto longo (cap
    2000/1000), util quando a ementa e o proprio conteudo (CJF/STJ/BNP/TJDFT, que
    nao tem tool de inteiro teor).
    """
    if not resultados:
        return f"{titulo}: Nenhum resultado encontrado."

    resultados = dedup_resultados(resultados)
    cap_ementa = 2000 if completo else PREVIEW_CHARS
    cap_decisao = 1000 if completo else PREVIEW_CHARS
    houve_corte = False

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
            em = truncar(r.ementa, cap_ementa)
            houve_corte = houve_corte or len(r.ementa.strip()) > len(em)
            rotulo = "Ementa" if completo else "Ementa (preview)"
            linhas.append(f"   {rotulo}: {em}")
        if r.decisao:
            dec = truncar(r.decisao, cap_decisao)
            houve_corte = houve_corte or len(r.decisao.strip()) > len(dec)
            linhas.append(f"   Decisao: {dec}")
        if r.url:
            linhas.append(f"   Link: {r.url}")
        for k, v in r.extras.items():
            linhas.append(f"   {k}: {v}")
        linhas.append("")

    if houve_corte and not completo:
        linhas.append(
            "Nota: ementas/decisoes truncadas (preview). Reexecute com completo=True "
            "para o texto integral (ou use a tool de inteiro teor da fonte)."
        )

    return "\n".join(linhas)
