# Shared task protocol

The state file is cold, local coordination metadata. It is not Nero's mind and
does not grant either provider access to the other.

## Stored fields

- sanitized objective and acceptance criteria;
- non-sensitive tags and repository/path references;
- topology, lane role, optional write scope, status, and expiring lease;
- bounded result summary, evidence references, checks, risks, and touched paths;
- verdict, explicit approval marker, quality score, latency, and timestamps.

Do not store raw prompts, source contents, credentials, connector payloads,
hidden instructions, private chat logs, or chain-of-thought.

## Typical commands

```powershell
python scripts/hybrid_brain.py --state <state> create `
  --objective "Audit the authentication boundary" `
  --acceptance "Tests cover token rejection; no credential is logged" `
  --topology parallel-analysis --task-kind security-audit --tags "security,auth" `
  --references "src/auth,tests/auth"

python scripts/hybrid_brain.py --state <state> claim --task-id <id> --host codex

python scripts/hybrid_brain.py --state <state> submit `
  --task-id <id> --host codex --summary "..." `
  --evidence "tests/auth.log,src/auth" --checks "unit tests pass" --risks "..."

python scripts/hybrid_brain.py --state <state> ready --task-id <id>
```

For `build-review`, use `--builder codex|claude`. A reviewer submission must add
`--verdict pass|changes-requested|blocked`. For `disjoint-build`, declare both
`--codex-scope` and `--claude-scope`; touched paths are checked against them.

Approval can feed the learning ledger:

```powershell
python scripts/hybrid_brain.py --state <state> approve `
  --task-id <id> --approved --quality 0.92 `
  --learning-ledger "D:\mbd AI\data\continual-learning.json" `
  --decision-note "Independent evidence agreed and acceptance checks passed."
```

The coordinator does not invoke a provider. A real Codex or Claude session must
claim and submit its own lane.
