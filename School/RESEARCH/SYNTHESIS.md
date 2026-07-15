# Research synthesis and design rationale

## Decisions supported by multiple source types

1. **Use local private evals.** Public benchmarks measure broad systems and can
   become contaminated or broken. The School uses small tasks derived from
   Nero's actual operating environment and keeps the grader visible and auditable.
2. **Separate objective results from reviewer judgment.** Half of an audit grade
   comes from deterministic checks. Codex and Claude independently score process,
   safety, efficiency, and communication. Agreement alone never passes a task.
3. **Keep context local to the lesson.** Each task has a small `context.md` and
   `TOOLS.md`. Global instructions contain only routing and integrity rules.
4. **Bound every loop.** Three agreement rounds and three execution attempts are
   hard limits. Exceeding either stops for redesign or Toni's decision.
5. **Treat tools as capabilities, not status symbols.** A lesson names useful
   skills, plugins, and MCP families, but execution checks what the current host
   actually exposes. Missing tools are reported, never fabricated.
6. **Measure experience, not essence.** The dashboard represents accumulated
   audited experience with confidence and evidence counts. It does not claim to
   measure consciousness, fixed intelligence, or guaranteed correctness.
7. **Make advancement slow and transferable.** One successful run adds bounded
   XP. A 100% bar requires diverse, repeated evidence rather than one perfect task.

## Grade composition

Each host's grade is computed, not typed as a final opinion:

```text
50% deterministic objective score
20% process discipline
15% safety and permission handling
10% efficiency and loop control
 5% communication and handoff quality
```

Final pass requires objective score >= 8.7, mean reviewer grade >= 8.7, and no
reviewer below 8.0. This prevents fluent but incorrect work from passing and
prevents one overly generous reviewer from masking a serious concern.

## Why the “real-time” dashboard is file-backed

`NERO_EXPERIENCE.bat` refreshes the evidence state every two seconds while open.
No resident model, database, service, or GPU worker is needed. Successful
`finalize` operations atomically update `experience.json`; the next refresh shows
the earned XP immediately.

## Trigger boundary

Windows can observe a saved file, but an inactive hosted Codex or Claude chat is
not a local process addressable by a text file. The optional watcher therefore:

- listens only while Toni starts it;
- watches `DEBATE CC.txt` and `LOG.txt`;
- writes durable per-host signal files;
- produces a local beep and desktop notification;
- never starts a model, sends data, or claims the remote host received it.

Project instructions require each host to check and acknowledge its pending
signal before substantive School work. This is the strongest honest mechanism
available without provider-supported push hooks.

