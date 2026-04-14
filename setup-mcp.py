#!/usr/bin/env python3
"""
setup-mcp.py - Register/unregister the juridico MCP server in Claude Desktop.

Usage:
    python setup-mcp.py              # Register server
    python setup-mcp.py --dry-run    # Preview without writing
    python setup-mcp.py --uninstall  # Remove server entry
    python setup-mcp.py --remove     # Same as --uninstall
"""

import sys
from pathlib import Path

# Import shared module from same directory
sys.path.insert(0, str(Path(__file__).parent))
from mcp_autoconfig import find_executable, register_server, unregister_server

SERVER_NAME = "juridico"
REPO_DIR = str(Path(__file__).parent.resolve())


def build_entry():
    """Build the mcpServers entry for juridico."""
    uv_path = find_executable("uv")
    if not uv_path:
        print("ERROR: uv not found in PATH.")
        print("Install uv: https://docs.astral.sh/uv/getting-started/installation/")
        sys.exit(1)

    return {
        "command": uv_path,
        "args": ["--directory", REPO_DIR, "run", "juridico-mcp"],
    }


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    uninstall = "--uninstall" in args or "--remove" in args

    if uninstall:
        unregister_server(SERVER_NAME, dry_run=dry_run)
    else:
        entry = build_entry()
        register_server(SERVER_NAME, entry, dry_run=dry_run)


if __name__ == "__main__":
    main()
