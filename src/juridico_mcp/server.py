"""
juridico-mcp-server — MCP Server para Jurisprudencia Brasileira

Consolida 6 fontes:
1. CJF (Jurisprudencia Unificada STF/STJ/TRFs) — httpx
2. STJ SCON (Acordaos e monocraticas do STJ) — Chrome dedicado/CDP (aba de fundo)
3. BNP/Pangea (Precedentes qualificados com tese firmada) — httpx
4. TJDFT JurisDF (Acordaos e monocraticas do TJDFT) — httpx
5. RT Online (jurisprudencia premium + inteiro teor) — Chrome dedicado/CDP
6. Jusbrasil (TJs estaduais/TRTs agregados + inteiro teor) — Chrome dedicado/CDP

Transporte: stdio (Claude Desktop) ou HTTP. Roteamento entre fontes: listar_fontes().
"""

from mcp.server.fastmcp import FastMCP
from .clients.cjf import get_client as get_cjf, BASES_CJF
from .clients.stj import get_client as get_stj
from .clients.bnp import get_client as get_bnp, TIPOS_PRECEDENTES
from .clients.tjdft import get_client as get_tjdft, BASES_TJDFT
from .shared import formatar_resultados_texto, ResultadoJuridico, clampar
from .rt import jurisprudencia as rt_juris
from .rt import delivery as rt_delivery
from .jusbrasil import jurisprudencia as jb_juris
from .jusbrasil import inteiro_teor as jb_it
from .jusbrasil import vault as jb_vault

mcp = FastMCP("juridico-mcp-server")


# ── CJF (Prioridade 1) ───────────────────────────────────────────────


@mcp.tool()
def cjf_buscar_jurisprudencia(
    busca: str,
    bases: str = "STJ",
    max_resultados: int = 10,
    completo: bool = False,
) -> str:
    """Jurisprudencia federal UNIFICADA (STF, STJ, TRF1-6) no portal CJF.

    QUANDO USAR: varredura ampla por tema na esfera federal/superior. Para
    precedente vinculante com tese firmada -> bnp_buscar_precedentes; para um TJ
    estadual -> jusbrasil_jurisprudencia_buscar.

    SINTAXE CJF (operadores MAIUSCULOS; NAO confundir com BNP): `E` (AND), `OU`
    (OR), `NAO` (exclui), `ADJ` (adjacencia), `PROX5` (proximidade 5 palavras).
    Ex.: "dano moral E consumidor".

    Args:
        busca: query na sintaxe CJF (E/OU/NAO/ADJ/PROX).
        bases: tribunais por virgula — STF, STJ, TRF1..TRF6, TNU (default "STJ").
        max_resultados: 1-50 (default 10; clampado).
        completo: False (default) = ementa em PREVIEW (economiza tokens); True =
            ementa integral. CJF nao tem inteiro teor — a ementa E o conteudo, use
            completo=True para analisar o acordao a fundo.

    Returns: lista (numero, orgao, relator, data, ementa, link); duplicatas por
        numero (mesmo acordao em bases diferentes) sao removidas.
    """
    try:
        client = get_cjf()
        resultados = client.buscar(busca, bases, clampar(max_resultados, hi=50))
        return formatar_resultados_texto(
            resultados,
            titulo=f"CJF Jurisprudencia [{bases}]",
            completo=completo,
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
    completo: bool = False,
) -> str:
    """Busca no STJ SCON: acordaos (base="ACOR") e decisoes monocraticas (base="MONO").

    SERVER-ONLY: roda em ABA DE FUNDO no Chrome dedicado (STJ_CDP_URL, default
    http://127.0.0.1:9222) — NAO abre janela. A 1a busca leva ~6-10s (Cloudflare
    auto-resolve no navegador real); sem o Chrome dedicado, degrada com erro.

    NUMERO DE PROCESSO: passe APENAS digitos (sem pontos/hifens/barras) — o campo
    livre do SCON e match literal e pontuacao quebra o casamento.
        Certo:  "12345678920243000000" (CNJ) | "REsp 1234567" (classe+digitos)
        Errado: "1234567-89.2024.3.00.0000" | "REsp 1.234.567/SP"

    Args:
        busca: texto livre (ex.: "dano moral"); numero = so digitos (ver acima).
        base: "ACOR" (acordaos, default) ou "MONO" (monocraticas).
        data_inicial/data_final: DD/MM/AAAA (data de julgamento), opcionais.
        max_resultados: 1-50 (default 10; clampado).
        completo: False (default) = ementa em PREVIEW; True = ementa integral. STJ
            nao expoe inteiro teor por tool — a ementa E o conteudo.

    Returns: lista (numero, relator, orgao, data, ementa, link).
    """
    try:
        client = get_stj()
        resultados = await client.buscar_async(busca, base, data_inicial, data_final, clampar(max_resultados, hi=50))
        tipo = "Acordaos" if base.upper() == "ACOR" else "Monocraticas"
        return formatar_resultados_texto(
            resultados,
            titulo=f"STJ {tipo}",
            completo=completo,
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
    completo: bool = False,
) -> str:
    """Precedentes QUALIFICADOS (art. 927 CPC) no BNP/Pangea: tese firmada, questao
    juridica, situacao e processos paradigma.

    QUANDO USAR: quando a tese exige um precedente VINCULANTE/PERSUASIVO, nao
    jurisprudencia geral (para esta, use cjf/stj/jusbrasil). Hierarquia: RG
    (Repercussao Geral/STF, erga omnes) > RR (Repetitivo/STJ) > SV (Sumula
    Vinculante) > SUM (sumula, persuasiva) > IRDR/IAC (regional).

    SINTAXE BNP (NAO use E/OU/NAO): `+termo` (obrigatorio), `-termo` (exclui),
    `"frase"` (exata). Ex.: '+plano +saude +reajuste', '"tema 1066"'.

    Args:
        busca: sintaxe BNP (+/-/"frase").
        orgaos: por virgula — STF, STJ, TST, TSE, STM, TRFs, TJs (default "STF,STJ").
        tipos: RG, RR, SV, SUM, IRDR, IAC, PUIL (default "RG,RR,SV,SUM").
        max_resultados: 1-50 (default 10; clampado).
        completo: False (default) = tese/questao em PREVIEW; True = integral.

    Returns: precedentes (tese, questao, situacao, paradigmas). Os com situacao
        PENDENTE (sem tese firmada) sao sinalizados ao final.
    """
    try:
        client = get_bnp()
        resultados, total = client.buscar(busca, orgaos, tipos, clampar(max_resultados, hi=50))

        texto = formatar_resultados_texto(
            resultados,
            titulo=f"BNP Precedentes [{orgaos}]",
            total=total,
            completo=completo,
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
    completo: bool = False,
) -> str:
    """Jurisprudencia do TJDFT (TJ do DF e Territorios) via JurisDF: acordaos,
    monocraticas e turmas recursais.

    QUANDO USAR: tese que precisa de jurisprudencia do DF. Outros TJs estaduais ->
    jusbrasil_jurisprudencia_buscar.

    SINTAXE JurisDF (operadores MAIUSCULOS): `E`/`OU`/`NAO`, "frase exata",
    `termo$` (wildcard: bio$ -> biologia/biografia). Ex.: '"dano moral" E consumidor'.

    Args:
        busca: query JurisDF.
        max_resultados: 1-100 (default 10; clampado).
        sinonimos: expande a busca com sinonimos (default True).
        completo: False (default) = ementa em PREVIEW; True = ementa integral.

    Returns: lista (numero, orgao, relator, data, ementa).
    """
    try:
        client = get_tjdft()
        resultados, total = client.buscar(busca, clampar(max_resultados, hi=100), sinonimos)
        return formatar_resultados_texto(
            resultados,
            titulo="TJDFT JurisDF",
            total=total,
            completo=completo,
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
    """Jurisprudência premium da RT Online (Revista dos Tribunais). SERVER-ONLY via
    Chrome dedicado logado (RT_CDP_URL); degrada com erro sem a sessão.

    QUANDO USAR: jurisprudência curada/premium e, sobretudo, quando precisar do
    INTEIRO TEOR de um julgado — a busca devolve a URL e, com ela,
    rt_capturar_md(doc_url) entrega o teor em Markdown e rt_baixar_pdf(doc_url) o PDF.

    Pelo menos um de livre/numero/relator é obrigatório. Ano único OU intervalo
    (data_de/data_ate). Cabeçalho validado p/ TRT/TST; metadados parciais em STF/STJ.

    Args:
        livre: texto livre.
        numero: número do processo.
        relator: nome do relator.
        tribunais: siglas por vírgula.
        ano: ano de julgamento (ex.: "2024").
        data_de/data_ate: dd/mm/aaaa (data de julgamento).
        max_resultados: 1-50 (default 10; clampado).

    Returns: lista (número, relator, tribunal, data, JRP, link). Use a URL com
        rt_capturar_md / rt_baixar_pdf para o inteiro teor.
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
            numero=r.get("numero_processo", ""),
            orgao=r.get("tribunal", ""),
            relator=r.get("relator", ""),
            data=r.get("data_julgamento", ""),
            url=r.get("url", ""),
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
def rt_capturar_md(doc_url: str, gravar: bool = True) -> str:
    """Captura um julgado RT como Markdown (a partir do HTML do documento).

    Retorna JSON com status:
    - "ok" + "path": gravado com sucesso na vault
    - "ok_sem_gravacao" + "markdown" + "aviso": markdown extraído mas nota não
      gravada (ex: metadados required ausentes para cortes não-TRT)
    - "ok" + "markdown": gravar=False, markdown retornado sem gravar
    - "erro" + "mensagem": falha de extração ou gravação inesperada
    """
    import json as _json
    doc_url = (doc_url or "").strip()
    if not doc_url:
        return "Parametro invalido: doc_url obrigatoria."
    try:
        doc = rt_juris.extrair_documento(doc_url)
        from .rt import captura_md as _cap
        corpo_md = _cap.html_para_md(doc["html_corpo"])
        markdown = corpo_md
    except Exception as e:
        return _json.dumps({"status": "erro", "mensagem": str(e)}, ensure_ascii=False)
    if not gravar:
        return _json.dumps({"status": "ok", "markdown": markdown}, ensure_ascii=False)
    from .rt import vault as rt_vault
    try:
        path = rt_vault.escrever_julgado(doc, corpo_md)
    except ValueError as e:
        # Campo required ausente (ex: classe vazia em corte não-TRT) — devolve
        # o markdown já extraído + aviso claro; conteúdo NÃO é descartado.
        return _json.dumps(
            {"status": "ok_sem_gravacao", "markdown": corpo_md, "aviso": str(e)},
            ensure_ascii=False,
        )
    except Exception as e:
        return _json.dumps({"status": "erro", "mensagem": f"falha ao gravar nota: {e}"}, ensure_ascii=False)
    return _json.dumps({"status": "ok", "path": path}, ensure_ascii=False)


@mcp.tool()
def rt_baixar_pdf(doc_url: str, destino: str = "") -> str:
    """Baixa o PDF de um julgado RT (use a URL de rt_jurisprudencia_buscar)."""
    import os as _os, json as _json
    doc_url = (doc_url or "").strip()
    if not doc_url:
        return "Parametro invalido: doc_url obrigatoria."
    pasta = destino.strip() if destino else _os.environ.get("RT_DOWNLOAD_DIR", "").strip()
    if not pasta:
        return _json.dumps(
            {"status": "erro", "mensagem": "RT_DOWNLOAD_DIR nao configurado: passe destino ou configure o diretorio de download"},
            ensure_ascii=False,
        )
    try:
        data, filename = rt_delivery.baixar_documento(doc_url, "PDF")
    except Exception as e:
        return _json.dumps({"status": "erro", "mensagem": str(e)}, ensure_ascii=False)
    _os.makedirs(pasta, exist_ok=True)
    path = _os.path.join(pasta, filename)
    with open(path, "wb") as fh:
        fh.write(data)
    return _json.dumps({"status": "ok", "path": path, "bytes": len(data), "filename": filename}, ensure_ascii=False)


# ── Jusbrasil (jurisprudencia agregada, server-only via CDP) ──────────


@mcp.tool()
def jusbrasil_jurisprudencia_buscar(
    termo: str = "",
    pagina: int = 1,
    max_resultados: int = 10,
    ordenar: str = "relevancia",
    periodo: str = "qualquer",
    tribunal: str = "",
    tipo: str = "todos",
    completo: bool = False,
) -> str:
    """Busca jurisprudencia agregada no Jusbrasil (server-only via Chrome dedicado/CDP).

    Cobre o acervo agregado do Jusbrasil (TJs estaduais, TRTs e orgaos pouco
    cobertos pelas fontes httpx). Requer a aba logada do Chrome dedicado
    (JUSBRASIL_CDP_URL, default http://127.0.0.1:9222). Le o DOM da pagina de
    busca. A ementa sai em PREVIEW truncado (economia de tokens); para o texto
    integral de um julgado use jusbrasil_inteiro_teor com a URL do resultado, ou
    completo=True para previews longos na propria lista.

    Args:
        termo: Texto livre da busca (obrigatorio).
        pagina: Pagina de resultados (1+, default 1).
        max_resultados: Limite de resultados (1-30, padrao 10).
        ordenar: "relevancia" (default) ou "recente" (mais novos primeiro).
        periodo: recorte por data — "qualquer" (default), "mes", "ano",
            "2anos", "3anos", "5anos".
        tribunal: sigla-familia para filtrar — "" (todos, default), "STF",
            "STJ", "TST", "TSE", "STM", "TCU", "TNU", "TRU", "CNJ", "CARF",
            "TJ", "TRF", "TRT", "TRE", "TJM", "TCE". O filtro e por familia
            (STJ agrupa seus orgaos; TJ agrupa todos os TJs estaduais).
        tipo: tipo de julgado — "todos" (default), "acordao", "sumula",
            "decisao", "sentenca", "despacho".

    Returns:
        Jurisprudencia formatada com tribunal, tipo, data, ementa e link.
    """
    termo = (termo or "").strip()
    if not termo:
        return "Parametro invalido: informe o termo de busca."
    try:
        regs = jb_juris.buscar(
            termo,
            pagina=max(1, int(pagina)),
            max_resultados=max(1, min(int(max_resultados), 30)),
            ordenar=ordenar,
            periodo=periodo,
            tribunal=tribunal,
            tipo=tipo,
        )
    except Exception as e:
        return f"Erro na busca Jusbrasil jurisprudencia: {e}"
    resultados = [
        ResultadoJuridico(
            fonte="jusbrasil",
            tipo=r.get("tipo") or "jurisprudencia",
            numero=r.get("numero", ""),
            orgao=r.get("tribunal", ""),
            data=r.get("data_publicacao", ""),
            ementa=r.get("ementa", ""),
            url=r.get("url", ""),
            extras={"titulo": r.get("titulo"), "doc_id": r.get("doc_id")},
        )
        for r in regs
    ]
    return formatar_resultados_texto(
        resultados, titulo="Jusbrasil — Jurisprudência", completo=completo
    )


@mcp.tool()
def jusbrasil_inteiro_teor(doc_url: str, gravar: bool = False) -> str:
    """Extrai o inteiro teor de um julgado do Jusbrasil (server-only via CDP).

    Use a URL de um resultado de jusbrasil_jurisprudencia_buscar. Abre o julgado,
    le os metadados (numero/relator/orgao/data por regex sobre o texto renderizado,
    robusto a drift de classe CSS), clica a aba "Inteiro Teor" e extrai o texto
    completo (~27k chars). Gate de seguranca: o resultado nasce citavel=false
    (jurisprudencia auto-extraida; so humano promove).

    Args:
        doc_url: URL do julgado (/jurisprudencia/{slug}/{docId}).
        gravar: Se True, grava nota julgado (Template-Julgado, citavel: false) na
            vault (requer THINKBOX_VAULT_PATH). Default False (so retorna o payload).

    Returns:
        JSON. gravar=False: status "ok" + payload (metadados, ementa, inteiro_teor,
        citavel). gravar=True: "ok"+"path" gravado; "ok_sem_gravacao"+payload+"aviso"
        quando faltam campos required; "erro"+"mensagem" em falha de extracao.
    """
    import json as _json
    doc_url = (doc_url or "").strip()
    if not doc_url:
        return "Parametro invalido: doc_url obrigatoria."
    try:
        payload = jb_it.extrair_inteiro_teor(doc_url)
    except Exception as e:
        return _json.dumps({"status": "erro", "mensagem": str(e)}, ensure_ascii=False)
    if not gravar:
        return _json.dumps({"status": "ok", **payload}, ensure_ascii=False)
    try:
        path = jb_vault.escrever_julgado(payload)
    except ValueError as e:
        # Required ausente (ex.: numero nao parseado) — devolve o conteudo extraido
        # + aviso; nada e descartado.
        return _json.dumps(
            {"status": "ok_sem_gravacao", "aviso": str(e), **payload},
            ensure_ascii=False,
        )
    except Exception as e:
        return _json.dumps({"status": "erro", "mensagem": f"falha ao gravar nota: {e}"}, ensure_ascii=False)
    return _json.dumps({"status": "ok", "path": path, "citavel": payload["citavel"]}, ensure_ascii=False)


# ── Metadados ─────────────────────────────────────────────────────────


@mcp.tool()
def listar_fontes() -> str:
    """Indice e roteamento das fontes de jurisprudencia. CHAME PRIMEIRO se estiver
    em duvida sobre qual tool usar — cada fonte tem sintaxe propria."""
    return """juridico-mcp-server — fontes de jurisprudencia (cada uma com SINTAXE PROPRIA).

COMO ESCOLHER:
- Precedente VINCULANTE / tese firmada (RG/RR/SV/SUM) -> bnp_buscar_precedentes
- Jurisprudencia federal/superior AMPLA (STF/STJ/TRF) -> cjf_buscar_jurisprudencia
- STJ especifico (acordao/monocratica; por numero)     -> stj_buscar_jurisprudencia
- TJ do DF -> tjdft_buscar_jurisprudencia | outros TJs estaduais/TRTs -> jusbrasil
- INTEIRO TEOR de um julgado -> jusbrasil_inteiro_teor (Jusbrasil) ou
  rt_capturar_md/rt_baixar_pdf (RT). As demais fontes so devolvem EMENTA.

FONTES:
1. cjf_buscar_jurisprudencia  — STF/STJ/TRF1-6 unificado. Sintaxe: E/OU/NAO/ADJ/PROX. (httpx)
2. stj_buscar_jurisprudencia  — STJ SCON (base ACOR/MONO). Texto livre; numero = SO digitos.
   Server-only: aba de fundo no Chrome dedicado (sem janela); 1a busca ~6-10s.
3. bnp_buscar_precedentes     — precedentes qualificados (tese firmada). Sintaxe: +termo/-termo/"frase". (httpx)
4. tjdft_buscar_jurisprudencia— TJDFT (DF). Sintaxe: E/OU/NAO/"aspas"/termo$ (wildcard). (httpx)
5. RT Online (server-only, RT_CDP_URL) — premium + INTEIRO TEOR:
   rt_jurisprudencia_buscar(livre/numero/relator/tribunais/ano/data) -> resultados (+URL);
   rt_capturar_md(doc_url) -> Markdown; rt_baixar_pdf(doc_url) -> PDF.
6. Jusbrasil (server-only, JUSBRASIL_CDP_URL :9222) — TJs estaduais/TRTs agregados + INTEIRO TEOR:
   jusbrasil_jurisprudencia_buscar(termo, ordenar/periodo/tribunal/tipo, ...) -> resultados (+URL);
   jusbrasil_inteiro_teor(doc_url) -> ~27k chars (gate citavel:false). Rate-limit >=2s/hit.

ECONOMIA DE TOKENS: buscas com ementa (CJF/STJ/BNP/TJDFT/Jusbrasil) devolvem a
ementa em PREVIEW por padrao; passe completo=True para a ementa integral NA LISTA.
Para o inteiro teor da decisao use as tools dedicadas (RT/Jusbrasil).
"""


# ── Entry point ───────────────────────────────────────────────────────


def main() -> None:
    """Ponto de entrada para stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
