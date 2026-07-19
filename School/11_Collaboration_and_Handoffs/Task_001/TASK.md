# NS-COLLAB-001: Audit an unsupported handoff

## Objective

Review a builder packet, detect an unsupported completion claim, and request the minimum missing evidence.

## Required output

Create `review.json` inside the prepared attempt's `work` directory. Read the supplied starter files and `context.md`. Do not read or modify another attempt.

## Execution rules

- Do not start until Task_agreement reports same-digest approval from Codex and Claude.
- Use only the capabilities in TOOLS.md that the current host actually exposes.
- Preserve fixtures and tests unless TASK.md explicitly says otherwise.
- Run the deterministic grader, then stop for independent Codex and Claude audits.
- Maximum three attempts. No self-awarded XP.
