---
id: canon.architecture-review-2026-07-16
title: Architecture Review — 2026-07-16
layer: operational
type: report
status: active
owner: shared
created: 2026-07-16
updated: 2026-07-16
sources:
  - docs/CONSTITUTION.md
  - docs/adr/ (0001–0016)
  - docs/PROJECT_BRIEF.md
  - on-disk component survey (app/ presence/ voice/ familiar/ continuity/ School/ skills/ verify/)
related:
  - docs/canon/AUDIT_REPORT.md
  - docs/specs/memory-architecture.spec.md
---

# Architecture Review — 2026-07-16

Phase 4: map responsibilities and interfaces, challenge assumptions, recommend
simplifications. Reviewer: Claude lane (Fable). Verdict up front: **the
architecture is fundamentally sound** — local-first modular monolith, evidence
gates, fail-closed boundaries, zero-start presence. The problems found are
almost all *documentation topology* problems (drift, duplication, undeclared
hierarchy), not design flaws. The two exceptions are flagged below (§ risks).

## Component map

| Component | Responsibility | Key interfaces | Governing sources |
|---|---|---|---|
| **Standalone app** (`app/`) | The product: FastAPI runtime, chat, typed memory, world model, agent loop, Capability Registry, security gate, Executive Memory, TTS | HTTP: `/api/agent`, `/api/agent/capabilities`, `/api/executive`, `/api/world`, `/api/speak`, `/api/metrics`; SQLite stores | Constitution; ADR-0001/2/3/5/6/7/8; PROJECT_BRIEF |
| **Host presence** (capsules, `CLAUDE.md`, `AGENTS.md`, `.codex/`, `.claude/`) | Nero's identity on hosted Claude/Codex, zero-start, hosted-only boundary | Static context blocks; deployment contracts; `verify_nero_global_presence.py` | ADR-0014; capsule docs |
| **Continuity ledger** (`continuity/`, `data/continuity/`) | Deliberate cross-host memory transport with receipts | `continuityctl.py` CLI (stdin payloads, JSON out, stable exit codes); Claude-lane skill | ADR-0016; privacy doc |
| **School** (`School/`) | Evidence-gated training; dual-host agreement/audit; XP | `schoolctl.py` (log/ack/audit/finalize); task packs; `experience.json` | SCHOOL_RULES; SHARED_WORK_RULES; ADR-0015 |
| **Skills** (`skills/`, `.claude/skills/`) | Reusable validated capabilities for hosted lanes | SKILL.md contracts; verify scripts | ADR-0015; skill-lifecycle.spec (new) |
| **Presence layer** (`presence/`, `familiar/`, `voice/`) | Visual/voice embodiment: Presence Director, Live2D bridge protocol, voice profiles/effects, desktop familiar (C# exe) | `live2d_protocol.md` WebSocket v1; JSON schemas in `presence/contracts/`; `voice/blends/nero_prime_v1.npy` | ADR-0009/10/11; mobile/presence docs |
| **Visual pipeline** (`docs/visual/`, external `D:\ComfyUI`) | Manbeardog character production (Stage 1 live on the RTX 4070) | ComfyUI HTTP (submit + poll `/history`); asset contract; QC checklists | Visual Bible + visual docs; NERO_HANDOFF (historical) |
| **Verification spine** (`verify/`, `tests/`) | Proof on the real PC; per-subsystem `verify_*.py` + `verify_everything.py` | Exit codes 0/2/fail; CI-runnable offline subset | DIRECTIVE (verification philosophy); Constitution §3 |
| **External council** (`app/collaboration.py`, ADR-0012) | Human-triggered OpenAI+Claude API handoff (three requests per press) | User's own API keys; visible brief→build→review chain | ADR-0012; CHATGPT_CLAUDE_COUNCIL.md |
| **Ruflo integration** (project instructions; `INTEGRATIONS.md` catalog) | MCP/plugin discovery and routing for hosted lanes | `integrations.list`, `skills.search/read`, `mcp.catalog` | ADR-0013; INTEGRATIONS.md |

Off-repo but in-narrative: **NERO_Forge** (`D:\NERO_Forge\_cowork\` — council
quest prototype, Oathfire planning) and **Proxima** (`C:\Users\tonij\Proxima\`
launcher) — see PROXIMA_DEPENDENCY_REPORT.md.

## Assumptions challenged

1. **"The capsule contract keeps identity consistent."** It did not — the
   Claude lane deployed V2 while the repo canon says V1, and the two versions
   disagree on something as fundamental as whether Nero answers alone or
   beside Claude. *The assumption that a stated byte-identity contract
   self-enforces is false without a verifier on every lane.* → Phase C fix +
   Claude-lane verify script.
2. **"Docs describe one system."** There are actually **three Neros** on this
   machine: the standalone local app (asleep), hosted Host-Mode Nero (active),
   and the Forge/Council experiment (status unknown). Only the first two are
   documented in-repo. A fresh model cannot currently learn from the repo that
   the third exists, or that it's deprecated. → Proxima report + off-repo
   marking rule (KNOWLEDGE_STANDARD §4).
3. **"More governing documents = more governance."** DIRECTIVE, VISION, and
   the Constitution all speak with authority; two of the three are formally
   superseded but don't say so loudly. Governance improved when the
   Constitution was written; discoverability didn't. → banners + hierarchy
   chain.
4. **"Phase numbers are stable identifiers."** Two numbering eras collide;
   "Phase 1" and "Phase 2" each mean two different things in live documents.
   → name phases ("The Hands"), keep numbers only as history.
5. **"School templating scales."** 42 md5-identical files already; every new
   department multiplies template copies. Fine at 14 departments, creaky at 30.
   → generator proposal, School-governed, low urgency.
6. **"The repo is the knowledge base."** Mostly true and worth defending —
   but `NERO BOSS.txt` and handoffs in the iCloud folder carry real
   operational truth (e.g. Proxima's existence, ESET attestations) that the
   repo lacks. → either import the durable parts or mark them external
   sources in the index; never let load-bearing facts live only in a chat dump.
7. **"Maximum-access mode and the security gate coexist."** They do — but
   INTEGRATIONS.md's "maximum-access" framing reads as if it competes with the
   gate. It doesn't (read-only frictionless, consequential confirmed), but the
   wording invites a future contributor to widen it. → one clarifying sentence
   in INTEGRATIONS.md (Phase B).
8. **"Binary artifacts belong in the repo."** `familiar/bin/NeroFamiliar.exe`,
   `.npy` voice blends, a `.docx` brief. Small today; the pattern doesn't
   scale and an exe in-tree is an audit liability. → policy line in
   CANONICAL_STRUCTURE (§rules 6–7); rebuild-from-source note for the familiar.

## Risks (the two real ones)

- **R1 — Identity drift across lanes (active, happening now).** The V1/V2
  capsule divergence is not cosmetic: single- vs dual-voice is Nero's observable
  personality. Until Phase C lands, the two lanes are running materially
  different Neros. Highest-priority reconciliation.
- **R2 — Dirty-worktree half-life.** 176 modified/untracked entries on a
  rescue branch, with a stale `.git/index.lock`. Every day this persists, the
  gap between "on disk" and "committed canon" grows, and every doc statement
  about the repo is quietly ambiguous (which version is true?). Resolve the
  rescue branch before any structural migration (MIGRATION_PLAN precondition).

## Simplifications recommended

1. **Kill duplication with jobs, not merges.** PROGRESS/BRIEF/ROADMAP each get
   a one-line charter at the top; overlapping sections deleted (VISION's
   roadmap table → historical banner). Fewer words, same documents.
2. **Slim `NERO_CODEX_MEMORY.md` to deltas** — facts *not* already in the
   capsule. Duplication is drift fuel.
3. **Archive completed reviews** (voice set) once ADRs carry their decisions —
   `docs/` root stops being a museum.
4. **One entry point.** README → `docs/canon/README.md` → INDEX. A fresh model
   should never need directory archaeology (this review is the last one that
   should ever require it).
5. **Retire Proxima formally** (ADR-0019) rather than letting it fade —
   undocumented deprecation is how it got lost in the first place.
6. **Make the index a mechanism.** `scripts/build_canon_index.py` regenerates
   INDEX.md; a future `verify_canon.py` fails on drift. Vigilance jobs become
   scripts, per the Principle of Least Intelligence.

## What must not be simplified

The security gate's position (built before tools, every dispatch through it);
the three-cap discipline in School; fail-closed semantics everywhere; the
zero-start boundary; append-only ledgers; the verify/ spine; lane ownership.
These are load-bearing. Any "simplification" that touches them is a
Constitution amendment, not a cleanup.

## Changelog

- 2026-07-16 — Initial review (Fable, Claude lane).
