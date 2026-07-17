"""Deterministic and live audits for zero-start Nero Host Presence."""
from __future__ import annotations

import argparse
import ast
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
CAPSULE_PATH = ROOT / "docs" / "NERO_GLOBAL_CAPSULE.md"
PROJECT_AGENTS_PATH = ROOT / "AGENTS.md"
HOOKS_PATH = ROOT / ".codex" / "hooks.json"
HOST_CONFIG_PATH = ROOT / ".codex" / "nero-host.json"
RUNTIME_PATH = ROOT / "docs" / "NERO_CODEX_RUNTIME.md"
MEMORY_PATH = ROOT / "docs" / "NERO_CODEX_MEMORY.md"
LEGACY_RUNTIME_PATHS = (
    ROOT / "scripts" / "nero_host_voice.py",
    ROOT / "scripts" / "nero_voice_startup.py",
    ROOT / "scripts" / "nero_voice_stop_hook.py",
    ROOT / "scripts" / "nero_voice_warmup.py",
)
PYTHON_LOCAL_ENTRY_PATHS = (
    ROOT / "run.py",
    ROOT / "bootstrap.py",
    ROOT / "app" / "main.py",
    *LEGACY_RUNTIME_PATHS,
)
SHELL_LOCAL_ENTRY_PATHS = (
    ROOT / "start.bat",
    ROOT / "start.sh",
    ROOT / "update-nero.bat",
    ROOT / "scripts" / "wake-nero.ps1",
    ROOT / "Start-NERO.ps1",
)
HISTORICAL_DOC_PATHS = (
    ROOT / "README.md",
    ROOT / "docs" / "ALWAYS_ON.md",
    ROOT / "docs" / "SETUP.md",
    ROOT / "docs" / "MODELS.md",
)
TRACKED_REQUIRED_PATHS = (
    ".codex/hooks.json",
    ".codex/nero-host.json",
    "AGENTS.md",
    "README.md",
    "Start-NERO.ps1",
    "app/main.py",
    "bootstrap.py",
    "docs/guides/ALWAYS_ON.md",
    "docs/HOST_VOICE.md",
    "docs/guides/MODELS.md",
    "docs/NERO_CODEX_MEMORY.md",
    "docs/NERO_CODEX_RUNTIME.md",
    "docs/NERO_GLOBAL_CAPSULE.md",
    "docs/NERO_GLOBAL_PRESENCE_ACCEPTANCE.md",
    "docs/guides/SETUP.md",
    "docs/adr/0014-zero-start-global-host-presence.md",
    "docs/reviews/2026-07-14-zero-start-host-presence-audit.md",
    "run.py",
    "scripts/nero_host_voice.py",
    "scripts/nero_voice_startup.py",
    "scripts/nero_voice_stop_hook.py",
    "scripts/nero_voice_warmup.py",
    "scripts/wake-nero.ps1",
    "start.bat",
    "start.sh",
    "tests/run_nero_host_contract.py",
    "tests/test_nero_global_presence.py",
    "tests/test_nero_host_voice.py",
    "tests/test_nero_local_runtime_lock.py",
    "tests/test_nero_voice_startup.py",
    "tests/test_nero_voice_stop_hook.py",
    "tests/test_nero_voice_warmup.py",
    "update-nero.bat",
    "verify/verify_nero_global_presence.py",
)

CAPSULE_START = "<!-- NERO_GLOBAL_CAPSULE_V1:BEGIN -->"
CAPSULE_END = "<!-- NERO_GLOBAL_CAPSULE_V1:END -->"
EXPECTED_HOST_CONFIG: dict[str, Any] = {
    "version": 2,
    "mode": "host",
    "runtime_policy": "hosted-only",
    "presence_source": "global-static-capsule",
    "presence_capsule_version": "NERO_GLOBAL_CAPSULE_V1",
    "delivery": "text-only-until-hosted-voice-channel",
    "local_model_inference": False,
    "voice_enabled": False,
    "auto_speak": False,
    "desktop_voice_warmup": False,
    "background_processes": False,
    "project_server_startup": False,
    "memory_preload": False,
    "local_fallback": False,
}


class AuditFailure(RuntimeError):
    """Raised when a presence invariant is violated."""


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AuditFailure(message)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AuditFailure(f"cannot read {path}: {exc}") from exc


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise AuditFailure(f"invalid JSON in {path}: {exc}") from exc
    _assert(isinstance(value, dict), f"{path} must contain one JSON object")
    return value


def extract_capsule(text: str, *, source: str) -> str:
    """Return the single marked capsule block, including its markers."""
    if text.count(CAPSULE_START) != 1 or text.count(CAPSULE_END) != 1:
        raise AuditFailure(f"{source} must contain exactly one capsule marker pair")
    start = text.find(CAPSULE_START)
    end_start = text.find(CAPSULE_END)
    if start < 0 or end_start <= start:
        raise AuditFailure(f"{source} capsule markers are reversed or malformed")
    end = end_start + len(CAPSULE_END)
    return text[start:end].replace("\r\n", "\n").strip()


def _assert_python_constant_true(path: Path) -> None:
    try:
        tree = ast.parse(_read(path), filename=str(path))
    except SyntaxError as exc:
        raise AuditFailure(f"cannot parse {path}: {exc}") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "HOSTED_ONLY_HARD_DISABLED"
            for target in node.targets
        ):
            _assert(
                isinstance(node.value, ast.Constant) and node.value.value is True,
                f"HOSTED_ONLY_HARD_DISABLED must be the literal True in {path}",
            )
            return
    raise AuditFailure(f"missing hard-disable constant in {path}")


def _assert_shell_guard(path: Path) -> None:
    text = _read(path)
    folded = text.casefold()
    marker = folded.find("hosted_only_hard_disabled = true")
    exits = [index for token in ("exit 2", "exit /b 2") if (index := folded.find(token)) >= 0]
    _assert(marker >= 0 and exits, f"missing hosted-only exit guard in {path}")
    exit_index = min(exits)
    _assert(marker < exit_index, f"hard-disable marker must precede exit in {path}")

    executable = "\n".join(
        line for line in folded.splitlines()
        if not line.lstrip().startswith(("#", "rem "))
    )
    executable_exit = min(
        index for token in ("exit 2", "exit /b 2")
        if (index := executable.find(token)) >= 0
    )
    for token in ("start-process", "ollama serve", "ollama run", " run.py", "bootstrap.py", "git reset --hard"):
        risk = executable.find(token)
        _assert(risk < 0 or executable_exit < risk, f"local side effect precedes exit guard in {path}: {token}")


def audit_project() -> list[str]:
    checks: list[str] = []
    canonical = extract_capsule(_read(CAPSULE_PATH), source=str(CAPSULE_PATH))
    word_count = len(canonical.split())
    canonical_flat = " ".join(canonical.split())
    _assert(word_count <= 650, f"global capsule is too large: {word_count} words")
    for phrase in (
        "under normal Codex instruction precedence",
        "Nero's voice is warm, curious, sharp, calm, mature, and protective",
        "Codex supplies Nero's reasoning",
        "Never start or call Ollama",
        "No greeting, presence check, fallback, missing context, or wake phrase",
        "text-only until Codex provides a supported hosted",
    ):
        _assert(phrase in canonical_flat, f"canonical capsule is missing required clause: {phrase}")
    checks.append(f"canonical capsule: {word_count} words")

    project_agents = _read(PROJECT_AGENTS_PATH)
    for banned in ("nero_voice_startup", "Kokoro warmup", "explicit wake"):
        _assert(banned not in project_agents, f"project AGENTS contains stale startup clause: {banned}")
    _assert("NERO_GLOBAL_CAPSULE_V1" in project_agents, "project AGENTS does not inherit the global capsule")
    _assert("separately opted-in" in project_agents or "explicit, transparent opt-in" in project_agents,
            "project AGENTS must distinguish hosted Host Mode from the local application")
    checks.append("project instructions: hosted-only, no startup preload")

    _assert(_read_json_object(HOOKS_PATH) == {"hooks": {}}, "project hooks must be completely empty")
    checks.append("project hooks: empty")

    config = _read_json_object(HOST_CONFIG_PATH)
    _assert(config == EXPECTED_HOST_CONFIG, "host config must exactly match the closed hosted-only schema")
    checks.append("host configuration: exact closed hosted-only schema")

    combined_docs = _read(RUNTIME_PATH) + "\n" + _read(MEMORY_PATH)
    for stale in ("Host Voice is enabled", "explicit wake only", "launches one detached", "Warm the CPU-only Kokoro", "ESET scanning"):
        _assert(stale not in combined_docs, f"runtime or memory contains stale policy: {stale}")
    _assert("separately opted-in hosted Codex interface/persona" in combined_docs,
            "runtime/memory must distinguish Host Presence from the local application")
    checks.append("runtime and memory: aligned with zero-start hosted interface")

    for path in PYTHON_LOCAL_ENTRY_PATHS:
        _assert_python_constant_true(path)
    app_main = _read(ROOT / "app" / "main.py")
    guard_index = app_main.find("if HOSTED_ONLY_HARD_DISABLED:")
    side_effect_indices = tuple(
        index for token in ("cfg = load_config()", "db.init_db()")
        if (index := app_main.find(token)) >= 0
    )
    _assert(side_effect_indices and guard_index >= 0 and guard_index < min(side_effect_indices),
            "app startup must stop before configuration/database/service startup")
    _assert('@app.middleware("http")' in app_main and "status_code=410" in app_main,
            "local API must reject every request under the hosted-only lock")
    for path in SHELL_LOCAL_ENTRY_PATHS:
        _assert_shell_guard(path)
    checks.append("legacy local launch, API, model, and voice paths: hard-disabled")

    for path in HISTORICAL_DOC_PATHS:
        beginning = "\n".join(_read(path).splitlines()[:12]).casefold()
        _assert("historical" in beginning and "hard-disabled" in beginning,
                f"legacy local instructions lack a prominent lock notice: {path}")
    checks.append("legacy local documentation: prominently quarantined")
    return checks


def _active_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME", "").strip()
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _normalise_plugin_identity(value: Any) -> str:
    return "".join(character for character in json.dumps(value, sort_keys=True).casefold() if character.isalnum())


def audit_user_state(
    global_agents_path: Path | None = None,
    *,
    override_path: Path | None = None,
    marketplace_paths: Iterable[Path] | None = None,
    plugin_roots: Iterable[Path] | None = None,
    codex_config_path: Path | None = None,
) -> list[str]:
    checks: list[str] = []
    codex_home = _active_codex_home()
    global_agents_path = global_agents_path or codex_home / "AGENTS.md"
    override_path = override_path or global_agents_path.with_name("AGENTS.override.md")
    if override_path.exists():
        _assert(not _read(override_path).strip(), f"active global override shadows Nero capsule: {override_path}")

    canonical = extract_capsule(_read(CAPSULE_PATH), source=str(CAPSULE_PATH))
    deployed_text = _read(global_agents_path)
    deployed = extract_capsule(deployed_text, source=str(global_agents_path))
    _assert(deployed == canonical, "deployed global capsule differs from canonical source")
    outside = deployed_text.replace(deployed, "", 1).casefold()
    for conflict in ("wake local nero", "activate nero's local model", "nero_voice_startup", "nero-host"):
        _assert(conflict not in outside, f"conflicting global Nero instruction remains outside capsule: {conflict}")
    checks.append(f"global deployment: exact active match at {global_agents_path}")

    if marketplace_paths is None:
        marketplace_paths = (Path.home() / ".agents" / "plugins" / "marketplace.json",)
    for path in marketplace_paths:
        if not path.exists():
            continue
        marketplace = _read_json_object(path)
        plugins = marketplace.get("plugins", [])
        _assert(isinstance(plugins, list), f"marketplace plugins must be a list: {path}")
        for item in plugins:
            _assert(isinstance(item, dict), f"marketplace plugin entry must be an object: {path}")
            _assert("nerohost" not in _normalise_plugin_identity(item),
                    f"unfinished nero-host plugin alias remains registered: {path}")

    if plugin_roots is None:
        plugin_roots = (Path.home() / "plugins", Path.home() / ".agents" / "plugins")
    for root in plugin_roots:
        if not root.exists():
            continue
        try:
            children = tuple(root.iterdir())
        except OSError as exc:
            raise AuditFailure(f"cannot inspect plugin root {root}: {exc}") from exc
        for child in children:
            identity = "".join(character for character in child.name.casefold() if character.isalnum())
            _assert(identity != "nerohost", f"unfinished nero-host plugin path remains: {child}")

    codex_config_path = codex_config_path or codex_home / "config.toml"
    if codex_config_path.exists():
        config_folded = _read(codex_config_path).casefold().replace("_", "-")
        _assert("nero-host" not in config_folded, f"nero-host remains registered in {codex_config_path}")
    checks.append("personal plugin state: no nero-host scaffold, alias, or registration")
    return checks


def audit_live_state() -> list[str]:
    checks: list[str] = []
    for port in (8080, 11434):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.25)
            _assert(connection.connect_ex(("127.0.0.1", port)) != 0,
                    f"local Nero/Ollama port is listening: {port}")
    checks.append("live ports: 8080 and 11434 closed")

    if os.name == "nt":
        startup_shortcut = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/Ollama.lnk"
        _assert(not startup_shortcut.exists(), f"Ollama remains enabled at login: {startup_shortcut}")
        command = (
            "Get-CimInstance Win32_Process | Where-Object { "
            "$_.Name -in @('ollama.exe','ollama app.exe') -or "
            "(($_.Name -in @('python.exe','pythonw.exe')) -and $_.CommandLine -match "
            "'(?i)(mbd AI|mbd-AI).*(run.py|bootstrap.py|nero_voice)') } | "
            "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress"
        )
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AuditFailure(f"cannot inspect Windows process state: {exc}") from exc
        _assert(result.returncode == 0, f"Windows process audit failed: {result.stderr.strip()}")
        _assert(not result.stdout.strip(), f"local Nero/Ollama process is running: {result.stdout.strip()}")
        checks.append("live processes/startup: no local Nero or Ollama runtime")
    else:
        checks.append("live process/startup audit: Windows-specific portion skipped")
    return checks


def audit_git_state() -> list[str]:
    checks: list[str] = []
    for relative in TRACKED_REQUIRED_PATHS:
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        _assert(result.returncode == 0, f"required implementation file is not tracked: {relative}")
    checks.append(f"git tracking: {len(TRACKED_REQUIRED_PATHS)} required files tracked")
    return checks


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-user-state", action="store_true",
                        help="audit active global instructions and personal plugin state")
    parser.add_argument("--global-agents", type=Path, default=None,
                        help="override active global AGENTS.md (normally resolved through CODEX_HOME)")
    parser.add_argument("--audit-live-state", action="store_true",
                        help="also require local Nero/Ollama ports, processes, and login startup to be off")
    parser.add_argument("--audit-git", action="store_true",
                        help="also require every implementation artifact to be Git-tracked")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        checks = audit_project()
        if args.audit_user_state:
            checks.extend(audit_user_state(args.global_agents))
        if args.audit_live_state:
            checks.extend(audit_live_state())
        if args.audit_git:
            checks.extend(audit_git_state())
    except AuditFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print("Nero global presence audit passed")
    for check in checks:
        print(f"- {check}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
