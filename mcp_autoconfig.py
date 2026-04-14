#!/usr/bin/env python3
"""
mcp_autoconfig.py - Shared module for MCP server auto-registration.

Detects platform, locates claude_desktop_config.json, and registers/unregisters
an MCP server entry idempotently. Python 3.8+, stdlib only.
"""

import json
import os
import shutil
import sys
from pathlib import Path


def get_config_path():
    """Return the path to claude_desktop_config.json for the current platform."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            raise RuntimeError("APPDATA environment variable not set")
        return Path(appdata) / "Claude" / "claude_desktop_config.json"
    else:
        raise RuntimeError("Unsupported platform: %s" % sys.platform)


def load_config(config_path):
    """Load existing config or return empty skeleton."""
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"mcpServers": {}}


def save_config(config_path, config, dry_run=False):
    """Write config as JSON (UTF-8, no BOM, indent=2). Creates backup first."""
    if dry_run:
        print("\n[dry-run] Would write to: %s" % config_path)
        print(json.dumps(config, indent=2, ensure_ascii=False))
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Backup existing file
    if config_path.exists():
        backup = config_path.with_suffix(".json.bak")
        shutil.copy2(config_path, backup)
        print("Backup: %s" % backup)

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("Written: %s" % config_path)


def register_server(server_name, entry, dry_run=False):
    """Add or update an MCP server entry. Returns action taken."""
    config_path = get_config_path()
    config = load_config(config_path)

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    existing = config["mcpServers"].get(server_name)

    if existing == entry:
        print("[%s] unchanged - already configured correctly." % server_name)
        return "unchanged"

    action = "updated" if existing else "added"
    config["mcpServers"][server_name] = entry
    save_config(config_path, config, dry_run=dry_run)
    if not dry_run:
        print("[%s] %s." % (server_name, action))
    return action


def unregister_server(server_name, dry_run=False):
    """Remove an MCP server entry. Returns action taken."""
    config_path = get_config_path()
    config = load_config(config_path)

    servers = config.get("mcpServers", {})
    if server_name not in servers:
        print("[%s] not found in config - nothing to remove." % server_name)
        return "not_found"

    del servers[server_name]
    save_config(config_path, config, dry_run=dry_run)
    print("[%s] removed." % server_name)
    return "removed"


def find_executable(name):
    """Find absolute path of an executable (cross-platform)."""
    path = shutil.which(name)
    if path:
        return os.path.realpath(path)
    return None
