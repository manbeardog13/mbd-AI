---
id: host.capsule-v3-proposal
title: Capsule V3 Proposal - deliberate evolution after reconciliation
layer: operational
type: plan
status: proposed
owner: shared
version: 1.1.0
created: 2026-07-17
updated: 2026-07-17
sources:
  - docs/host/NERO_CLAUDE_GLOBAL_CAPSULE.md
  - docs/host/NERO_COWORK_PROJECT_CAPSULE.md
  - docs/specs/memory-architecture.spec.md
related:
  - docs/adr/0021-review-inbox.md
---

# Capsule V3 Proposal — deliberate evolution after reconciliation

V2 reconciliation is complete (repo = deployed reality, verifiers green).
This proposal is the **evolution** half of the standing rule: two intentional
changes, each with exact replacement text, awaiting Toni's decision. Nothing
here is deployed; adopting any item bumps the affected block to **V3**, repo
source first, then deployment, then verifier confirmation.

## Item 1 — Teach-exception sentence (Claude capsule)

**Problem:** the deployed V2 Claude capsule asserts `data/memory.db`
exclusivity, while the documented, Toni-authorized `claude_teach_nero.py`
batch path writes `source='claude-teaching'` rows (memory-architecture.spec,
Open item 2). Reality and text disagree by one sentence.

**Proposed addition** (to the Claude capsule's memory boundary section):

> Batch teaching via `scripts/claude_teach_nero.py` — run only on Toni's
> explicit request, idempotent, embeddings left null, mirrored in
> `docs/host/NERO_TAUGHT_KNOWLEDGE.md` — is the sole exception to memory.db
> exclusivity. It is a maintenance act, never a runtime path.

**Effect:** closes memory-architecture.spec Open item 2; Codex's isolated
"high-confidence conflict" resolves textually.

## Item 2 — ARCHITECT_MEMORY reference (Cowork project capsule)

**Problem:** the deployed `NERO_GLOBAL_CAPSULE_V2` block references
`docs/ARCHITECT_MEMORY.md`, which does not exist in the repository.

**Option A — remove the reference (recommended).** The role that document
implies (durable architect-level facts, loaded cold) is now filled by the
canon itself (`docs/canon/README.md` read order + INDEX). Replacement text:

> Static capsules and repository files such as `docs/NERO_CODEX_MEMORY.md`
> and the canon under `docs/canon/` are cold documentation. [...]

**Option B — create the document.** A slim architect-memory file (deltas
only, like the slimmed CODEX_MEMORY target) whose job the canon does not
already do. Requires defining that job first; none has been identified.

**Recommendation:** Option A. Reference removal is one line; creating a
document without a distinct job violates the audit's own duplication
findings.

## Item 3 — Voice Bible pointer (both capsules)

**Problem:** the capsules carry six voice adjectives; the operational voice
law now lives in `docs/persona/NERO_VOICE_BIBLE.md` (ADR-0022) with tests.
Engines should be pointed at the law, not left to improvise from adjectives.

**Proposed addition** (one line, identity sections of both capsule blocks):

> Voice and presentation follow `docs/persona/NERO_VOICE_BIBLE.md` (the
> operational voice law, test-gated); these adjectives remain the anchor.

**Effect:** style evolves in canon without identity-version events; new
engines onboard the voice from one pointer.

## Adoption checklist (when Toni decides)

1. Update the repo canonical source block(s) to V3 markers with the chosen
   text (this file's exact wording).
2. Deploy: user-global CLAUDE.md block and/or Cowork project instructions.
3. Run `verify_nero_claude_presence.py` and `verify_nero_learning_hybrid.py`
   (both derive marker versions dynamically — no code change needed).
4. Record adoption in this file (status → active) and the capsule changelogs.

## Changelog

- 1.1.0 (2026-07-17) — Item 3 added: Voice Bible pointer (ADR-0022).
- 1.0.0 (2026-07-17) — Initial proposal (Fable, Claude lane; L2 inbox item).
