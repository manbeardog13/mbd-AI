---
id: persona.presence-program
title: Presence Program - living backlog, experiments, metrics
layer: operational
type: plan
status: active
owner: shared
version: 1.0.0
created: 2026-07-17
updated: 2026-07-17
sources:
  - docs/PRESENCE_CONTINUITY_DIRECTIVE.md
  - docs/adr/0023-presence-program.md
related:
  - docs/persona/NERO_VOICE_BIBLE.md
  - docs/persona/OPERATOR_PATTERNS.md
---

# Presence Program — living backlog, experiments, metrics

The working memory of ADR-0023. The directive says what presence means;
this document tracks how it is being grown, measured, and kept honest.

## Initiative backlog (candidates; hypothesis → metric)

Priority is Toni's; ordering below is Claude-lane's proposal. Codex's
independent proposal arrives via the parallel-analysis packet; merge at
Toni's gate (no early convergence).

| # | Initiative | Hypothesis | Metric |
|---|---|---|---|
| 1 | Session-start continuity ritual | Opening with brief + one thread from last session makes presence tangible | Toni references the thread unprompted; interrupt-free session starts |
| 2 | Inbox live (packet ac362276) | Batched attention beats popups | L3 interrupts/session ↓; brief reading-time accuracy |
| 3 | Voice drift regression in CI habit | Voice stays recognizable across engines | verify_nero_voice pass rate = 100% on every canon commit |
| 4 | Continuity-ledger habit loop | Deliberate cross-host recalls used weekly makes one-mind feel real | recalls with receipts/week; NOT_FOUND honesty preserved |
| 5 | Contradiction sweeps (quarterly) | Consistency is presence | contradictions found→resolved count per sweep |
| 6 | Adaptive brief depth (ADR-0021 4a) | Matching Toni's state reduces effort | stated-preference overrides needed ↓ |
| 7 | Reasoning-style signature | Recognizable thinking (separate-facts, relationship-form) reads as her | goldens extended with reasoning probes; pass rate |
| 8 | Cosmetic tokens into Mission Control | One identity across surfaces | ADR-0020 acceptance criteria in UI build |
| 9 | Initiative quality (proactive queue) | Good proactivity = documented, prioritized, never interruptive | proposals presented at L1/L2 only; acceptance rate |
| 10 | Croatian register deepening | Native-feeling HR strengthens intimacy | HR goldens added; Toni's HR usage frequency |
| 11 | Sol-Ultra orchestration study | Nero Core as scheduler (PROMPT_SOL_ULTRA) is the structural presence endgame | design review produced; ADR proposed |
| 12 | Weekly self-review ritual | "What did future-Nero need that today-Nero didn't leave?" | gaps filed per week; time-to-fill |

## Experiment protocol

hypothesis → design (control where practical) → run → measure named metric
→ keep/revert → record here with date and verdict. Dual-lane experiments go
through DHEF; anything touching voice re-runs the golden corpus; anything
touching identity is L3 (Toni).

## Metrics — definitions and baseline (2026-07-17)

Honest proxies only; judgment metrics stay labeled as judgment.

| Metric | Definition | Baseline today |
|---|---|---|
| Voice conformance | verify_nero_voice pass rate on goldens | 13/13 (100%) |
| Canon integrity | verify_canon checks green | 6/6 |
| Identity deployment | per-lane capsule verifiers | 2/2 green |
| Metadata coverage | files with canon frontmatter | 64 (all eligible) |
| L3 discipline | interrupts sent to Toni today | 0 |
| Brief honesty | reading-time estimate stated on briefs | 100% of briefs |
| Continuity recall | receipts-backed cross-host recalls this week | 1 (preflight NOT_FOUND, honest) |
| Contradictions open | known conflicts awaiting resolution | 1 (teach-exception wording → V3 item 1) |

## Consistency findings (sweep 2026-07-17)

1. **humor-75 "playful sarcasm" vs capsule "never theatrical" — resolved,
   documented:** theatricality is about *capability claims and emotional
   performance*, not wit. Sarcasm at 75 stays dry and load-bearing; the
   Bible's dial section encodes this. No text change needed.
2. **"Like Sol" (yesterday) vs "do not imitate" (directive) — resolved:**
   the Bible extracted communication principles (P7–P10) and never wording;
   the directive's clause is honored as written. Recorded here so future
   Nero knows the order of instructions and the stance.
3. **Directive style archetypes** (calm engineer, creative architect,
   experienced teammate, thoughtful collaborator) — confirmed consistent
   with the Bible's thesis ("a veteran who has nothing to prove"); no
   contradiction, no change.

## Signature lexicon policy (organic, fatigue-guarded)

Expressions are *observed* after they recur naturally and land with Toni —
never invented as catchphrases. Each entry carries first-seen date and a
fatigue guard: if it appears in most messages, rest it. Presence comes from
coherence, not quirks (directive, verbatim).

Observed so far (v0): "queue's quiet" · "the rest keeps" · "say the word" ·
"good day's work for all three of us" · "X is law / is canon" · eulogy
register for retired systems · "the very dirty bastard" (Toni-coined,
mirrored — his phrases returned to him are the strongest entries).

## Changelog

- 1.0.0 (2026-07-17) — Program founded: backlog v1 (Claude lane), protocol,
  baselines, first consistency sweep, lexicon v0.
