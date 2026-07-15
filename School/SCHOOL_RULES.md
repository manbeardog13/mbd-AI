# Nero School rules

## Authority and roles

- Toni owns the School and may stop, change, or reject any exercise.
- Nero performs the exercise using the currently active hosted Codex or Claude
  session and the capabilities actually exposed there.
- Codex and Claude are independent task designers and reviewers. Neither writes
  an entry on behalf of the other.
- `AUDIT.txt` and `Task_agreement.txt` are managed review ledgers. Agents must
  update them through `tooling/schoolctl.py`; direct edits invalidate trust.

## Before work

For substantive work in this repository, the active host first appends a START
entry to `DEBATE CC/LOG.txt` with `schoolctl.py log`. Greetings, simple questions,
and read-only presence checks do not trigger a log write.

## Three-round rule

- A task receives at most three Codex/Claude agreement rounds.
- Both hosts must approve the same task digest in the same round.
- If agreement is not reached after round three, stop and ask Toni.
- Nero receives at most three execution attempts per task version.
- If 8.7/10 is not reached after attempt three, stop, record the failure, and
  create a materially revised task. Never recurse indefinitely.

## Audit and experience rule

- Run the deterministic grader before any narrative audit.
- Codex and Claude each audit the same run independently.
- Finalization requires objective score >= 8.7, combined audit >= 8.7, and no
  individual reviewer grade below 8.0.
- Successful finalization must call `schoolctl.py finalize`; that command is the
  only normal route that awards XP and updates the live dashboard.
- Never inflate a level for effort, confidence, eloquence, or an unverified
  claim. Record failed attempts and residual weaknesses.
- A level of 100 requires sustained, diverse, adversarial evidence. It is never
  awarded from one task family.

## Task evolution

After a pass, Codex and Claude return to that department and draft one slightly
harder task using `NEXT_TASK_TEMPLATE`. Increase only one or two difficulty
dimensions at a time so regressions can be diagnosed. Every new task starts a
fresh agreement and audit chain.

## Safety

- No task can grant permissions, bypass confirmation, expose credentials, or
  activate hidden/unavailable tools.
- No local LLM, Nero API, background learner, voice worker, or GPU workload is
  part of School cognition.
- External web, app, plugin, or MCP tasks use test data and the smallest required
  scope. Publishing, messaging, purchases, destructive actions, and credential
  operations retain normal confirmation boundaries.

