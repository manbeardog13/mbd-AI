---
id: spec.desktop-familiar
title: Nero Void Guardian Desktop Familiar
layer: core
type: spec
status: active
owner: toni
version: 2.0.0
created: 2026-07-17
updated: 2026-07-18
sources:
  - familiar/nero_companion_runtime_v2.json
  - docs/adr/0025-desktop-familiar.md
  - docs/adr/0020-identity-plane-and-engine-handoff.md
  - docs/IDENTITY_EVOLUTION_CHARTER.md
related:
  - presence/README.md
  - familiar/README.md
---

# Nero Void Guardian Desktop Familiar

The Familiar is Nero's opt-in desktop manifestation: an adult female void elf
with high twin magenta ponytails, pointed ears, thick plain black wayfarers,
obsidian-black plate, violet-eyed wolf-head pauldrons, and the heavy two-handed
mace Jeklik's Crusher — Mongoose Thunder. These silhouette locks are immutable
across animation states and output scale.

It is an ambient visual language for hosted system activity, not another
persona, model, speaker, gate, or authority. The machine-readable contract in
`familiar/nero_companion_runtime_v2.json` is normative for state IDs, event
IDs, priorities, timing, palette, interactions, accessibility, and assets.

## Runtime contract

- The 19-state catalog includes arrival, idle, listening, thinking, speaking,
  separate Claude and Codex channels, dual-agent activity, truthful success and
  failure, attention, critical alert, repository push, reposition, dismissal,
  and hidden.
- The 15-event matrix is priority-then-time ordered. Queue depth is bounded at
  32; repeated events coalesce within 750 ms. Critical events preempt all
  interruptible states. Idle is always interruptible.
- `task.succeeded` and `git.push_succeeded` may be emitted only after the
  caller supplies `confirmed: true` and bounded printable provenance for the
  result. A generic celebration is presentation intent and settles to idle;
  the Familiar infers neither gate completion nor repository publication.
- Nero uses magenta/violet/cyan void effects. Claude uses warm amber clockwise
  circular/rune effects. Codex uses ice-blue counterclockwise grid/hex effects.
  Agent identity must remain readable without relying on color alone.
- The shipped RGBA atlas `assets/nero/nero-voidcaster-v2.png` is sliced as 8
  columns by 2 rows of exact 192x208 cells, with nearest-neighbor scaling at
  1x, 2x, and 3x. The JSON contract records its SHA-256, row-major crop
  formula, source/alpha provenance hashes, frame groups, and explicit
  per-state base-frame fallback registry.

## Architecture and authority

1. `PresenceIntent` remains the renderer-neutral brain-facing API.
2. `FamiliarRuntime` maps intents to exact, bounded v2 event IDs in
   uniquely named, atomically published envelopes under
   `familiar/runtime/command.d/`; it never launches the executable. The spool
   is bounded to 32 envelopes/16 KiB and applies backpressure when no consumer
   acknowledges. Envelopes are deleted only after UI-thread acceptance;
   malformed envelopes are quarantined as `.bad`.
3. The WPF overlay runs only after explicit user launch. It performs no model,
   network, shell, source-gate, publication, approval, or voice work.
4. Commands are display-only data. Unknown IDs fail closed. Labels are
   printable, single-line, and bounded to 160 characters.
5. Review Inbox information remains a queue-view. The Familiar may present an
   attention event but cannot approve, reject, finalize, merge, or publish.
6. Missing animation art uses the declared per-state safe base-frame fallback
   and reports fallback status in Mission Control; it never crashes or invents
   success.

## Interaction and accessibility

The overlay is click-through by default. The tray exposes pause, reduced
motion, interaction, Mission Control, dismiss, and exit. Interactive mode
supports click, double-click, drag, hover, right-click, and Escape. Dialogue is
typed at 52 characters per second and bounded to 10 visible lines. Audio is off
by default and no TTS implementation is authorized.

Reduced-motion mode preserves semantic state changes while removing large
travel, shake, and particle-heavy motion. Critical/failure/attention states use
shape, label, and motion distinctions in addition to color. Active-state
automation names are exposed to screen readers.

## Acceptance criteria

- The locked identity remains recognizable at 1x, 2x, and 3x.
- Claude and Codex remain distinguishable by geometry, direction, label, and
  palette, including during `agents.dual_active`.
- `system.critical` preempts lower-priority activity and the bounded queue never
  grows without limit.
- Missing art falls back safely and visibly without terminating the runtime.
- No success state is inferred from an attempted action.
- Reduced motion preserves all state meanings.
- Atlas dimensions, alpha support, cell geometry, and crop map are verified
  deterministically before release.
- No autostart, daemon, local model, network connection, voice synthesis, shell
  execution, or source-gate authority is introduced.

## Changelog

- 2.0.0 (2026-07-18) — Toni-directed Void Guardian identity, exact event/state
  contract, generated production atlas, accessibility, and strict authority
  boundaries.
- 1.0.0 (2026-07-17) — Initial Phase 2 semantic bridge and compact Mission
  Control surface.
