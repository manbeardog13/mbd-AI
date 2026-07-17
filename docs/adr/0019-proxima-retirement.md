# ADR-0019: Proxima retirement

**Status:** Accepted (Toni, 2026-07-17 — retirement executed: processes stopped, no autostart entry existed; folder disposition of C:\Users\tonij\Proxima remains Toni's — archive or delete; reversible until then)
**Date:** 2026-07-16

## Context

Proxima is an Electron launcher/status app at `C:\Users\tonij\Proxima\` from
the NERO_Forge Council workshop era. The 2026-07-16 dependency audit
(`docs/canon/PROXIMA_DEPENDENCY_REPORT.md`) found: **zero references anywhere
in this repository**; documented unreliability (it marked Claude "up" without
a confirmed response and attempted a fictional `chatgpt` model handshake —
NERO_ChatGPT_Handoff §3); and full functional supersession by canon mechanisms
(ADR-0012 External Council, ADR-0015 DHEF/School collaboration, ADR-0016
continuity ledger). As a resident status process it also contradicts the
zero-start presence principle (ADR-0014) and the truth rule that no contact is
claimed unless it happened. It survives only as undocumented habit — the exact
kind of ghost dependency the canonical knowledge base exists to eliminate.

## Decision

Retire Proxima from Nero's active stack:

1. It is not launched as part of any Nero workflow; any startup entry is
   removed. The folder may be archived or deleted — Toni's choice; it lives
   outside this repo either way.
2. No resident replacement. A future Forge status view, if ever wanted, uses
   the cold run-read-exit pattern (`operations_console.py` precedent).
3. This ADR is the canonical record that Proxima existed, what it did, and why
   it is gone; the dependency report holds the evidence.
4. Any Proxima revival or update is a new decision and, per the standing
   security rule, a new artifact check before use.

## Consequences

- One less resident process; one less source of fabricated status claims; the
  zero-start boundary holds everywhere.
- The Forge-era mailbox/queue history remains readable at
  `D:\NERO_Forge\_cowork\` (off-repo, unverified from here) without a UI.
- If some untracked personal workflow still relies on Proxima's window, Toni
  discovers it during Phase E verification (5-minute checklist in the report)
  before deletion — retirement is reversible until the folder is removed.

## Alternatives considered

- **Retain as-is:** rejected — undocumented, unreliable by its own record,
  redundant, and boundary-violating.
- **Repair and adopt into canon:** rejected — every capability it theatrically
  promised now exists honestly (ADR-0012/0015/0016); adopting a dev-mode
  Electron app buys UI, not capability, at resident-process cost.
- **Silent deletion without an ADR:** rejected — undocumented deprecation is
  how it became a ghost in the first place.
