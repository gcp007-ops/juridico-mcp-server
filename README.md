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
