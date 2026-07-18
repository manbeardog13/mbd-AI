#!/usr/bin/env python3
"""Offline verification for Nero's installed skill and MCP integration catalog."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.capabilities import Context, Registry  # noqa: E402
from app.capabilities.integrations import IntegrationCatalog  # noqa: E402
from app.capabilities.integrations.catalog import (  # noqa: E402
    REQUESTED_PLUGINS,
    register_integration_capabilities,
)


def main() -> int:
    catalog = IntegrationCatalog(ttl=0)
    plugins = catalog.plugins()
    names = {plugin.name for plugin in plugins}
    skills = catalog.skills()
    missing = sorted(REQUESTED_PLUGINS - names)

    reg = Registry()
    register_integration_capabilities(reg, catalog=catalog)
    ctx = Context(allowed_dirs=[str(Path(__file__).resolve().parent.parent)])
    listing = reg.dispatch("integrations.list", {}, ctx)
    skill_listing = reg.dispatch("skills.search", {"limit": 100}, ctx)
    mcp_listing = reg.dispatch("mcp.catalog", {}, ctx)

    checks = {
        "all requested plugins discovered": not missing,
        "installed skills discovered": len(skills) >= 10,
        "integration list is callable without a model": listing.ok,
        "skill search is callable without a model": skill_listing.ok,
        "MCP catalog is callable without starting servers": mcp_listing.ok,
        "Ruflo stdio definition found": any(p.name == "ruflo-core" and p.mcp_servers for p in plugins),
        "GitHub bridge connector found": any(p.name == "github" and p.transport == "codex-connector" for p in plugins),
        "Hugging Face bridge connector found": any(p.name == "hugging-face" and p.transport == "codex-connector" for p in plugins),
    }
    for label, ok in checks.items():
        print(f"  {'OK' if ok else 'XX'} {label}")
    print(f"     -> {len(plugins)} plugins, {len(skills)} skills; no MCP server launched")
    if missing:
        print(f"     -> missing: {', '.join(missing)}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
