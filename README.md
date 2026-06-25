# juridico-mcp-server

MCP server para **jurisprudência brasileira** — consolida **6 fontes** num único server Python/FastMCP: 3 públicas via httpx (CJF, BNP, TJDFT) + 3 server-only via Chrome dedicado/CDP (STJ, RT, Jusbrasil).

> **Roteamento:** em dúvida sobre qual tool usar, chame `listar_fontes()` primeiro — ela traz um guia "como escolher" + a sintaxe de cada fonte.

## Fontes Integradas

| Tool | Fonte | Sintaxe | Dados |
|------|-------|---------|-------|
| `cjf_buscar_jurisprudencia` | CJF Unificada | E, OU, NAO, ADJ, PROX | Acórdãos STF, STJ, TRF1-TRF6 (ementa) |
| `stj_buscar_jurisprudencia` | STJ SCON ⚠ server-only | Texto livre (número = só dígitos) | Acórdãos, monocráticas STJ (ementa) |
| `bnp_buscar_precedentes` | Pangea/BNP (CNJ) | +termo, -termo, "frase" | Precedentes com tese firmada |
| `tjdft_buscar_jurisprudencia` | JurisDF TJDFT | E, OU, NAO, "aspas", $ | Acórdãos, monocráticas TJDFT (ementa) |
| `bnp_listar_tipos` | BNP | — | Tipos de precedentes |
| `listar_fontes` | — | — | Índice + roteamento entre fontes |
| `rt_jurisprudencia_buscar` | RT Online ⚠ server-only | livre/numero/relator/tribunais/ano | Jurisprudência premium RT |
| `rt_capturar_md` / `rt_baixar_pdf` | RT Online ⚠ server-only | doc_url | **Inteiro teor** RT (Markdown / PDF) |
| `jusbrasil_jurisprudencia_buscar` | Jusbrasil ⚠ server-only | texto livre + filtros (tribunal/tipo/período/ordem) | TJs estaduais, TRTs agregados (ementa) |
| `jusbrasil_inteiro_teor` | Jusbrasil ⚠ server-only | doc_url, gravar | **Inteiro teor** (~27k) + nota `julgado` |

> **Ementa vs inteiro teor:** só **RT** e **Jusbrasil** expõem o inteiro teor da decisão (tools dedicadas). CJF/STJ/BNP/TJDFT devolvem **ementa** — que é o conteúdo daquelas fontes.
>
> **Economia de tokens:** as buscas com ementa devolvem a ementa em **preview** truncado por padrão; passe `completo=True` para a ementa integral na própria lista. Duplicatas por número são deduplicadas.

## Requisitos

- Python >= 3.10
- uv (recomendado) ou pip

## Instalação

```bash
cd juridico-mcp-server
pip install -e .
# ou com uv:
uv pip install -e .
```

## Claude Desktop

Adicione ao `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "juridico": {
      "command": "python",
      "args": ["-m", "juridico_mcp"],
      "env": {
        "PYTHONPATH": "C:\\GIT\\juridico-mcp-server\\src"
      }
    }
  }
}
```

Ou com uv:

```json
{
  "mcpServers": {
    "juridico": {
      "command": "uv",
      "args": ["--directory", "C:\\GIT\\juridico-mcp-server", "run", "juridico-mcp"]
    }
  }
}
```

## Sintaxe de Busca por Fonte

**IMPORTANTE:** Cada fonte tem sintaxe diferente.

### CJF
```
"dano moral" E consumidor
pensao E morte NAO militar
aposentadoria ADJ especial
```

### STJ SCON
```
plano de saude reajuste abusivo
sumula 7
```

### BNP/Pangea
```
+plano +saude +reajuste
"tema 1066"
+ICMS +"base de calculo" -importacao
```

### TJDFT JurisDF
```
"dano moral" E consumidor
plano$ E saude (wildcard: plano, planos, planejamento...)
```

## Tools RT Online (server-only)

As tools RT exigem Chrome dedicado com CDP ativo e **não funcionam em Claude Desktop**
(são server-side via `RT_CDP_URL`). As fontes httpx (CJF, BNP, TJDFT) permanecem intactas
e independentes — as fontes CDP (STJ, RT, Jusbrasil) não afetam seu funcionamento.

### Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `RT_CDP_URL` | Sim (tools RT) | URL do Chrome DevTools Protocol do browser dedicado (ex: `http://localhost:9222`) |
| `JUSBRASIL_CDP_URL` | Não (default `:9222`) | CDP do Chrome dedicado logado no Jusbrasil |
| `STJ_CDP_URL` | Não (default `:9222`) | CDP do Chrome dedicado para o STJ SCON (aba de fundo; resolve o Cloudflare sem abrir janela) |
| `THINKBOX_VAULT_PATH` | Para captura/PDF | Caminho raiz da vault ThinkBox; usado por `rt_capturar_md`/`jusbrasil_inteiro_teor` (gravar) e `rt_baixar_pdf` (destino padrão) |

### `rt_jurisprudencia_buscar`

Busca jurisprudência premium na RT Online. Pelo menos um de `livre`, `numero` ou `relator` é obrigatório.

```
rt_jurisprudencia_buscar(
    livre=""        # texto livre
    numero=""       # número do processo
    relator=""      # nome do relator
    tribunais=""    # tribunais separados por vírgula (ex: "TRT-3,TST")
    ano=""          # ano de julgamento (ex: "2024")
    data_de=""      # data inicial dd/mm/aaaa (julgamento)
    data_ate=""     # data final dd/mm/aaaa (julgamento)
    max_resultados=10
)
```

**Escopo atual:** jurisprudência premium. Parser de cabeçalho validado para a Justiça do Trabalho (TRT/TST); para outras cortes (STJ, STF, TJs) a busca e o PDF funcionam, mas a extração de metadados do julgado (classe/relator/órgão) pode ficar parcial — nesse caso `rt_capturar_md` retorna o markdown com aviso (`ok_sem_gravacao`), sem gravar a nota. Legislação e súmulas serão adicionadas em versões futuras.

### `rt_baixar_pdf`

Baixa o PDF de um julgado RT usando a URL retornada por `rt_jurisprudencia_buscar`.

```
rt_baixar_pdf(
    doc_url=""    # URL do documento (obrigatória)
    destino=""    # pasta de destino; padrão: THINKBOX_VAULT_PATH/Conhecimento/Fontes/Julgados/RT/_pdf/
)
```

Retorna JSON com `status`, `path`, `bytes` e `filename`.

### `rt_capturar_md`

Extrai o julgado como Markdown a partir do HTML do documento RT. Por padrão (`gravar=True`) grava
uma nota `julgado` na vault ThinkBox (requer `THINKBOX_VAULT_PATH`). Passe `gravar=False` para
obter apenas o markdown sem persistir nada.

```
rt_capturar_md(
    doc_url=""     # URL do documento (obrigatória)
    gravar=True    # True → grava nota julgado na vault; False → retorna só o markdown
)
```

Retorna JSON com `status` e `path` (quando `gravar=True`) ou `markdown` (quando `gravar=False`).

## STJ SCON (server-only)

O STJ está atrás de um Cloudflare *managed challenge*. Em vez de abrir uma janela
de browser (que roubava foco na máquina), o STJ roda numa **aba de fundo no Chrome
dedicado** (`STJ_CDP_URL`, default `http://127.0.0.1:9222`) — o navegador real
resolve o challenge sozinho em ~6s; a 1ª busca leva ~6-10s. `headless` puro não é
opção (o Cloudflare bloqueia). Para localizar por número, passe **apenas dígitos**
(`12345678920243000000` ou `REsp 1234567`) — pontuação quebra o match do SCON.

## Jusbrasil (server-only)

Acervo agregado (TJs estaduais, TRTs e órgãos pouco cobertos pelas fontes httpx),
lido do DOM da sessão logada no Chrome dedicado (`JUSBRASIL_CDP_URL`, default
`:9222`). Rate-limit automático ≥2s entre hits.

```
jusbrasil_jurisprudencia_buscar(
    termo,                 # texto livre (obrigatório)
    pagina=1, max_resultados=10,
    ordenar="relevancia",  # ou "recente"
    periodo="qualquer",    # mes/ano/2anos/3anos/5anos
    tribunal="",           # sigla-família: STF/STJ/TJ/TRF/TRT/...
    tipo="todos",          # acordao/sumula/decisao/sentenca/despacho
    completo=False,        # ementa em preview; True = integral
)

jusbrasil_inteiro_teor(doc_url, gravar=False)
# Inteiro teor (~27k chars) + metadados. Gate citável: false (nasce não-citável;
# só humano promove). gravar=True grava nota `julgado` (Template-Julgado) na vault.
```

## Complementaridade com datajud-mcp-server

Este server complementa o `datajud-mcp-server` (TypeScript):

| datajud-mcp-server | juridico-mcp-server |
|---------------------|---------------------|
| Metadados processuais | Jurisprudência e precedentes |
| Capa, partes, movimentações | Ementas, teses, inteiro teor |
| Todos os 90+ tribunais | STF, STJ, TRFs, TJDFT + TJs estaduais/TRTs (Jusbrasil) + RT premium |
| API Elasticsearch DataJud | APIs variadas (REST, DOM via CDP logado) |

## Licença

MIT (código próprio). Baseado em endpoints públicos dos tribunais.
BNP client inspirado em georgemarmelstein/bnp-api (MIT).
