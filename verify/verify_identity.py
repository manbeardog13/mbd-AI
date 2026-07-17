#!/usr/bin/env python3
"""Identity Review engine (ADR-0024): one command, the whole health picture.

Runs every deterministic verifier, gathers coverage counts and live inbox
stats, and emits the Identity Review metrics table (markdown) plus JSON.
Judgment scores stay human; this supplies the mechanical half."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
VERIFIERS = ("verify_canon", "verify_nero_voice", "verify_nero_inbox",
             "verify_nero_claude_presence", "verify_nero_learning_hybrid",
             "verify_nero_global_presence")


def run_verifier(name: str) -> bool:
    r = subprocess.run([sys.executable, str(ROOT / "verify" / f"{name}.py")],
                       capture_output=True, text=True, timeout=300)
    return r.returncode == 0


def main() -> int:
    write = "--write" in sys.argv
    results = {name: run_verifier(name) for name in VERIFIERS}
    index_head = (ROOT / "docs/canon/INDEX.md").read_text(encoding="utf-8").splitlines()[4]
    m = re.search(r"(\d+) knowledge files - (\d+) carrying", index_head)
    files, migrated = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    goldens = len(re.findall(r"^## probe: ", (ROOT / "docs/persona/voice-goldens.md")
                             .read_text(encoding="utf-8"), re.M))
    adrs = len(list((ROOT / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md")))
    inbox = {"pending": 0, "blocking": 0, "auto": 0}
    state_path = ROOT / "data/review-inbox.json"
    if state_path.exists():
        st = json.loads(state_path.read_text(encoding="utf-8"))
        entries = st.get("entries", [])
        inbox["pending"] = sum(1 for e in entries if e.get("status") == "pending")
        inbox["blocking"] = sum(1 for e in entries
                                if e.get("status") == "pending" and e.get("blocking"))
        inbox["auto"] = sum(1 for e in entries
                            if e.get("status") == "approved" and e.get("level", 9) < 2)
    metrics = {
        "date": date.today().isoformat(),
        "verifiers": results,
        "verifiers_green": f"{sum(results.values())}/{len(results)}",
        "knowledge_files": files, "frontmatter_migrated": migrated,
        "voice_goldens": goldens, "adr_count": adrs,
        "inbox": inbox,
    }
    rows = [
        ("Verifiers green", metrics["verifiers_green"],
         ", ".join(k for k, v in results.items() if not v) or "all systems verify"),
        ("Knowledge files / migrated", f"{files} / {migrated}", "index header"),
        ("Voice goldens", str(goldens), "reference corpus size"),
        ("Decisions (ADRs)", str(adrs), "docs/adr"),
        ("Inbox pending / blocking", f"{inbox['pending']} / {inbox['blocking']}",
         "operator attention surface"),
        ("Self-approvals on record", str(inbox["auto"]),
         "earned autonomy (policy-gated)"),
    ]
    lines = [f"## Mechanical metrics — {metrics['date']}", "",
             "| Metric | Value | Note |", "|---|---|---|"]
    lines += [f"| {a} | {b} | {c} |" for a, b, c in rows]
    print("\n".join(lines))
    print()
    print(json.dumps(metrics, indent=2))
    if write:
        out = ROOT / "docs/persona/identity-reviews" / f"metrics-{metrics['date']}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        print(f"\nwritten: {out}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
