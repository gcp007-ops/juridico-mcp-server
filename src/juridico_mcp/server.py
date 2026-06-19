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
from .shared import formatar_resultados_texto, ResultadoJuridico
from .rt import jurisprudencia as rt_juris
from .rt import delivery as rt_delivery

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

    CRITICO -- BUSCA POR NUMERACAO:
        Para localizar um processo/acordao pelo numero, passe APENAS digitos
        sequenciados. NAO usar pontos, hifens, barras ou espacos.

        Errado:  busca="1234567-89.2024.3.00.0000"   (CNJ formatado)
        Errado:  busca="REsp 1.234.567"              (formato com pontos)
        Errado:  busca="REsp 1.234.567/SP"           (com UF e barra)
        Certo:   busca="12345678920243000000"        (CNJ so digitos)
        Certo:   busca="REsp 1234567"                (classe + digitos)
        Certo:   busca="1234567"                     (so o numero sequencial)

        Justificativa: o campo "livre" do SCON e match literal/tokenizado;
        pontuacao quebra o casamento. Use digitos puros para o numero e,
        opcionalmente, a sigla da classe processual (REsp, AgRg, HC, etc).

    Args:
        busca: Termo de busca livre (ex: "dano moral", "sumula 7").
               Para numero de processo/acordao: APENAS digitos, sem
               pontos/hifens/barras. Ver "CRITICO -- BUSCA POR NUMERACAO".
        base: "ACOR" para acordaos, "MONO" para monocraticas
        data_inicial: Formato DD/MM/AAAA (opcional)
        data_final: Formato DD/MM/AAAA (opcional)
        max_resultados: Limite (1-50, padrao 10)

    Returns:
        Decisoes formatadas com numero, relator, ementa, orgao julgador

    Examples:
        - busca="plano de saude reajuste abusivo", base="ACOR"
        - busca="responsabilidade civil objetiva", data_inicial="01/01/2024"
        - busca="REsp 1234567", base="ACOR"                # numero sem pontos
        - busca="12345678920243000000", base="ACOR"        # CNJ so digitos
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


# ── RT Online (Prioridade 5) ─────────────────────────────────────────


@mcp.tool()
async def rt_jurisprudencia_buscar(
    livre: str = "",
    numero: str = "",
    relator: str = "",
    tribunais: str = "",
    ano: str = "",
    data_de: str = "",
    data_ate: str = "",
    max_resultados: int = 10,
) -> str:
    """Busca jurisprudência premium na RT Online (server-only via Chrome dedicado/CDP).

    Pelo menos um de livre/numero/relator é obrigatório. Ano único OU intervalo
    (data_de/data_ate em dd/mm/aaaa, data de julgamento). Requer RT_CDP_URL.

    Args:
        livre: Texto livre para busca
        numero: Número do processo
        relator: Nome do relator
        tribunais: Tribunais separados por vírgula
        ano: Ano de julgamento (ex: "2024")
        data_de: Data inicial em dd/mm/aaaa (data de julgamento)
        data_ate: Data final em dd/mm/aaaa (data de julgamento)
        max_resultados: Limite de resultados (1-50, padrão 10)

    Returns:
        Acórdãos formatados com número, relator, tribunal, data, JRP e link
    """
    if not any(s.strip() for s in (livre, numero, relator)):
        return "Parametro invalido: informe ao menos livre, numero ou relator."
    try:
        regs = await rt_juris.buscar(
            livre=livre.strip(),
            numero=numero.strip(),
            relator=relator.strip(),
            tribunais=tribunais.strip(),
            ano=ano.strip(),
            data_de=data_de.strip(),
            data_ate=data_ate.strip(),
            max_resultados=max(1, min(int(max_resultados), 50)),
        )
    except Exception as e:
        return f"Erro na busca RT jurisprudencia: {e}"
    resultados = [
        ResultadoJuridico(
            fonte="rt",
            tipo="acordao",
            numero=r["numero_processo"],
            orgao=r["tribunal"],
            relator=r["relator"],
            data=r["data_julgamento"],
            url=r["url"],
            extras={
                "jrp": r.get("jrp"),
                "veiculo": r.get("veiculo"),
                "data_publicacao": r.get("data_publicacao"),
            },
        )
        for r in regs
    ]
    return formatar_resultados_texto(resultados, titulo="RT Online — Jurisprudência")


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
