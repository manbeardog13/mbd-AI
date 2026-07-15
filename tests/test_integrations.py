"""Offline tests for installed-skill discovery and guarded MCP registration."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.capabilities import Context, Registry
from app.capabilities.integrations.catalog import IntegrationCatalog, register_integration_capabilities
from app.capabilities.integrations.mcp import infer_mcp_risk, register_mcp_tools
from app.security.gate import RiskClass


class FakeMCP:
    def __init__(self):
        self.calls = []

    def list_tools(self):
        return [
            {
                "name": "list_items", "description": "List items.",
                "inputSchema": {"type": "object", "properties": {}},
                "annotations": {"readOnlyHint": True},
            },
            {
                "name": "delete_item", "description": "Delete an item.",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
                "annotations": {"destructiveHint": True},
            },
        ]

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return {"content": [{"type": "text", "text": f"called:{name}"}], "isError": False}


def _fixture(root: Path) -> None:
    plugin = root / "vendor" / "example" / "1.2.3"
    (plugin / ".codex-plugin").mkdir(parents=True)
    (plugin / "skills" / "demo").mkdir(parents=True)
    (plugin / ".codex-plugin" / "plugin.json").write_text(json.dumps({
        "name": "example", "version": "1.2.3", "description": "Example plugin",
    }), encoding="utf-8")
    (plugin / "skills" / "demo" / "SKILL.md").write_text(
        '---\nname: demo\ndescription: "Demonstrate discovery"\n---\n\n# Demo\nUse carefully.\n',
        encoding="utf-8",
    )
    (plugin / ".mcp.json").write_text(json.dumps({
        "mcpServers": {"example": {
            "command": "example-mcp", "args": ["--stdio"], "env": {"SECRET": "not-exported"},
        }}
    }), encoding="utf-8")


def test_skill_catalog_discovers_searches_and_reads_by_id():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fixture(root)
        catalog = IntegrationCatalog(root, ttl=0)
        found = catalog.search_skills("discovery")
        assert [skill.id for skill in found] == ["example:demo"]
        loaded = catalog.read_skill("example:demo")
        assert loaded and "Use carefully" in loaded[0]
        assert catalog.read_skill("../../secrets") is None


def test_catalog_redacts_mcp_environment_values():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fixture(root)
        plugin = IntegrationCatalog(root, ttl=0).plugins()[0].summary()
        server = plugin["mcp_servers"][0]
        assert server["env_keys"] == ["SECRET"]
        assert "not-exported" not in json.dumps(plugin)


def test_catalog_capabilities_are_registered_and_safe():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fixture(root)
        reg = Registry()
        register_integration_capabilities(reg, catalog=IntegrationCatalog(root, ttl=0))
        names = {spec["name"] for spec in reg.specs()}
        assert {"integrations.list", "skills.search", "skills.read", "mcp.catalog"} <= names
        result = reg.dispatch("skills.read", {"skill_id": "example:demo"}, Context(allowed_dirs=[tmp]))
        assert result.ok and "# Demo" in result.output


def test_mcp_tools_register_individually_with_risk():
    client = FakeMCP()
    reg = Registry()
    caps = register_mcp_tools(reg, "example", client)
    assert [cap.risk for cap in caps] == [RiskClass.SAFE, RiskClass.HIGH]
    safe = reg.dispatch("mcp.example.list.items", {}, Context(allowed_dirs=["."]))
    assert safe.ok and client.calls == [("list_items", {})]
    denied = reg.dispatch(
        "mcp.example.delete.item", {"id": "1"}, Context(allowed_dirs=["."], confirm=None),
    )
    assert not denied.ok and len(client.calls) == 1


def test_mcp_annotations_cannot_deescalate_named_mutation():
    tool = {"name": "delete_everything", "annotations": {"readOnlyHint": True}}
    assert infer_mcp_risk(tool) == RiskClass.HIGH


def test_download_is_not_treated_as_read_only():
    tool = {"name": "download_artifact", "annotations": {"readOnlyHint": True}}
    assert infer_mcp_risk(tool) == RiskClass.HIGH


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} integration tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
