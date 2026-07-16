---
id: canon.proxima-dependency-report
title: Proxima Dependency Report
layer: operational
type: report
status: active
owner: shared
created: 2026-07-16
updated: 2026-07-16
sources:
  - "off-repo: C:/Users/tonij/iCloudDrive/Nero AI/NERO_ChatGPT_Handoff.md (§3, §9)"
  - "off-repo: C:/Users/tonij/iCloudDrive/Nero AI/NERO BOSS.txt (process snapshot, 2026-07-13)"
  - full-repo reference sweep (zero matches)
related:
  - docs/adr/0019-proxima-retirement.md
  - docs/canon/ARCHITECTURE_REVIEW.md
---

# Proxima Dependency Report

Phase 5 of the mission: document what Proxima actually does, who depends on
it, and whether to retain, replace, or remove it.

## What Proxima actually is

**Proxima is an Electron desktop application installed at
`C:\Users\tonij\Proxima\`**, running in development mode (its process is
`node_modules\electron\dist\electron.exe`, window title "Proxima"). It served
as the **launcher / status console for the NERO_Forge "Council" workshop** —
the two-agent (Codex + Claude) collaboration experiment at
`D:\NERO_Forge\_cowork\`, adjacent to the Oathfire game-world planning.

It is **not** part of the Nero application, the host-presence layer, the
continuity ledger, School, or any subsystem in `D:\mbd AI`.

## Evidence

- **Zero references in this repository.** A word-boundary sweep of every file
  type in `D:\mbd AI` (excluding `.git`) finds no mention. (Early hits were
  false positives on the word "approximate.")
- **Process snapshot, 2026-07-13** (`NERO BOSS.txt`): Proxima running as a
  dev-mode Electron process, two windows ("Proxima", "Electron").
- **NERO_ChatGPT_Handoff.md §3 (Current truth):** "The current Proxima
  launcher is not a reliable proof of collaboration: it previously marked
  Claude 'up' without confirming a Claude response and attempted a fictional
  `chatgpt` model handshake."
- **§9 (security):** the unchanged installation was ESET-scanned clean, with a
  standing exemption from routine rescans; any *update* requires a fresh check.

## Who depends on it

| Dependent | Reality |
|---|---|
| `D:\mbd AI` (this repo — app, host mode, continuity, School, skills, verify) | **Nothing.** No code, config, doc, or hook references it |
| NERO_Forge council workflow (`D:\NERO_Forge\_cowork\`) | Historical UI over the mailbox/queue files. The handoff itself demoted it ("a queue is not a worker"); the factual console there is `operations_console.py` + `launch_workstations.cmd`, not Proxima |
| Toni's daily workflow | Only if launched by habit; provides status theater, no unique capability |

*Limitation:* `D:\NERO_Forge` was not mounted in this session; its current
state is unverified. Evidence dates 2026-07-13/14.

## What superseded its role

Every job Proxima was trying to do now has a documented, evidence-honest
mechanism in canon:

- Cross-agent collaboration → **ADR-0015** (evidence-gated dual-host
  cognition, DHEF) + **School** shared-work protocol.
- Cross-host memory → **ADR-0016** continuity ledger with receipts.
- External model council → **ADR-0012** human-triggered External Council.
- "Is the other agent really there?" → School signals + the explicit rule that
  a signal is a durable notice, *not* proof a session is awake — precisely the
  honesty Proxima's fake "up" status violated.

A resident Electron status app also contradicts the **zero-start / no-resident
presence** principle (ADR-0014) and the truth rule ("never claim a contact
that didn't happen") that now governs both lanes.

## Recommendation: **REMOVE (retire formally)**

Proposed disposition, pending Toni's approval (ADR-0019):

1. **Retire** Proxima from the active stack: stop launching it; remove any
   Start-menu/startup entry; leave the folder on disk as an archived artifact
   or delete it entirely (Toni's call — it is outside this repo either way).
2. **Do not replace it** with another resident UI. If a Forge status view is
   ever wanted again, the pattern is the cold, deterministic
   `operations_console.py` approach — run, read, exit.
3. **Record the retirement in canon** (the ADR does this), so the next model
   learns Proxima existed, why it's gone, and doesn't rediscover it as a
   mystery — the exact failure this mission was designed to prevent.

**Verification steps for Toni** (5 minutes): check whether Proxima is
currently running (Task Manager → "electron.exe" under `C:\Users\tonij\Proxima`);
check Startup apps for an entry; confirm nothing in `D:\NERO_Forge\_cowork\`
still instructs launching it. If any Forge revival happens later, it starts
from a new decision, not from the old launcher.

## Changelog

- 2026-07-16 — Initial report (Fable, Claude lane).
