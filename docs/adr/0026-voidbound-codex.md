# ADR-0026: Voidbound Codex is a static local-first game module

**Status:** Accepted

**Date:** 2026-07-18

## Context

Toni asked for a Nero-native implementation of the Phantasy Codex Adventure
product concept: a polished persistent retro action RPG with procedural worlds,
classes, bosses, Journey and Survival play, and broad input support.

The standalone Nero API is hard-disabled in hosted mode. A game must not revive
that runtime, gain access to memory or governance surfaces, or introduce a
second application backend merely to serve deterministic assets.

## Decision

Implement Voidbound Codex as a self-contained Canvas/JavaScript module under
`app/static/adventure/`. A narrow stdlib-only HTTP host serves those immutable
assets on loopback. The host exposes no mutation or model API. Game persistence
is a versioned browser-local record; rankings are explicitly local rather than
presented as shared or attested.

The renderer, combat simulation, procedural tile field, audio synthesis, input
mapping, and progression remain dependency-free. This follows the Principle of
Least Intelligence and keeps the feature inspectable by one maintainer.

Companion art is imported through immutable, hashed project copies rather than
read from user pet folders at runtime. Each companion shares the 8×11 pet atlas
contract behind one renderer/behavior adapter. Published Iskra and Nero assets
are marked validated; Mia remains explicitly provisional until her independent
build publishes validation. The game never mutates or waits on that build.

## Consequences

- The game runs offline after checkout and requires only Python plus a browser.
- It never reads Nero's memory database or Review Inbox and cannot execute a
  gate, tool, model, or external command from browser code.
- A future shared leaderboard requires a separate approved ADR with identity,
  abuse, privacy, and authority boundaries; local rankings are the only v1
  behavior.
- Visual art is procedural in v1, avoiding copied or externally licensed game
  assets while keeping a replaceable asset boundary. v1.1 adds project-original
  generated key art and Toni's versioned pet assets with recorded provenance.
