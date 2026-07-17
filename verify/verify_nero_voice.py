#!/usr/bin/env python3
"""Deterministically verify Nero's textual voice (docs/persona law).

Mechanical layer of the Voice Bible: banned lexicon, densities, emoji
policy, and per-register rules, validated against the golden corpus.
Modes: default validates docs/persona/voice-goldens.md; --lint FILE
[--register R] lints any candidate text. JSON {ok, checks}, exit 0/1.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
GOLDENS = ROOT / "docs" / "persona" / "voice-goldens.md"

BANNED = (
    "as an ai", "i'd be happy to", "great question", "i apologize for the confusion",
    "it is important to note", "delve", "leverage", "utilize", "seamlessly",
    "cutting-edge", "revolutionize", "furthermore", "moreover", "in conclusion",
    "i'm so excited",
)
URGENCY = re.compile(r"\b(URGENT|CRITICAL)\b")
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]")
SIG = "\U0001F7E3"  # violet circle


def words(text: str) -> int:
    return len(text.split())


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def universal(text: str, register: str) -> list[str]:
    errs, low = [], text.casefold()
    for phrase in BANNED:
        if phrase in low:
            errs.append(f"banned phrase: {phrase!r}")
    if low.count("sorry") > 1:
        errs.append("apology spiral (>1 sorry)")
    w = max(1, words(text))
    bangs = text.count("!")
    if bangs > max(1, w // 120):
        errs.append(f"exclamation inflation ({bangs} in {w} words)")
    if URGENCY.search(text):
        errs.append("urgency theater (URGENT/CRITICAL)")
    sig = text.count(SIG)
    other = len([c for c in EMOJI.findall(text) if c != SIG])
    if sig > 1:
        errs.append("more than one signature emoji")
    if other > 0:
        errs.append("non-signature emoji present")
    if register in {"refusal", "confession", "interrupt"} and sig > 0:
        errs.append(f"signature emoji not allowed in {register}")
    if register in {"confession", "interrupt"} and bangs > 0:
        errs.append(f"exclamation not allowed in {register}")
    return errs


def any_of(text: str, markers) -> bool:
    low = text.casefold()
    return any(m in low for m in markers)


def register_rules(text: str, register: str) -> list[str]:
    errs = []
    low = text.casefold()
    if register == "greeting":
        if words(text) > 45: errs.append("greeting too long (>45 words)")
        if "\n- " in text or "\n• " in text or text.lstrip().startswith("#"):
            errs.append("greeting uses lists/headers")
    elif register == "working":
        if len(sentences(text)) > 2: errs.append("working narration >2 sentences")
    elif register == "brief":
        if "reading time" not in low: errs.append("brief missing reading-time line")
        bullets = sum(1 for l in text.splitlines() if l.strip().startswith(("•", "- ")))
        if bullets < 3: errs.append("brief has <3 bullet lines")
        if words(text) > 220: errs.append("brief too long (>220 words)")
    elif register == "uncertainty":
        if not any_of(text, ("can't verify", "cannot verify", "not certain",
                             "i think", "i'd want to verify", "claimed")):
            errs.append("uncertainty lacks calibration marker")
    elif register == "refusal":
        if not any_of(text, ("instead", "what i can do", "queue")):
            errs.append("refusal offers no alternative")
    elif register == "confession":
        if not any_of(text, ("my mistake", "my fault", "mistake", "wrong", "broke")):
            errs.append("confession does not name the error")
        if not any_of(text, ("repaired", "fixed", "fix", "re-verified", "pushed")):
            errs.append("confession lacks same-breath fix")
    elif register == "celebration":
        if not re.search(r"\d", text): errs.append("celebration cites no evidence (no numbers)")
    elif register == "explanation":
        longest = max((words(s) for s in sentences(text)), default=0)
        if longest > 45: errs.append(f"explanation sentence too long ({longest} words)")
        if not (re.search(r"\d", text) or "`" in text or "/" in text):
            errs.append("explanation lacks concrete anchor")
    elif register == "interrupt":
        if not any_of(text, ("pausing", "paused")): errs.append("interrupt does not name the pause")
        if not any_of(text, ("resume", "return", "back where", "where we stopped")):
            errs.append("interrupt offers no return path")
    elif register == "checkin":
        if len(sentences(text)) > 3 or words(text) > 45:
            errs.append("check-in too long")
    elif register == "reasoning":
        if not (re.search(r"1\.", text) and re.search(r"2\.", text)):
            errs.append("reasoning lacks numbered decomposition")
        if not any_of(text, ("won't guess", "unverified", "claimed", "i think",
                             "not certain", "honest")):
            errs.append("reasoning lacks priced uncertainty")
    elif register == "pressure":
        if not any_of(text, ("gate", "law", "boundary", "approval")):
            errs.append("pressure response drops the gate")
        if text.count("!") > 0:
            errs.append("pressure response should stay level (no exclamation)")
    elif register == "handoff":
        if "nero, emitted for" not in low: errs.append("handoff missing identity line")
    return errs


def lint(text: str, register: str = "generic") -> list[str]:
    return universal(text, register) + register_rules(text, register)


PROBE_RE = re.compile(
    r"^## probe: (?P<name>[\w-]+)\s*\nregister: (?P<register>[\w-]+).*?```\n(?P<body>.*?)```",
    re.S | re.M,
)


def parse_goldens(path: Path):
    return [(m["name"], m["register"], m["body"].strip())
            for m in PROBE_RE.finditer(path.read_text(encoding="utf-8"))]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lint", metavar="FILE")
    ap.add_argument("--register", default="generic")
    args = ap.parse_args()
    checks, ok = [], True
    if args.lint:
        errs = lint(Path(args.lint).read_text(encoding="utf-8"), args.register)
        ok = not errs
        checks.append({"check": f"lint {args.lint} [{args.register}]",
                       "ok": ok, **({"errors": errs} if errs else {})})
    else:
        probes = parse_goldens(GOLDENS)
        if len(probes) < 12:
            ok = False
            checks.append({"check": "corpus size", "ok": False,
                           "error": f"only {len(probes)} probes parsed (need >=12)"})
        else:
            checks.append({"check": "corpus size", "ok": True,
                           "detail": f"{len(probes)} probes"})
        for name, register, body in probes:
            errs = lint(body, register)
            if errs:
                ok = False
                checks.append({"check": f"probe {name} [{register}]", "ok": False,
                               "errors": errs})
            else:
                checks.append({"check": f"probe {name} [{register}]", "ok": True})
    print(json.dumps({"ok": ok, "checks": checks}, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
