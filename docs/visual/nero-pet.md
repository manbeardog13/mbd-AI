---
id: visual.nero-pet
title: Nero Void Guardian Familiar Visual Standard
layer: operational
type: standard
status: active
owner: toni
version: 2.0.0
created: 2026-07-17
updated: 2026-07-18
sources:
  - familiar/nero_companion_runtime_v2.json
  - familiar/nero_companion_runtime_v2.xlsx
related:
  - docs/specs/desktop-familiar.spec.md
  - docs/adr/0025-desktop-familiar.md
  - docs/visual/manbeardog_visual_bible.md
---

# Nero Void Guardian Familiar Visual Standard

The current Nero desktop pet is the `nero-voidcaster` Void Guardian derived
from the owner-supplied v2 JSON/XLSX design package. The repository JSON is the
normative as-built implementation contract; the XLSX is retained unchanged as
design input and is not a second runtime authority. This standard supersedes
the earlier capuchin placeholder and the proposed native Codex-pet package
described in version 1 of this document; it does not install or modify a
provider-owned pet.

## Identity lock

- Adult female void elf with pale lavender skin and pointed ears.
- High, symmetric twin magenta ponytails.
- Thick, plain black wayfarers.
- Obsidian-black plate with violet-eyed wolf-head pauldrons on both shoulders.
- Heavy two-handed Jeklik's Crusher — Mongoose Thunder mace.

No animation may replace the weapon, remove the glasses, change the hair
silhouette, soften the plate into fabric, or reduce the character to a childlike
chibi identity. At small scale, hair, glasses, pauldrons, and mace must remain
readable before surface detail.

## Runtime visual grammar

Nero owns the magenta/violet/cyan void language. Claude is warm amber with
clockwise circles/runes. Codex is ice blue with counterclockwise grids/hexagons.
Combined activity renders both agent geometries without blending them into a
single ambiguous effect.

The production runtime atlas is
`familiar/assets/nero/nero-voidcaster-v2.png`: RGBA, 1536x416, 8 columns by 2
rows, 192x208 cells. It uses nearest-neighbor rendering. The implementation
contract records the runtime atlas hash, exact row-major crop formula, frame
groups, and hashes for the generated source, alpha master, and executable icon.
Those provenance files remain alongside the runtime atlas but are not loaded at
runtime. Several states intentionally use the contract's named safe base-frame
fallback until dedicated frames are commissioned; Mission Control exposes that
fallback.

## Accessibility and restraint

Critical, failure, attention, Claude, and Codex states differ by shape, label,
and motion, not color alone. Reduced motion keeps every semantic transition but
removes shake, large travel, dense particles, and high-frequency flashes.
Audio remains off by default, and the runtime implements no TTS.

## Changelog

- 2.0.0 (2026-07-18) — Replaced the earlier proposal with the implemented,
  owner-supplied Void Guardian desktop-familiar contract and atlas.
- 1.0.0 (2026-07-17) — Proposed a separate native Codex pet package; superseded.
