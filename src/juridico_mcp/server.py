"""
juridico-mcp-server — MCP Server para Jurisprudencia Brasileira

Consolida 4 fontes publicas:
1. CJF (Jurisprudencia Unificada STF/STJ/TRFs)
2. STJ SCON (Acordaos e monocraticas do STJ)
3. BNP/Pangea (Precedentes qualificados com tese firmada)
4. TJDFT JurisDF (Acordaos e monocraticas do TJDFT)

Transporte: stdio (Claude Desktop) ou HTTP
"""

from mcp.server.fastmcp import FastMCP
from .clients.cjf import get_client as get_cjf, BASES_CJF
from .clients.stj import get_client as get_stj
from .clients.bnp import get_client as get_bnp, TIPOS_PRECEDENTES
from .clients.tjdft import get_client as get_tjdft, BASES_TJDFT
from .shared import formatar_resultados_texto

mcp = FastMCP("juridico-mcp-server")


# ── CJF (Prioridade 1) ───────────────────────────────────────────────


@mcp.tool()
def cjf_buscar_jurisprudencia(
    busca: str,
    bases: str = "STJ",
    max_resultados: int = 10,
) -> str:
    """
    Busca jurisprudencia unificada no portal CJF.
    Inclui acordaos do STF, STJ, TRF1 a TRF6.

    SINTAXE CJF (diferente do BNP!):
    - "termo1 E termo2" = AND
    - "termo1 OU termo2" = OR
    - "NAO termo" = exclusao
    - "termo1 ADJ termo2" = adjacencia
    - "termo1 PROX5 termo2" = proximidade (5 palavras)

    Args:
        busca: Query com sintaxe CJF (E, OU, NAO, ADJ, PROX)
        bases: Tribunais separados por virgula. Opcoes: STF, STJ, TRF1, TRF2, TRF3, TRF4, TRF5, TRF6
        max_resultados: Limite de resultados (1-50, padrao 10)

    Returns:
        Acordaos formatados com ementa, relator, orgao, data

    Examples:
        - busca="dano moral E consumidor", bases="STJ"
        - busca="plano de saude E reajuste NAO coletivo", bases="STJ,TRF1"
    """
    try:
        client = get_cjf()
        resultados = client.buscar(busca, bases, max_resultados)
        return formatar_resultados_texto(
            resultados,
            titulo=f"CJF Jurisprudencia [{bases}]",
        )
    except Exception as e:
        return f"Erro na busca CJF: {e}"


# ── STJ SCON (Prioridade 2) ──────────────────────────────────────────


@mcp.tool()
async def stj_buscar_jurisprudencia(
    busca: str,
    base: str = "ACOR",
    data_inicial: str = "",
    data_final: str = "",
    max_resultados: int = 10,
) -> str:
    """
    Busca jurisprudencia no STJ via SCON.
    Acordaos colegiados e decisoes monocraticas com ementa e inteiro teor.

    NOTA: Usa browser real (nodriver) para contornar Cloudflare.
    Primeira busca demora ~20s. Requer Chrome instalado.

    Args:
        busca: Termo de busca livre (ex: "dano moral", "sumula 7")
        base: "ACOR" para acordaos, "MONO" para monocraticas
        data_inicial: Formato DD/MM/AAAA (opcional)
        data_final: Formato DD/MM/AAAA (opcional)
        max_resultados: Limite (1-50, padrao 10)

    Returns:
        Decisoes formatadas com numero, relator, ementa, orgao julgador

    Examples:
        - busca="plano de saude reajuste abusivo", base="ACOR"
        - busca="responsabilidade civil objetiva", data_inicial="01/01/2024"
    """
    try:
        client = get_stj()
        resultados = await client.buscar_async(busca, base, data_inicial, data_final, max_resultados)
        tipo = "Acordaos" if base.upper() == "ACOR" else "Monocraticas"
        return formatar_resultados_texto(
            resultados,
            titulo=f"STJ {tipo}",
        )
    except Exception as e:
        return f"Erro na busca STJ: {e}"


# ── BNP/Pangea (Prioridade 3) ────────────────────────────────────────


@mcp.tool()
def bnp_buscar_precedentes(
    busca: str,
    orgaos: str = "STF,STJ",
    tipos: str = "RG,RR,SV,SUM",
    max_resultados: int = 10,
) -> str:
    """
    Busca precedentes qualificados no Banco Nacional de Precedentes (BNP/Pangea).
    Retorna tese firmada, questao juridica, situacao e processos paradigma.

    SINTAXE BNP (diferente da CJF!):
    - +termo = obrigatorio (AND)
    - -termo = excluido (NOT)
    - "frase" = expressao exata
    - NAO funcionam: E, OU, NAO, AND, OR, NOT

    HIERARQUIA DE PRECEDENTES:
    1. RG (Repercussao Geral STF) - vinculante erga omnes
    2. RR (Recurso Repetitivo STJ) - vinculante
    3. SV (Sumula Vinculante STF) - vinculante
    4. SUM (Sumula STF/STJ) - altamente persuasivo
    5. IRDR/IAC - persuasivo regional

    Args:
        busca: Query com sintaxe BNP (+termo, -termo, "frase")
        orgaos: Orgaos separados por virgula (STF, STJ, TST, TSE, STM, TRFs, TJs)
        tipos: Tipos: RG, RR, SV, SUM, IRDR, IAC, PUIL (separados por virgula)
        max_resultados: Limite (1-50, padrao 10)

    Returns:
        Precedentes com tese firmada, questao juridica, situacao, paradigmas

    Examples:
        - busca='+plano +saude +reajuste', orgaos="STJ"
        - busca='"tema 1066"', orgaos="STF", tipos="RG"
        - busca='+ICMS +"base de calculo" +PIS', orgaos="STF,STJ"
    """
    try:
        client = get_bnp()
        resultados, total = client.buscar(busca, orgaos, tipos, max_resultados)

        texto = formatar_resultados_texto(
            resultados,
            titulo=f"BNP Precedentes [{orgaos}]",
            total=total,
        )

        # Adicionar nota sobre situacao
        pendentes = [r for r in resultados if "pendente" in (r.situacao or "").lower()]
        if pendentes:
            texto += f"\n\n⚠ ATENCAO: {len(pendentes)} precedente(s) com situacao PENDENTE (sem tese firmada)."

        return texto
    except Exception as e:
        return f"Erro na busca BNP: {e}"


@mcp.tool()
def bnp_listar_tipos() -> str:
    """Lista todos os tipos de precedentes disponiveis no BNP com codigos."""
    linhas = ["Tipos de precedentes no BNP:", ""]
    for codigo, descricao in TIPOS_PRECEDENTES.items():
        linhas.append(f"  {codigo:6s} — {descricao}")
    return "\n".join(linhas)


# ── TJDFT JurisDF (Prioridade 4) ─────────────────────────────────────


@mcp.tool()
def tjdft_buscar_jurisprudencia(
    busca: str,
    max_resultados: int = 10,
    sinonimos: bool = True,
) -> str:
    """
    Busca jurisprudencia no TJDFT via JurisDF.
    Acordaos, monocraticas e decisoes de turmas recursais.

    SINTAXE JurisDF (operadores em MAIUSCULO):
    - "termo1 E termo2" = AND
    - "termo1 OU termo2" = OR
    - "NAO termo" = exclusao
    - "frase exata" entre aspas
    - termo$ = wildcard (bio$ encontra biologia, biografia)

    Args:
        busca: Query JurisDF (E, OU, NAO, "aspas", $wildcard)
        max_resultados: Limite (1-100, padrao 10)
        sinonimos: Expandir busca com sinonimos (default True)

    Returns:
        Decisoes formatadas com ementa, relator, orgao, data

    Examples:
        - busca='"dano moral" E consumidor'
        - busca='"plano de saude" E reajuste NAO coletivo'
    """
    try:
        client = get_tjdft()
        resultados, total = client.buscar(busca, max_resultados, sinonimos)
        return formatar_resultados_texto(
            resultados,
            titulo="TJDFT JurisDF",
            total=total,
        )
    except Exception as e:
        return f"Erro na busca TJDFT: {e}"


# ── Metadados ─────────────────────────────────────────────────────────


@mcp.tool()
def listar_fontes() -> str:
    """Lista todas as fontes de jurisprudencia disponiveis neste server."""
    return """Fontes disponiveis no juridico-mcp-server:

1. CJF (cjf_buscar_jurisprudencia)
   Jurisprudencia unificada: STF, STJ, TRF1-TRF6
   Sintaxe: E, OU, NAO, ADJ, PROX
   Dados: Acordaos com ementa

2. STJ SCON (stj_buscar_jurisprudencia)
   Acordaos e monocraticas do STJ
   Sintaxe: Texto livre
   Dados: Ementa, relator, orgao, inteiro teor

3. BNP/Pangea (bnp_buscar_precedentes)
   Precedentes qualificados (art. 927 CPC)
   Sintaxe: +termo, -termo, "frase"
   Dados: Tese firmada, questao juridica, situacao, paradigmas
   Tipos: RG, RR, SV, SUM, IRDR, IAC, PUIL

4. TJDFT JurisDF (tjdft_buscar_jurisprudencia)
   Acordaos e monocraticas do TJDFT
   Sintaxe: Texto livre
   Dados: Ementa, relator, orgao

NOTA: Cada fonte tem sintaxe de busca DIFERENTE.
- CJF usa: E, OU, NAO, ADJ, PROX
- BNP usa: +termo, -termo, "frase"
- STJ e TJDFT: texto livre
"""


# ── Entry point ───────────────────────────────────────────────────────


def main() -> None:
    """Ponto de entrada para stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
