#!/usr/bin/env python3
"""Deterministically verify the canonical knowledge base (docs/canon standard).

Mechanizes the 2026-07-16/17 manual audits: index drift, frontmatter schema,
supersession banners, relative-link integrity, ADR log consistency, and the
onboarding read-order contract. Standalone; not wired into verify_everything
(that file is app-owned). House output: JSON {ok, checks}, exit 0/1.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__",
             "data", "models", "output", "_nero_preview"}
LAYERS = {"core", "operational", "archival"}
STATUSES = {"proposed", "active", "superseded", "archived"}
OWNERS = {"toni", "shared", "claude-lane", "codex-lane", "school"}
TYPES = {"constitution", "adr", "spec", "standard", "report", "plan", "guide",
         "handoff", "review", "reference", "index", "log"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
LINK_EXTS = (".md", ".py", ".json", ".yaml", ".yml", ".txt", ".sql", ".png", ".webp", ".sh", ".ps1", ".bat")


def skipped(path: Path, root: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.relative_to(root).parts)


def knowledge_files(root: Path):
    for p in sorted(root.rglob("*.md")):
        if not skipped(p, root):
            yield p


def parse_frontmatter(text: str):
    """Return (meta dict, line index after closing ---) or (None, 0)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, 0
    meta = {}
    for i in range(1, min(len(lines), 80)):
        if lines[i].strip() == "---":
            return meta, i + 1
        line = lines[i]
        if ":" in line and not line.startswith(" ") and not line.strip().startswith("-"):
            key, _, val = line.partition(":")
            val = val.strip().strip("'\"")
            if val and not val.startswith("["):
                meta[key.strip()] = val
    return None, 0


def check_index_current(root: Path):
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "build_canon_index.py"), "--check"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise AssertionError("INDEX.md is stale - regenerate with scripts/build_canon_index.py")
    return "index deterministic and current"


def check_frontmatter(root: Path):
    errors, ids = [], {}
    validated = 0
    for p in knowledge_files(root):
        rel = p.relative_to(root).as_posix()
        if rel.startswith("School/"):
            continue  # School adopts the standard under its own protocol
        meta, _ = parse_frontmatter(p.read_text(encoding="utf-8-sig", errors="replace"))
        if not meta or ("id" not in meta and "layer" not in meta):
            continue  # unmigrated or non-canon frontmatter (e.g. skills)
        validated += 1
        for field in ("id", "layer", "status", "owner"):
            if field not in meta:
                errors.append(f"{rel}: missing {field}")
        if meta.get("layer") and meta["layer"] not in LAYERS:
            errors.append(f"{rel}: bad layer {meta['layer']}")
        if meta.get("status") and meta["status"] not in STATUSES:
            errors.append(f"{rel}: bad status {meta['status']}")
        if meta.get("owner") and meta["owner"] not in OWNERS:
            errors.append(f"{rel}: bad owner {meta['owner']}")
        if meta.get("type") and meta["type"] not in TYPES:
            errors.append(f"{rel}: bad type {meta['type']}")
        fid = meta.get("id")
        if fid:
            if fid in ids:
                errors.append(f"duplicate id {fid}: {rel} and {ids[fid]}")
            ids[fid] = rel
    if errors:
        raise AssertionError("; ".join(errors[:8]))
    return f"{validated} canon frontmatter blocks valid, ids unique"


def check_supersession_banners(root: Path):
    errors = []
    for p in knowledge_files(root):
        rel = p.relative_to(root).as_posix()
        if rel.startswith("School/"):
            continue
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        meta, body_start = parse_frontmatter(text)
        if not meta or meta.get("status") not in {"superseded", "archived"}:
            continue
        if "superseded_by" not in meta:
            errors.append(f"{rel}: status {meta['status']} without superseded_by")
        window = [l for l in text.splitlines()[body_start:] if l.strip()][:10]
        blob = " ".join(window).casefold()
        if "supersed" not in blob and "archiv" not in blob and "historical" not in blob:
            errors.append(f"{rel}: no visible supersession banner in first 10 body lines")
    if errors:
        raise AssertionError("; ".join(errors[:8]))
    return "superseded/archived docs carry superseded_by + visible banner"


def check_links(root: Path):
    broken = []
    for p in knowledge_files(root):
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in LINK_RE.finditer(text):
            target = m.group(1)
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            bare = target.split("#")[0]
            if not bare or not bare.endswith(LINK_EXTS):
                continue
            resolved = (root / bare.lstrip("/")) if bare.startswith("/") else (p.parent / bare)
            try:
                ok = resolved.resolve().exists()
            except OSError:
                ok = False
            if not ok:
                broken.append(f"{p.relative_to(root).as_posix()} -> {target}")
    if broken:
        raise AssertionError("; ".join(broken[:8]))
    return "all relative links resolve"


def check_adr_consistency(root: Path):
    adr = root / "docs" / "adr"
    files = {int(f.name[:4]) for f in adr.glob("[0-9][0-9][0-9][0-9]-*.md")}
    rows = {int(n) for n in re.findall(r"^\| \[(\d{4})\]", (adr / "README.md").read_text(encoding="utf-8"), re.M)}
    problems = []
    if files - rows:
        problems.append(f"files missing from log: {sorted(files - rows)}")
    if rows - files:
        problems.append(f"log rows without files: {sorted(rows - files)}")
    if problems:
        raise AssertionError("; ".join(problems))
    return f"ADR files and log agree ({len(files)} decisions)"


def check_read_order(root: Path):
    text = (root / "docs" / "canon" / "README.md").read_text(encoding="utf-8")
    _, body_start = parse_frontmatter(text)
    text = "\n".join(text.splitlines()[body_start:])
    order = ["CONSTITUTION.md", "INDEX.md", "PROJECT_BRIEF.md"]
    positions = [text.find(name) for name in order]
    if -1 in positions or positions != sorted(positions):
        raise AssertionError("canon README read-order contract broken")
    return "onboarding read-order contract intact"


CHECKS = (
    ("index current", check_index_current),
    ("frontmatter schema", check_frontmatter),
    ("supersession banners", check_supersession_banners),
    ("relative links", check_links),
    ("ADR consistency", check_adr_consistency),
    ("read-order contract", check_read_order),
)


def main() -> int:
    ok, checks = True, []
    for name, fn in CHECKS:
        try:
            detail = fn(ROOT)
            checks.append({"check": name, "ok": True, "detail": detail})
        except Exception as exc:
            ok = False
            checks.append({"check": name, "ok": False, "error": str(exc)})
    print(json.dumps({"ok": ok, "checks": checks}, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
