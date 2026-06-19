# RT Online Jurisprudência no juridico-mcp-server — busca + captura

Data: 2026-06-19
Repo: `juridico-mcp-server`
Status: design (aguardando revisão do usuário)

## Contexto

`juridico-mcp-server` é um agregador de jurisprudência **httpx / fontes públicas**
(CJF, STJ, BNP, TJDFT), portátil (stdio/HTTP), sem estado autenticado. Tools atuais:
`cjf_buscar_jurisprudencia`, `stj_buscar_jurisprudencia`, `bnp_buscar_precedentes`,
`bnp_listar_tipos`, `tjdft_buscar_jurisprudencia`, `listar_fontes`.

A RT Online (Thomson/WLBR) cobre jurisprudência premium que essas fontes públicas não
têm (acórdãos indexados, JurisTendência, etc.). O acesso RT é **server-only, autenticado
via OnePass/Auth0, dirigido por CDP** no Chrome dedicado (`RT_CDP_URL`, perfil compartilhado
com Novajus/L1) — natureza distinta das fontes httpx. A Doutrina RT já vive em outro MCP
(`busca-academica-mcp`); por decisão do usuário, **jurisprudência RT vive aqui**.

Decisões fixadas (usuário, 2026-06-19):
1. **Casa:** estender `juridico-mcp-server`. RT entra como fonte premium/server-only
   (carve-out): só as tools RT exigem `RT_CDP_URL`; as httpx seguem portáteis e intactas.
2. **Reuso:** `cdp-scaffold` para o CDP genérico + **portar** os bits RT-específicos
   (auth OnePass, form-runner, delivery offload) da implementação já validada em
   `busca-academica-mcp` (cópia consciente — segue a decisão de não compartilhar `rt_auth`).
3. **v1:** jurisprudência com **busca avançada + captura (PDF + MD→nota `julgado`)**.
   Legislação/súmulas RT ficam para fase posterior.

## Recon ao vivo (2026-06-19, sessão CDP dedicada, máquina-servidor)

Tudo abaixo foi mapeado/validado ao vivo (mesma sessão que validou a Doutrina end-to-end).

### Busca de jurisprudência

- Entrada: `tocguid=brjuris` (`/maf/api/tocectory?tocguid=brjuris&stnew=true&oss=true&ndd=1`).
- `#searchForm` action: **`/maf/app/trail/searchfromlink/run`** (difere da Doutrina, `…/search/run`).
- Campos de usuário admitidos: `frt` (livre), `num` (Número do Acórdão/Processo),
  `jud` (Relator), `tribunais` (+ `queryTC`/`queryTJ`/`queryRF`/`queryRT`/`queryRE`/`queryJM`/`queryTA`
  e flags `TCall/TJall/...` — seleção de cortes), `dateType`+`fromDate`/`toDate`/`exactDate`/`ano`
  (data de **julgamento**), `dateTypeDisp`+`*Disp` (data de **publicação**), `revistas`,
  `volume`, `pageNum`, filtros `GR01..GR06`/`RR` (Repercussão Geral / Recursos Repetitivos),
  `snippets`. Placeholders-as-value a zerar: `IWglobal1`,`IWglobal2`,`num`,`jud`,`tribunais`,`revistas`,`volume`,`pageNum`.
- v1 expõe: `livre(frt)`, `numero(num)`, `relator(jud)`, `tribunais(tribunais)`,
  `data_julg_de/ate` (dateType=between + fromDate/toDate) ou `ano`. Filtros de corte por
  código e GR/RR ficam para fase posterior (mapa de códigos é extenso).

### Parser de resultados (DISTINTO da Doutrina)

Container `div.result` e link `a.documentLink` (iguais), mas:
- título do link = `"<numero_processo> - <relator> - Data de Julgamento <dd/mm/aaaa>"`.
- `p.subTitle` (NÃO `p.author`): 1º = **tribunal**; 2º = `"<diário> | <mês/ano> | JRP\AAAA\NNN"`.
- código do julgado: `JRP\\d{4}\\d+` (não `DTR\`).
- `docguid` no `href`. 50 resultados por página.

Campos extraídos: `numero_processo`, `relator`, `data_julgamento`, `tribunal`,
`veiculo`(diário), `data_publicacao`, `jrp`, `docguid`, `url`.

### Página de documento (jurisprudência)

- Corpo em `#docContent` (extraível, mesmo padrão da Doutrina).
- `infotype` do `#deliveryForm` = **`br_juris`** (Doutrina era `br_doutrina`).
- **Título de artigo não se aplica:** `h1.hTitleDoctrina` vazio; `h1.hTitle` = nome do tribunal.
  O identificador útil vem da linha-cabeçalho do corpo, ex.:
  `"TRT-3.ª Reg. - Recurso Ordinário em Rito Sumaríssimo 0010198-10.2024.5.03.0079 - 6.ª Turma -
  j. 8/10/2024 - julgado por José Murilo de Morais - DEJT 10/10/2024 - Área do Direito: Trabalho"`
  → dela saem `classe`, `numero`, `orgao_julgador`(turma), `data_julgamento`, `relator`,
  `data_publicacao`, `assunto`(área).

### Delivery (PDF/RTF) — REUSÁVEL SEM MUDANÇA

O pipeline offload validado para Doutrina é **collection-agnostic**: ele navega à página do
documento, clica `#saveImage`, lê o `#deliveryForm` da própria página (que já traz o
`infotype` correto — `br_juris` aqui) e segue POST→trigger→poll(`offload/status`)→GET(`offload/get`).
Não precisa saber a coleção. Portado tal qual de `busca-academica-mcp`.

## Objetivos

1. `rt_jurisprudencia_buscar(...)`: busca avançada de jurisprudência RT (livre/numero/relator/
   tribunais/data de julgamento), formato de saída consistente com as demais tools do server.
2. `rt_baixar_pdf(doc_url, destino="")`: baixa o PDF do julgado (pipeline offload).
3. `rt_capturar_md(doc_url, gravar=True)`: grava nota `julgado` na vault a partir do HTML do documento.
4. Camada RT sobre `cdp-scaffold`, com os bits RT portados e validados; degradação honesta
   sem `RT_CDP_URL` (as tools httpx existentes seguem funcionando).

## Não-objetivos

- Legislação/súmulas RT (fase posterior).
- Filtros de corte por código (`queryTC/...`) e GR/RR no v1 (mapa extenso; depois).
- Mudar/tocar as tools httpx existentes (CJF/STJ/BNP/TJDFT) além do `listar_fontes`.
- Compartilhar lib `rt-core` com busca-academica (decisão: portar, não extrair).
- Converter PDF→MD (MD vem do HTML; PDF é binário à parte).

## Arquitetura

Novo subpacote `src/juridico_mcp/rt/` (server-only), sobre `cdp-scaffold`:

- **`rt/auth.py`** — login OnePass/Auth0 via CDP (`login_rt_via_cdp`), portado de
  busca-academica, usando os primitivos de `cdp_scaffold.cdp` (`open_background_tab`,
  `connect`, `cdp_eval`/`eval_in_tab`, `close_target`) em vez do websocket hand-rolled.
- **`rt/session.py`** — `run_search_form(entry_url, fields, *, placeholders, cdp_url, timeout)`
  (navega à entrada da coleção, zera placeholders, seta campos, POST in-page) + relogin
  reativo 1x. Camada genérica de submissão, sobre cdp-scaffold.
- **`rt/delivery.py`** — `baixar_documento(doc_url, formato='PDF'|'RTF') -> (bytes, filename)`
  (offload, collection-agnostic) + `_parse_status_xml` + `_normalizar_filename` (porte direto).
- **`rt/jurisprudencia.py`** — `ENTRY`, `PLACEHOLDERS`, `montar_campos(...)`,
  `parse_resultados(html) -> List[dict]` (parser específico de jurisprudência),
  `buscar(...)`, `extrair_documento(doc_url) -> dict` (lê `#docContent` + parseia a
  linha-cabeçalho em campos de `julgado`).
- **`rt/captura_md.py`** — `html_para_md` (markdownify) + `_limpar_corpo` (remove
  `[class*=relationship]`) — porte de busca-academica.
- **`rt/vault.py`** — `escrever_julgado(meta, corpo_md) -> path` (frontmatter `julgado`,
  pasta `Conhecimento/Fontes/Julgados/RT/`, slug ASCII, validação de YAML válido +
  required `tribunal/classe/numero` presentes).

`server.py` ganha 3 tools finas (`rt_jurisprudencia_buscar`, `rt_baixar_pdf`,
`rt_capturar_md`) + linha no `listar_fontes`. As tools RT capturam exceções e degradam
com mensagem acionável quando `RT_CDP_URL` ausente/CDP inacessível.

### Dependência cdp-scaffold

Adicionar `cdp-scaffold` (path/editable, como em novajus-mcp/leitor-processual-cdp) ao
`pyproject.toml`. Adicionar `markdownify`. `lxml` para os parsers.

## Detalhe — Busca (a)

`montar_campos(livre="", numero="", relator="", tribunais="", ano="", data_de="",
data_ate="")` mapeia: `livre→frt`, `numero→num`, `relator→jud`, `tribunais→tribunais`;
ano único → `dateType=exact`+`ano`/`exactDate`; intervalo → `dateType=between`+`fromDate`/`toDate`
(formato confirmar no mapeamento — placeholder vazio no recon; o plan valida o formato de data
ao vivo). Pelo menos um de livre/numero/relator obrigatório.

## Detalhe — Captura (b)

- `rt_capturar_md`: `extrair_documento(doc_url)` → meta (`tribunal`, `classe`, `numero`,
  `relator`, `data_julgamento`, `data_publicacao`, `orgao_julgador`, `assunto`, `jrp`) +
  HTML `#docContent` limpo → `html_para_md` → nota `julgado`.
- `rt_baixar_pdf`: `delivery.baixar_documento(doc_url, 'PDF')` → grava.

### Pouso na vault (proposta — validar)

- **noteType:** `julgado` (required `tribunal`, `classe`, `numero` — todos extraídos da
  linha-cabeçalho do corpo; se algum faltar, captura falha com erro acionável, não grava nota inválida).
- **Pasta:** `Conhecimento/Fontes/Julgados/RT/` (placement canônico de `julgado` +
  subpasta `RT/`).
- **Frontmatter:** `noteType: julgado`, `tribunal`, `classe`, `numero`, `relator`,
  `data_julgamento`, `data_publicacao`, `orgao_julgador`(turma), `assunto`(área),
  `fonte: "RT Online"`, `codigo: <JRP>`, `url`, `status: ativo`, `temas: []`.
  Escalares de texto entre aspas + `_yaml_escape` (lição da Doutrina: nome com `: ` quebra YAML).
- **Filename:** ASCII do número do processo (ex.: `0010198-10-2024-5-03-0079.md`).
- **PDF:** default `Conhecimento/Fontes/Julgados/RT/_pdf/` (ou `destino`).
- **Vault path:** env `THINKBOX_VAULT_PATH` (server-side; documentar no wrapper de inicialização).

## Tratamento de erro

- `RT_CDP_URL` ausente/CDP inacessível: tool RT retorna erro acionável; tools httpx intactas.
- Sessão expirada: relogin reativo 1x; depois `RuntimeError` honesto.
- `successful=false` no offload: erro acionável, sem fabricar arquivo.
- `#docContent` ausente ou required (`tribunal/classe/numero`) não extraído: não grava nota.

## Testes (sem rede/Chrome/Keychain/vault real)

- `rt/jurisprudencia.parse_resultados`: fixture HTML real de resultados → assert numero/relator/
  tribunal/data/jrp/docguid do 1º e multi.
- `montar_campos`: ano único vs intervalo vs numero/relator → campos corretos.
- `extrair_documento`: fixture do `#docContent` real → assert classe/numero/tribunal/relator/data.
- `delivery._parse_status_xml` / `_normalizar_filename`: unit (porte com testes).
- `captura_md.html_para_md` + `_limpar_corpo`: fixture → MD limpo.
- `vault.escrever_julgado`: tmp_path → frontmatter `julgado` válido (required presentes), filename ASCII.
- tools: monkeypatch das camadas → JSON + degradação sem `RT_CDP_URL`.
- Smoke ao vivo (server): 1 busca + 1 `rt_baixar_pdf` + 1 `rt_capturar_md`.

## Faseamento / Rollout

1. Dep cdp-scaffold + markdownify; esqueleto `rt/` + `auth.py`/`session.py` (porte sobre cdp-scaffold).
2. `rt/jurisprudencia.py` parser + `montar_campos` + `buscar` + tool `rt_jurisprudencia_buscar`.
3. `rt/delivery.py` (porte) + tool `rt_baixar_pdf`.
4. `extrair_documento` + `captura_md` + `rt/vault.py` (julgado) + tool `rt_capturar_md`.
5. `listar_fontes` + README + env de vault + registro no client.
6. Smoke ao vivo.

Cada passo: suíte verde antes de seguir. Commit por passo, pathspec explícito. PR no fim
(repo de software → fluxo de PR).

## Decisões fixadas

1. Casa: `juridico-mcp-server` (RT = carve-out premium/server-only; httpx intactas).
2. Reuso: cdp-scaffold + portar bits RT (não extrair lib compartilhada).
3. v1: jurisprudência busca avançada + captura (PDF + MD→`julgado`). Legislação/súmulas depois.
4. Delivery é collection-agnostic (reuso direto).

## Decisões abertas (revisão do usuário)

- Confirmar noteType `julgado` + pasta `Conhecimento/Fontes/Julgados/RT/` + mapeamento de frontmatter.
- Confirmar conjunto de params do v1 (incluir filtros de corte/GR-RR já, ou só depois?).
- Confirmar nome do env de vault (`THINKBOX_VAULT_PATH`) reusado entre os MCPs.
