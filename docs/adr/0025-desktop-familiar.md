# ADR-0025: Mission Control manifests through an opt-in Desktop Familiar

**Status:** Accepted and amended (directed by Toni, 2026-07-18)
**Date:** 2026-07-17
**Amended:** 2026-07-18

## Context

Mission Control needs a recognizable, glanceable expression outside provider
chat windows. The first working manifestation used a capuchin placeholder.
Toni subsequently supplied the machine-readable `nero-voidcaster` v2 design
package and directly instructed implementation of the new Nero pet. The
supplied JSON/XLSX remain preserved externally; the repository JSON is the
normalized as-built implementation contract derived from that package.

## Decision

Adopt `docs/specs/desktop-familiar.spec.md` v2 and
`familiar/nero_companion_runtime_v2.json`. The Desktop Familiar's visual
identity is amended from the capuchin placeholder to the locked adult female
Void Guardian silhouette. The change is an explicit owner-directed identity
decision, not an inference by a provider or runtime.

Keep the architecture renderer-neutral and cold. `FamiliarRuntime` writes one
bounded display-only event; it never launches the overlay. The WPF executable
remains opt-in and implements presentation only: no model, voice, network,
shell, gate, approval, merge, publication, or memory authority. Source and the
v2 JSON contract are authoritative; generated binaries are reproducible build
artifacts.

Success is provenance-bound at the bridge: generic positive presentation
intent is not completion evidence. `task.succeeded` and `git.push_succeeded`
require an explicit confirmation flag plus a bounded caller provenance string.
The bridge advertises only the L1 capabilities the shipped overlay implements;
full-body artwork alone does not promote the runtime to a higher presence tier.

## Consequences

- The capuchin art is legacy placeholder material, not current Nero Familiar
  identity.
- Claude, Codex, and Nero are visually separable by shape and motion as well as
  color; events can be inspected without granting the overlay agency.
- Missing state-specific art degrades to the verified atlas and a visible
  fallback marker while preserving runtime safety.
- Future identity changes require another explicit owner decision and contract
  revision; renderer changes do not require orchestration changes.

## Alternatives considered

- **Keep the capuchin as canonical:** superseded by Toni's direct v2 identity
  instruction.
- **Launch the Familiar from the bridge:** rejected because hidden lifecycle
  work violates the opt-in boundary.
- **Let the Familiar infer or execute review actions:** rejected because a
  presentation surface must never become an authority.
- **Put animation commands in the brain API:** rejected because it couples
  cognition to one renderer and weakens replaceability.
