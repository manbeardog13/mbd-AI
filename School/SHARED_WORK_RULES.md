<!-- NERO_SCHOOL_SHARED_WORK_V1:BEGIN -->
# Nero School shared-work protocol

- A local project opts into this protocol only when it contains
  `School/DEBATE CC/LOG.txt` and `School/tooling/schoolctl.py`.
- After the minimum read-only probe needed to detect opt-in, and before the first
  substantive mutation, execution, task design, or audit, append a START entry
  with `schoolctl.py log --actor codex|claude`. Greetings, simple questions,
  presence checks, and unrelated read-only answers do not write a log.
- Check the current host's `.signals/<host>.pending.json` before shared School
  work and acknowledge it with `schoolctl.py ack --actor <host>`. A signal is a
  durable notice, not proof that an inactive hosted chat was awakened.
- Never write a review, agreement, or log entry on behalf of the other host.
- Task debate is capped at three rounds and execution at three attempts. Stop
  and escalate after the cap; never recurse indefinitely.
- Do not edit School experience levels directly. After deterministic grading
  and independent Codex/Claude audits, run `schoolctl.py finalize`; only a valid
  result at or above 8.7/10 may award XP.
- Append a FINISH entry when the substantive shared task ends, including the
  audited grade when one exists and any remaining blocker.
<!-- NERO_SCHOOL_SHARED_WORK_V1:END -->
