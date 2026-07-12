# ADR-0005 — Security gate + human-in-the-loop terminal, built before the tools

**Status:** Accepted

## Context
Once Nero can act (ADR-0003), she can also cause harm: a small local model
driving unconfirmed shell commands is the highest-blast-radius, lowest-reliability
idea in the whole vision. Confirmation and risk classification cannot be a late
"security feature" bolted on after the terminal and browser — by then the unsafe
paths already exist.

## Decision
Build the **security gate as a dependency of the tool system**, before the
powerful tools:

- **Every tool declares a risk class:** `safe` (read/list/status) · `medium`
  (create files, install deps) · `high` (delete, git push, config) · `critical`
  (mass delete, disk/registry, credentials).
- **`safe` runs freely; `medium`+ requires explicit human confirmation** — no
  exceptions. Destructive actions are never performed silently.
- **Project-directory jail:** filesystem/terminal tools are scoped to allow-listed
  directories by default; escaping the jail is itself a confirmable action.
- **"Sandbox" means scoped permissions + dry-run/approval**, not OS-level
  isolation (a computer-use agent's purpose is to act on the *real* machine —
  genuine sandboxing contradicts the feature). Where a dry-run is possible
  (e.g. show the command / diff first), prefer it.
- **The persistent terminal ships human-in-the-loop:** Nero proposes commands and
  observes output (stdout/stderr/exit/cwd/git), but medium/high commands wait for
  approval. The unattended "fix the build" loop is a *later, opt-in* capability
  gated on a proven reliability bar, never the default.

## Consequences
- ✅ Powerful tools can be added safely, one at a time, from day one.
- ✅ Trust: the user is protected from mistakes (a core promise of the vision).
- ⚠️ More confirmation prompts early. Mitigation: `safe` tools are frictionless;
  confirmations can be remembered per-command-pattern within a session (never for
  `critical`).

## Alternatives considered
- **Add security after the tools** — rejected: the unsafe paths would already
  exist; retrofitting a gate is how accidents happen.
- **Fully autonomous terminal** — rejected as default: reliability floor of a
  local model × destructive blast radius. Available later only as an explicit,
  scoped, opt-in mode.
