# ADR-0012 — Human-triggered external council for frontier reasoning

**Status:** Accepted (2026-07-13, Toni)

## Context

Nero's local model is the default reasoning path, but some architecture and
implementation tasks benefit from frontier reasoning. Toni specifically wants
OpenAI and Anthropic to collaborate rather than receive isolated copy-and-paste
prompts. ADR-0006 already permits cloud reasoning only as an explicit,
transparent escalation.

## Decision

Add an **External Council** that is disabled by default and runs only after two
human choices: enabling it in private `config.yaml` and pressing the Council
button for a specific task. One run is strictly bounded:

```text
OpenAI (architect) → Claude (builder) → OpenAI (reviewer)
```

Nero sends only the requested task and the immediately prior council handoff.
It never automatically attaches chat history, long-term memory, world state,
local files, capabilities, or API keys. The browser shows the exact project
content transmitted on each handoff, while the application log records only
provider, stage, run ID, and character count. Council output is not persisted to
Nero memory by this first version.

## Consequences

- Keeps Nero local-first; ordinary chat never leaves the machine.
- Makes the cloud escalation visible, reviewable, and cost-bounded to two or
  three requests.
- Requires separate API accounts and usage billing; chat subscriptions are not
  relied upon.
- Council output is advice, not an autonomous change to the project. Toni still
  reviews it before any action.

## Alternatives considered

- **Cloud-by-default model router** — rejected because it violates ADR-0006.
- **Autonomous model-to-model loop** — rejected because it obscures cost,
  compounds errors, and removes the human checkpoint.
- **Copy and paste between web chats** — retained as a fallback, but it does
  not provide a transparent, reproducible Nero handoff.

