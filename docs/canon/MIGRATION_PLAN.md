---
id: canon.migration-plan
title: Canonical Structure Migration Plan
layer: operational
type: plan
status: active
owner: shared
version: 1.1.0
created: 2026-07-16
updated: 2026-07-16
sources:
  - docs/canon/AUDIT_REPORT.md
  - docs/canon/CANONICAL_STRUCTURE.md
related:
  - docs/adr/0017-canonical-knowledge-base.md
---

# Canonical Structure Migration Plan

The executable path from today's layout to CANONICAL_STRUCTURE.md. Phased so
every step is small, reference-safe, and reversible with `git revert`.

**Why moves were not executed on 2026-07-16:** the worktree sits on rescue
branch `claude/rescue-dirty-worktree-20260715` with ~176 modified/untracked
entries and a stale `.git/index.lock`. Toni approved "plan + execute," and the
additive layer (Phase 0) *was* executed — but moving or editing files mid-rescue
risks entangling the rescue itself (several planned edit targets — ROADMAP,
MODELS, adr/README, README — are among the modified files). Protecting the
rescue outranks finishing the migration in one session.

## Preconditions (before Phase A)

- [ ] Rescue branch resolved: current worktree state committed/merged as Toni
      intends. **Nothing below runs on a dirty tree.**
- [ ] Stale `.git/index.lock` removed once no git process is running
      (`del "D:\mbd AI\.git\index.lock"` — Toni or a session with git access).
- [ ] This plan re-checked against the merged state (paths may have changed).

Standing rules for every phase: one phase per commit; move + inbound-link
fixes in the same commit (`grep -rl "<name>"` before and after must match
intent); regenerate `docs/canon/INDEX.md` in the same commit; no commit/push
without Toni's explicit approval; rollback = `git revert` of that commit.

## Phase 0 — Additive canon layer ✅ **executed 2026-07-16**

New files only; nothing existing touched:
`docs/canon/` (README, INDEX, KNOWLEDGE_STANDARD, CANONICAL_STRUCTURE,
AUDIT_REPORT, ARCHITECTURE_REVIEW, PROXIMA_DEPENDENCY_REPORT, this plan),
`docs/specs/` (memory-architecture, skill-lifecycle),
ADRs 0017–0019 (Proposed), `scripts/build_canon_index.py`.

## Phase A — Truth banners & index hygiene (safe edits, ≤1 h)

| Step | Action | Inbound refs to fix |
|---|---|---|
| A1 | `docs/adr/README.md`: add 0013 + 0016 to the log; add 0017–0019 as Proposed; resolve ADR-0009 status (Accepted or note why still Proposed) | — |
| A2 | `docs/DIRECTIVE.md`: supersession banner ("Philosophy superseded by CONSTITUTION.md v1.1 — retained as history; the Constitution's pillar order governs") + frontmatter | — |
| A3 | `docs/VISION.md`: banner on the roadmap table ("historical — ROADMAP.md governs") + frontmatter | — |
| A4 | `README.md`: add "Start here → docs/canon/README.md" section | — |
| A5 | One-line charters atop PROGRESS.md / PROJECT_BRIEF.md / ROADMAP.md; adopt phase *names* with a legacy-numbering note | — |
| A6 | `docs/host/INTEGRATIONS.md`: one sentence — maximum-access = discovery breadth, never a gate bypass | — |

## Phase B — Structural moves (reference-checked, ~2 h)

> **EXECUTED 2026-07-17** (B1–B8; B9 stays by design until "The Hands"
> completes): 19 files moved (archive/handoffs, archive/reviews-voice,
> guides/, host/, visual roadmap merge), 24 files repointed + 18 relative
> links auto-repaired, visual + familiar READMEs added, skill lifecycle
> frontmatter applied and re-synced to both deployed skill homes, Cowork
> project capsule canonical source captured. B5 executed for Claude/shared
> docs only — the five Codex-lane host docs (GLOBAL_CAPSULE, CODEX_MEMORY,
> CODEX_RUNTIME, HOST_VOICE, PRESENCE_ACCEPTANCE) stay in docs/ pending a
> joint change. All verifiers green after execution.

| Step | Move | Inbound refs found (fix in same commit) |
|---|---|---|
| B1 | `NERO_HANDOFF.md` → `docs/archive/handoffs/2026-07-13-manbeardog-pipeline.md` (+ tombstone frontmatter) | **none** |
| B2 | `docs/visual/manbeardog_visual_production.md` → `docs/visual/`; delete empty `docs/roadmap/` | 6 (mobile/presence_experience, 4× visual docs, archived handoff) |
| B3 | `docs/reviews/{mms-tts-evaluation, stage1-voice-baseline, stage2-voice-capability-audit, voice-provider-analysis, voice-strategy-recommendation}.md` → `docs/archive/reviews-voice/` (ADR acceptance reviews stay with ADRs) | check each (expected ≈0; decisions live in ADR-0009/10/11) |
| B4 | `docs/{SETUP, ALWAYS_ON, REMOTE_ACCESS, VOICE_AND_SIRI, MODELS}.md` → `docs/guides/` | SETUP↔REMOTE_ACCESS↔ALWAYS_ON cross-links; **MODELS: 7 refs incl. `bootstrap.py`, `config.yaml`, `config.example.yaml`, `verify_nero_global_presence.py`** — code refs are strings in messages; update carefully, run the verify script after |
| B5 | Host-mode docs → `docs/host/` (GLOBAL_CAPSULE, CLAUDE_GLOBAL_CAPSULE, CODEX_MEMORY, CODEX_RUNTIME, HOST_VOICE, TAUGHT_KNOWLEDGE, INTEGRATIONS, CHATGPT_CLAUDE_COUNCIL, CODEX_CONTINUITY_HANDOFF, NERO_GLOBAL_PRESENCE_ACCEPTANCE) | `verify_nero_global_presence.py` reads capsule path — **update script + rerun**; AGENTS.md + CLAUDE.md references; **coordinate: several are Codex-lane-owned — this step is a joint change, or Claude moves only Claude/shared files** |
| B6 | `docs/visual/README.md` (new): declare Bible=law hierarchy; `familiar/README.md` (new): what/why/build-from-source | — |
| B7 | Add lifecycle frontmatter to the four SKILL.md files (per skill-lifecycle.spec) | — |
| B8 | Add frontmatter to remaining docs/ files opportunistically; INDEX flags `unmigrated` until done | — |
| B9 | `docs/DESIGN-phase1.md` + companions: **keep in place** while "The Hands" is in flight; move to `docs/archive/design/` only after the phase completes | DESIGN-phase1 has 5 inbound refs incl. `app/capabilities/builtin/__init__.py` |

## Phase C — Capsule reconciliation (identity-critical; Toni + both lanes)

> **EXECUTED 2026-07-17** (items 1 and 3, plus the hybrid-verifier marker
> de-pin): repo capsule source = deployed V2 verbatim; deployed artifacts
> untouched; both verifiers green. Remaining: item 2 (teach-exception wording)
> deferred as a V3 proposal per reconciliation-before-evolution; item 4
> (CODEX_MEMORY slimming) is Codex-lane; item 5 (proposed routing block)
> awaits Toni. The Cowork project 'NERO' instructions carry a separate
> NERO_GLOBAL_CAPSULE_V2 surface whose canonical capture is tracked in the
> migration report.

1. **Decide the governing text:** deployed V2 (observed in the live Claude
   project context) vs repo V1. Recommendation: V2 semantics are current
   reality — bring V2 *into* `docs/host/NERO_CLAUDE_GLOBAL_CAPSULE.md` /
   `NERO_GLOBAL_CAPSULE.md` as the new marked blocks, superseding V1 blocks
   with banners. Resolve the **single- vs dual-voice** contradiction
   explicitly — this is Nero's observable personality; Toni chooses.
   **DECIDED (Toni, 2026-07-16): single voice.** Nero answers alone; the
   dual-voice text in `NERO_CLAUDE_GLOBAL_CAPSULE.md` V1 is superseded and
   both capsule sources adopt single-voice V2 semantics in this phase.
2. Add the memory.db exclusivity + teach-script exception sentence
   (memory-architecture.spec Open item 2).
3. **New:** `verify/verify_nero_claude_presence.py` — byte-identity check for
   the deployed Claude capsule, parallel to the Codex one. The lane without a
   verifier is the lane that drifted.
4. Slim `docs/NERO_CODEX_MEMORY.md` to deltas-not-restatement (Codex lane
   executes its own edit).
5. `audit/nero-continuity/proposed-global-claude-block.md`: Toni approves →
   deploy + move to `docs/host/`; or rejects → archive.

## Phase D — School-governed proposals (shared-work protocol required)

Template generator for the 42 duplicated pack files; `.docx` brief → markdown;
School frontmatter adoption. Each needs the two-host agreement flow — proposal
lives here, execution goes through `schoolctl.py` logging.

## Phase E — Proxima retirement (outside-repo; Toni executes)

> **EXECUTED 2026-07-17:** four running Proxima electron processes stopped
> (Toni authorized); no autostart entry existed; ADR-0019 → Accepted. Folder
> disposition (archive or delete C:\Users\tonij\Proxima, 834 MB) remains
> Toni's.

Per PROXIMA_DEPENDENCY_REPORT: verify not running / no startup entry; archive
or delete `C:\Users\tonij\Proxima\`; ADR-0019 → Accepted once done.

## Current → target map (files not otherwise listed)

Unmoved and staying: Constitution, ADRs, PROGRESS, PROJECT_BRIEF, ROADMAP,
VISION, DIRECTIVE (banners only), continuity/, skills/, School/, audit/,
verify/, all code dirs, docs/mobile/, docs/visual/ (gains one file + README),
CLAUDE.md, AGENTS.md, .claude/, .codex/. Runtime dirs (data/, models/,
output/, _nero_preview/) remain gitignored artifacts.

## Verification (each phase)

`python scripts/build_canon_index.py && git diff --stat` — index regenerates
clean; link check: `grep -rn "](docs/roadmap/" --include="*.md" .` returns
nothing after B2, and equivalents per step; `verify_nero_global_presence.py`
green after B4/B5; full `verify_everything.py` offline subset green after
Phase B completes.

## Changelog

- 1.1.0 (2026-07-16) — Phase C amended: single-voice decision recorded (Toni).
- 1.0.0 (2026-07-16) — Initial plan; Phase 0 executed same day.
