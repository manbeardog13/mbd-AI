"""Minimal MCP stdio client and guarded per-tool capability adapter.

No MCP server is launched merely because Nero starts. A trusted, scanned server
definition must be selected first; only then does the client launch it on demand.
Discovered tools register individually, so read-only and mutating operations can
receive different risk classes at the existing Registry choke point.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Protocol

from ...security.gate import RiskClass
from ..registry import Context, Registry, Result

log = logging.getLogger("nero.capabilities.mcp")
PROTOCOL_VERSION = "2025-03-26"

_READ_PREFIXES = (
    "get", "list", "read", "search", "find", "fetch", "inspect", "status",
    "health", "show", "view", "query", "compare", "whoami",
)
_WRITE_PREFIXES = (
    "add", "create", "update", "delete", "remove", "merge", "push", "write",
    "upload", "publish", "send", "reply", "resolve", "unresolve", "lock",
    "unlock", "rerun", "enable", "disable", "download", "install", "spawn", "run", "execute",
)
_CRITICAL_WORDS = ("credential", "secret", "token", "password", "wipe", "format_disk")


class MCPClient(Protocol):
    def list_tools(self) -> list[dict]: ...
    def call_tool(self, name: str, arguments: dict) -> dict: ...


@dataclass(frozen=True)
class MCPServerSpec:
    name: str
    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0


def infer_mcp_risk(tool: dict, overrides: dict[str, RiskClass] | None = None) -> RiskClass:
    """Classify an MCP tool conservatively; server annotations are untrusted hints."""
    name = str(tool.get("name") or "").lower()
    if overrides and name in overrides:
        return overrides[name]
    if any(word in name for word in _CRITICAL_WORDS):
        return RiskClass.CRITICAL
    if name.startswith(_WRITE_PREFIXES):
        return RiskClass.HIGH
    annotations = tool.get("annotations")
    read_hint = isinstance(annotations, dict) and annotations.get("readOnlyHint") is True
    destructive_hint = isinstance(annotations, dict) and annotations.get("destructiveHint") is True
    if destructive_hint:
        return RiskClass.HIGH
    if read_hint and name.startswith(_READ_PREFIXES):
        return RiskClass.SAFE
    if name.startswith(_READ_PREFIXES):
        return RiskClass.SAFE
    return RiskClass.MEDIUM


def _safe_name(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "." for ch in value)
    return ".".join(part for part in cleaned.split(".") if part)


def _flatten_content(result: dict) -> str:
    chunks: list[str] = []
    for item in result.get("content") or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind == "text":
            chunks.append(str(item.get("text") or ""))
        elif kind in {"image", "audio"}:
            chunks.append(f"[{kind} content returned; binary data withheld from model context]")
        elif kind == "resource":
            resource = item.get("resource") or {}
            if isinstance(resource, dict):
                chunks.append(str(resource.get("text") or resource.get("uri") or "[resource]"))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


class MCPToolCapability:
    """One discovered MCP tool presented as a normal guarded Nero capability."""

    def __init__(
        self,
        server_name: str,
        tool: dict,
        client: MCPClient,
        *,
        risk: RiskClass | None = None,
    ):
        remote_name = str(tool.get("name") or "").strip()
        if not remote_name:
            raise ValueError("MCP tool has no name")
        self.remote_name = remote_name
        self.name = f"mcp.{_safe_name(server_name)}.{_safe_name(remote_name)}"
        self.description = str(tool.get("description") or f"MCP tool {remote_name}")
        schema = tool.get("inputSchema")
        self.args_schema = schema if isinstance(schema, dict) else {
            "type": "object", "properties": {}, "additionalProperties": True,
        }
        self.risk = risk or infer_mcp_risk(tool)
        self.provider = f"mcp:{server_name}"
        self._client = client

    def execute(self, args: dict, ctx: Context) -> Result:
        raw = self._client.call_tool(self.remote_name, args or {})
        if not isinstance(raw, dict):
            return Result(False, f"{self.remote_name} returned an invalid MCP result.")
        is_error = bool(raw.get("isError"))
        output = _flatten_content(raw) or json.dumps(raw, ensure_ascii=False)
        content_types = [
            str(item.get("type")) for item in (raw.get("content") or [])
            if isinstance(item, dict) and item.get("type")
        ]
        return Result(not is_error, output, {
            "server": self.provider,
            "remote_tool": self.remote_name,
            "is_error": is_error,
            "content_types": content_types,
        })


def register_mcp_tools(
    registry: Registry,
    server_name: str,
    client: MCPClient,
    *,
    risk_overrides: dict[str, RiskClass] | None = None,
) -> list[MCPToolCapability]:
    """Discover and register every tool from one already-approved MCP client."""
    registered: list[MCPToolCapability] = []
    for tool in client.list_tools():
        remote_name = str(tool.get("name") or "").lower()
        cap = MCPToolCapability(
            server_name, tool, client,
            risk=(risk_overrides or {}).get(remote_name) or infer_mcp_risk(tool, risk_overrides),
        )
        registry.register(cap)
        registered.append(cap)
    return registered


class StdioMCPClient:
    """Sequential JSON-RPC client for the MCP newline-delimited stdio transport."""

    def __init__(self, spec: MCPServerSpec):
        self.spec = spec
        self._process: subprocess.Popen[str] | None = None
        self._messages: queue.Queue[dict] = queue.Queue()
        self._write_lock = threading.RLock()
        self._request_lock = threading.RLock()
        self._next_id = 0
        self._initialized = False

    def _start(self) -> None:
        if self._process and self._process.poll() is None:
            return
        executable = shutil.which(self.spec.command)
        if not executable:
            raise FileNotFoundError(f"MCP command not found: {self.spec.command}")
        env = os.environ.copy()
        env.update({str(k): str(v) for k, v in self.spec.env.items()})
        self._process = subprocess.Popen(
            [executable, *self.spec.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            shell=False,
        )
        threading.Thread(target=self._read_stdout, daemon=True, name=f"mcp-{self.spec.name}-out").start()
        threading.Thread(target=self._drain_stderr, daemon=True, name=f"mcp-{self.spec.name}-err").start()
        self._initialize()

    def _read_stdout(self) -> None:
        process = self._process
        if not process or not process.stdout:
            return
        for line in process.stdout:
            try:
                message = json.loads(line)
                if isinstance(message, dict):
                    self._messages.put(message)
                elif isinstance(message, list):
                    for item in message:
                        if isinstance(item, dict):
                            self._messages.put(item)
            except json.JSONDecodeError:
                log.warning("MCP %s wrote non-JSON stdout", self.spec.name)

    def _drain_stderr(self) -> None:
        process = self._process
        if not process or not process.stderr:
            return
        for line in process.stderr:
            log.debug("MCP %s: %s", self.spec.name, line.rstrip())

    def _send(self, message: dict) -> None:
        process = self._process
        if not process or process.poll() is not None or not process.stdin:
            raise RuntimeError(f"MCP server {self.spec.name} is not running")
        encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        if "\n" in encoded:
            raise ValueError("MCP stdio message contains an embedded newline")
        with self._write_lock:
            process.stdin.write(encoded + "\n")
            process.stdin.flush()

    def _request_raw(self, method: str, params: dict | None = None) -> dict:
        with self._request_lock:
            self._next_id += 1
            request_id = self._next_id
            message = {"jsonrpc": "2.0", "id": request_id, "method": method}
            if params is not None:
                message["params"] = params
            self._send(message)
            deadline = time.monotonic() + max(1.0, self.spec.timeout_seconds)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"MCP {self.spec.name} timed out during {method}")
                try:
                    response = self._messages.get(timeout=remaining)
                except queue.Empty as exc:
                    raise TimeoutError(f"MCP {self.spec.name} timed out during {method}") from exc
                if response.get("id") == request_id and ("result" in response or "error" in response):
                    if "error" in response:
                        error = response.get("error") or {}
                        raise RuntimeError(str(error.get("message") or error))
                    result = response.get("result")
                    return result if isinstance(result, dict) else {}
                # Nero does not expose sampling/elicitation to MCP servers. Refuse
                # server-to-client requests explicitly instead of letting them hang.
                if "method" in response and "id" in response:
                    self._send({
                        "jsonrpc": "2.0", "id": response["id"],
                        "error": {"code": -32601, "message": "Client method not supported"},
                    })

    def _initialize(self) -> None:
        if self._initialized:
            return
        self._request_raw("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "nero", "version": "0.1"},
        })
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    def _request(self, method: str, params: dict | None = None) -> dict:
        self._start()
        return self._request_raw(method, params)

    def list_tools(self) -> list[dict]:
        tools: list[dict] = []
        cursor: str | None = None
        for _ in range(100):
            params = {"cursor": cursor} if cursor else {}
            result = self._request("tools/list", params)
            tools.extend(tool for tool in (result.get("tools") or []) if isinstance(tool, dict))
            cursor = result.get("nextCursor")
            if not cursor:
                return tools
        raise RuntimeError(f"MCP {self.spec.name} exceeded 100 tool-list pages")

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self._request("tools/call", {"name": name, "arguments": arguments or {}})

    def close(self) -> None:
        process = self._process
        self._process = None
        self._initialized = False
        if not process:
            return
        try:
            if process.stdin:
                process.stdin.close()
            process.wait(timeout=2.0)
        except Exception:  # noqa: BLE001 - shutdown is best effort
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except Exception:  # noqa: BLE001
                process.kill()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()
