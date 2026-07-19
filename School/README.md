# Nero School

Nero School is a repeatable, evidence-gated training environment for Nero under
Codex and Claude supervision. It is not model fine-tuning and it does not start
a local language model. Each lesson is a bounded repository task with explicit
context, allowed tools, deterministic checks, capped debate, dual-host audit,
and a reversible experience award.

## Start here

1. Read `SCHOOL_RULES.md` and `CURRICULUM.md`.
2. Run `NERO_EXPERIENCE.bat` to see the live evidence dashboard.
3. Give `CLAUDE_IMPLEMENTATION_BRIEF.md` to Claude. Initial tasks are executable
   but intentionally locked until Claude reviews their first agreement round.
4. In a task folder, inspect `TASK.md`, `context.md`, `TOOLS.md`,
   `Task_agreement.txt`, and `AUDIT.txt`.
5. Codex and Claude agree on the exact task digest, then `RUN_TASK.bat` prepares
   an isolated attempt directory.
6. Nero completes the task inside the printed `work` directory.
7. `GRADE_LATEST.bat` runs deterministic checks. Codex and Claude then append
   independent audits through `tooling/schoolctl.py audit`.
8. `schoolctl.py finalize` awards XP only when the deterministic score and
   combined audit reach at least 8.7/10.

No task may exceed three agreement rounds or three execution attempts. Failure
after the cap stops for diagnosis and task redesign instead of looping forever.

## Honest limitations

- Experience percentages are conservative estimates derived from recorded
  evidence. They are not objective measurements of intelligence.
- A user-owned filesystem cannot prove that only Codex or Claude edited a file.
  The School restricts accepted actor labels, hash-chains entries, binds
  agreement to task digests, and relies on Git history for tamper evidence.
- `DEBATE CC.txt` cannot wake an inactive hosted chat by itself. The opt-in
  watcher creates durable pending signals and a desktop notification. An active
  or newly started host must read and acknowledge its signal.

