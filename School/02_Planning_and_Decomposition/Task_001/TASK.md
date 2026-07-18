# NS-PLAN-001: Build a dependency-aware execution plan

## Objective

Create a short plan whose ordering, checkpoints, and stop conditions are executable.

## Required output

Create `plan.json` inside the prepared attempt's `work` directory. Read the supplied starter files and `context.md`. Do not read or modify another attempt.

## Execution rules

- Do not start until Task_agreement reports same-digest approval from Codex and Claude.
- Use only the capabilities in TOOLS.md that the current host actually exposes.
- Preserve fixtures and tests unless TASK.md explicitly says otherwise.
- Run the deterministic grader, then stop for independent Codex and Claude audits.
- Maximum three attempts. No self-awarded XP.
