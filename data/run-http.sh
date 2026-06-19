#!/bin/bash
# juridico-mcp HTTP transport wrapper (SuperGateway --stdio -> StreamableHttp :5062)
# Install target: /Users/gustavo/Developer/juridico-mcp-server/data/run-http.sh
# Launched by ~/Library/LaunchAgents/com.thinkbox.juridico-mcp-http.plist
set -euo pipefail

# RT (jurisprudencia premium) usa o Chrome dedicado via CDP (OnePass/WLBR) — SERVER-ONLY.
# As fontes httpx (CJF/STJ/BNP/TJDFT) seguem funcionando sem isto.
export RT_CDP_URL="${RT_CDP_URL:-http://127.0.0.1:9222}"
# Captura de julgado (rt_capturar_md) grava nota na vault Obsidian-sync.
export THINKBOX_VAULT_PATH="${THINKBOX_VAULT_PATH:-/Users/gustavo/ThinkBox}"
# Download de PDF (rt_baixar_pdf) grava em OneDrive para acesso multi-maquina.
export RT_DOWNLOAD_DIR="${RT_DOWNLOAD_DIR:-/Users/gustavo/Library/CloudStorage/OneDrive-Pessoal/0_Inbox/RT}"

exec /opt/homebrew/bin/npx -y supergateway \
  --stdio "/Users/gustavo/.local/bin/uv --directory /Users/gustavo/Developer/juridico-mcp-server run juridico-mcp" \
  --outputTransport streamableHttp \
  --streamableHttpPath /mcp \
  --port 5062 \
  --stateful
