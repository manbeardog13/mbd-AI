"""Read-only discovery of installed Codex/Claude skills and integration hosts.

Nero does not copy proprietary plugin runtimes or pretend that a Codex-hosted
connector is a local process. Instead, this catalog gives the model a stable,
searchable index of every installed skill and an honest availability state for
each integration. Skill content is read only after the model selects a relevant
skill, which protects the local model's limited context window.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from ...security.gate import RiskClass
from ..registry import Context, Registry, Result

DEFAULT_CACHE_ROOT = (
    Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "plugins" / "cache"
)

REQUESTED_PLUGINS = {
    "computer-use",
    "chrome",
    "browser",
    "visualize",
    "gitkraken-hooks",
    "ruflo-core",
    "ruflo-swarm",
    "github",
    "hugging-face",
}

_HOST_RUNTIMES = {"computer-use", "chrome", "browser", "visualize"}
_MAX_SKILL_CHARS = 32_000
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
_FIELD = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$")


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _frontmatter(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {}
    match = _FRONTMATTER.match(text)
    if not match:
        return {}
    out: dict[str, str] = {}
    for line in match.group(1).splitlines():
        field = _FIELD.match(line)
        if field:
            out[field.group(1)] = field.group(2).strip().strip('"\'')
    return out


def _manifest_at(root: Path) -> tuple[Path | None, dict]:
    for rel in (Path(".codex-plugin/plugin.json"), Path(".claude-plugin/plugin.json")):
        candidate = root / rel
        if candidate.is_file():
            return candidate, _read_json(candidate)
    return None, {}


@dataclass(frozen=True)
class SkillRecord:
    id: str
    name: str
    description: str
    plugin: str
    version: str
    path: Path

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "plugin": self.plugin,
            "version": self.version,
        }


@dataclass(frozen=True)
class PluginRecord:
    name: str
    version: str
    description: str
    root: Path
    skills: int
    transport: str
    availability: str
    mcp_servers: tuple[dict, ...] = ()

    def summary(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "skills": self.skills,
            "transport": self.transport,
            "availability": self.availability,
            "requested": self.name in REQUESTED_PLUGINS,
            "mcp_servers": list(self.mcp_servers),
        }


def _version_key(version: str) -> tuple:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in re.split(r"[.-]", version)
    )


def _server_summaries(root: Path) -> tuple[dict, ...]:
    config = _read_json(root / ".mcp.json")
    servers = config.get("mcpServers")
    if not isinstance(servers, dict):
        return ()
    out: list[dict] = []
    for name, raw in sorted(servers.items()):
        if not isinstance(raw, dict):
            continue
        env = raw.get("env")
        out.append({
            "name": str(name),
            "transport": "stdio",
            "command": str(raw.get("command") or ""),
            "args": [str(v) for v in (raw.get("args") or [])],
            "env_keys": sorted(str(k) for k in env) if isinstance(env, dict) else [],
            "connected": False,
        })
    return tuple(out)


class IntegrationCatalog:
    """A refreshable view over locally installed plugin metadata and skills."""

    def __init__(self, cache_root: Path | str = DEFAULT_CACHE_ROOT, *, ttl: float = 60.0):
        self.cache_root = Path(cache_root)
        self.ttl = max(0.0, float(ttl))
        self._loaded_at = 0.0
        self._skills: dict[str, SkillRecord] = {}
        self._plugins: dict[str, PluginRecord] = {}

    def _ensure(self) -> None:
        if not self._loaded_at or time.monotonic() - self._loaded_at >= self.ttl:
            self.refresh()

    def refresh(self) -> None:
        manifests: list[tuple[Path, dict]] = []
        for rel in ("*/*/*/.codex-plugin/plugin.json", "*/*/*/.claude-plugin/plugin.json"):
            for path in self.cache_root.glob(rel):
                data = _read_json(path)
                if data.get("name"):
                    manifests.append((path, data))

        roots: dict[Path, dict] = {path.parent.parent: data for path, data in manifests}
        skills_by_plugin: dict[str, list[SkillRecord]] = {}
        skill_map: dict[str, SkillRecord] = {}

        for path in self.cache_root.glob("*/*/*/skills/**/SKILL.md"):
            root = next((candidate for candidate in path.parents if candidate in roots), None)
            manifest = roots.get(root, {}) if root else {}
            meta = _frontmatter(path)
            plugin = str(manifest.get("name") or (root.parent.name if root else path.parent.name))
            name = str(meta.get("name") or path.parent.name)
            description = str(meta.get("description") or "").strip()
            version = str(manifest.get("version") or (root.name if root else ""))
            record = SkillRecord(
                id=f"{plugin}:{name}", name=name, description=description,
                plugin=plugin, version=version, path=path,
            )
            previous = skill_map.get(record.id)
            if previous is None or _version_key(record.version) >= _version_key(previous.version):
                skill_map[record.id] = record

        for skill in skill_map.values():
            skills_by_plugin.setdefault(skill.plugin, []).append(skill)

        plugins: dict[str, PluginRecord] = {}
        for root, manifest in roots.items():
            name = str(manifest.get("name") or root.parent.name)
            version = str(manifest.get("version") or root.name)
            app = _read_json(root / ".app.json")
            mcp_servers = _server_summaries(root)
            has_hooks = (root / "hooks/hooks.json").is_file() or (root / "hooks.json").is_file()
            if mcp_servers:
                transport, availability = "mcp-stdio", "ready-after-server-scan"
            elif app.get("apps"):
                transport, availability = "codex-connector", "bridge-backed"
            elif name in _HOST_RUNTIMES:
                transport, availability = "codex-host-runtime", "bridge-backed"
            elif has_hooks:
                transport, availability = "host-hooks", "host-only"
            else:
                transport, availability = "skill-catalog", "local-readable"
            record = PluginRecord(
                name=name,
                version=version,
                description=str(manifest.get("description") or "").strip(),
                root=root,
                skills=len(skills_by_plugin.get(name, [])),
                transport=transport,
                availability=availability,
                mcp_servers=mcp_servers,
            )
            previous = plugins.get(name)
            if previous is None or _version_key(record.version) >= _version_key(previous.version):
                plugins[name] = record

        self._skills = skill_map
        self._plugins = plugins
        self._loaded_at = time.monotonic()

    def skills(self) -> list[SkillRecord]:
        self._ensure()
        return sorted(self._skills.values(), key=lambda s: (s.plugin, s.name))

    def plugins(self) -> list[PluginRecord]:
        self._ensure()
        return sorted(
            self._plugins.values(),
            key=lambda p: (p.name not in REQUESTED_PLUGINS, p.name),
        )

    def search_skills(self, query: str = "", plugin: str = "", limit: int = 20) -> list[SkillRecord]:
        query = query.strip().lower()
        plugin = plugin.strip().lower()
        ranked: list[tuple[int, SkillRecord]] = []
        for skill in self.skills():
            if plugin and plugin not in skill.plugin.lower():
                continue
            haystack = f"{skill.id} {skill.description}".lower()
            if query and query not in haystack:
                continue
            score = (3 if query and query in skill.name.lower() else 0) + (2 if query in skill.id.lower() else 0)
            ranked.append((score, skill))
        ranked.sort(key=lambda pair: (-pair[0], pair[1].plugin, pair[1].name))
        return [skill for _, skill in ranked[:max(1, min(int(limit), 100))]]

    def read_skill(self, skill_id: str) -> tuple[str, bool] | None:
        self._ensure()
        record = self._skills.get(skill_id)
        if record is None:
            return None
        try:
            text = record.path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None
        truncated = len(text) > _MAX_SKILL_CHARS
        return text[:_MAX_SKILL_CHARS], truncated


class IntegrationList:
    name = "integrations.list"
    description = (
        "List every installed integration, how Nero can reach it, and whether it is "
        "local, MCP-ready, Codex-bridge-backed, or host-only. Use before claiming a plugin is callable."
    )
    args_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    risk = RiskClass.SAFE
    provider = "builtin:integration-catalog"

    def __init__(self, catalog: IntegrationCatalog):
        self.catalog = catalog

    def execute(self, args: dict, ctx: Context) -> Result:
        records = [p.summary() for p in self.catalog.plugins()]
        return Result(True, json.dumps(records, ensure_ascii=False), {"count": len(records)})


class SkillSearch:
    name = "skills.search"
    description = (
        "Search all installed Codex/Claude plugin skills. Read the relevant skill with "
        "skills.read before using its workflow; do not load unrelated skills into context."
    )
    args_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "plugin": {"type": "string"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "additionalProperties": False,
    }
    risk = RiskClass.SAFE
    provider = "skill:installed-catalog"

    def __init__(self, catalog: IntegrationCatalog):
        self.catalog = catalog

    def execute(self, args: dict, ctx: Context) -> Result:
        records = self.catalog.search_skills(
            str(args.get("query") or ""), str(args.get("plugin") or ""), args.get("limit") or 20,
        )
        payload = [record.summary() for record in records]
        return Result(True, json.dumps(payload, ensure_ascii=False), {"count": len(payload)})


class SkillRead:
    name = "skills.read"
    description = (
        "Read one installed skill by the stable id returned from skills.search. The id, not a "
        "filesystem path, is required so plugin files outside the project cannot be read arbitrarily."
    )
    args_schema = {
        "type": "object",
        "properties": {"skill_id": {"type": "string"}},
        "required": ["skill_id"],
        "additionalProperties": False,
    }
    risk = RiskClass.SAFE
    provider = "skill:installed-catalog"

    def __init__(self, catalog: IntegrationCatalog):
        self.catalog = catalog

    def execute(self, args: dict, ctx: Context) -> Result:
        skill_id = str(args.get("skill_id") or "").strip()
        loaded = self.catalog.read_skill(skill_id)
        if loaded is None:
            return Result(False, f"Unknown or unreadable skill: {skill_id!r}.", {"unknown": True})
        text, truncated = loaded
        return Result(True, text, {"skill_id": skill_id, "truncated": truncated})


class MCPCatalog:
    name = "mcp.catalog"
    description = (
        "List installed MCP server definitions and Codex-hosted connector families without "
        "starting processes or exposing environment values. Use it to choose a real provider."
    )
    args_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    risk = RiskClass.SAFE
    provider = "builtin:integration-catalog"

    def __init__(self, catalog: IntegrationCatalog):
        self.catalog = catalog

    def execute(self, args: dict, ctx: Context) -> Result:
        providers = [
            p.summary() for p in self.catalog.plugins()
            if p.transport in {"mcp-stdio", "codex-connector", "codex-host-runtime", "host-hooks"}
        ]
        return Result(True, json.dumps(providers, ensure_ascii=False), {"count": len(providers)})


class CodexBridgeInstructions:
    name = "codex.bridge.instructions"
    description = (
        "Get the structured handoff format for a capability that is available only through the "
        "active Codex task. This never invokes a host tool by itself."
    )
    args_schema = {"type": "object", "properties": {}, "additionalProperties": False}
    risk = RiskClass.SAFE
    provider = "builtin:codex-bridge"

    def execute(self, args: dict, ctx: Context) -> Result:
        contract = {
            "marker": "CODEX_BRIDGE_REQUEST",
            "required": ["integration", "action", "arguments", "reason"],
            "rule": (
                "Return this request to Toni in the active conversation. Codex may execute it only "
                "while actively brokering the task and will apply the host tool's own confirmations."
            ),
            "example": {
                "integration": "github",
                "action": "list pull requests",
                "arguments": {"repository": "owner/repo"},
                "reason": "The task needs current repository state.",
            },
        }
        return Result(True, json.dumps(contract, ensure_ascii=False), contract)


def register_integration_capabilities(
    registry: Registry,
    *,
    catalog: IntegrationCatalog | None = None,
) -> IntegrationCatalog:
    """Register the always-available catalog capabilities and return their catalog."""
    catalog = catalog or IntegrationCatalog()
    registry.register(IntegrationList(catalog))
    registry.register(SkillSearch(catalog))
    registry.register(SkillRead(catalog))
    registry.register(MCPCatalog(catalog))
    registry.register(CodexBridgeInstructions())
    return catalog
