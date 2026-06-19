# juridico-mcp-server

MCP server para **jurisprudência brasileira** — consolida 4 fontes públicas num único server Python/FastMCP.

## Fontes Integradas

| Tool | Fonte | Sintaxe | Dados |
|------|-------|---------|-------|
| `cjf_buscar_jurisprudencia` | CJF Unificada | E, OU, NAO, ADJ, PROX | Acórdãos STF, STJ, TRF1-TRF6 |
| `stj_buscar_jurisprudencia` | STJ SCON | Texto livre | Acórdãos, monocráticas STJ |
| `bnp_buscar_precedentes` | Pangea/BNP (CNJ) | +termo, -termo, "frase" | Precedentes com tese firmada |
| `tjdft_buscar_jurisprudencia` | JurisDF TJDFT | E, OU, NAO, "aspas", $ | Acórdãos, monocráticas TJDFT |
| `bnp_listar_tipos` | BNP | — | Tipos de precedentes |
| `listar_fontes` | — | — | Metadados das fontes |
| `rt_jurisprudencia_buscar` | RT Online ⚠ server-only | livre/numero/relator/tribunais/ano | Jurisprudência premium RT |
| `rt_baixar_pdf` | RT Online ⚠ server-only | doc_url, destino | PDF do julgado RT |
| `rt_capturar_md` | RT Online ⚠ server-only | doc_url, gravar | Markdown do julgado RT |

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

As três tools RT exigem Chrome dedicado com CDP ativo e **não funcionam em Claude Desktop**
(são server-side via `RT_CDP_URL`). As fontes httpx (CJF, STJ, BNP, TJDFT) permanecem intactas
e independentes — o RT não afeta seu funcionamento.

### Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `RT_CDP_URL` | Sim (tools RT) | URL do Chrome DevTools Protocol do browser dedicado (ex: `http://localhost:9222`) |
| `THINKBOX_VAULT_PATH` | Para captura/PDF | Caminho raiz da vault ThinkBox; usado por `rt_capturar_md` (gravar) e `rt_baixar_pdf` (destino padrão) |

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

## Complementaridade com datajud-mcp-server

Este server complementa o `datajud-mcp-server` (TypeScript):

| datajud-mcp-server | juridico-mcp-server |
|---------------------|---------------------|
| Metadados processuais | Jurisprudência e precedentes |
| Capa, partes, movimentações | Ementas, teses, inteiro teor |
| Todos os 90+ tribunais | STF, STJ, TRFs, TJDFT |
| API Elasticsearch DataJud | APIs variadas (REST, scraping) |

## Licença

MIT (código próprio). Baseado em endpoints públicos dos tribunais.
BNP client inspirado em georgemarmelstein/bnp-api (MIT).
