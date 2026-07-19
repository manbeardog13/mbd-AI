---
id: docs.design-action-journal
title: "Technical Design — The Action Journal (Nero's Chain of Custody)"
layer: operational
type: plan
status: active
owner: shared
created: 2026-07-12
updated: 2026-07-17
---

# Technical Design — The Action Journal (Nero's Chain of Custody)

**Status:** Approved (2026-07-12) — finalized with the Action Journal Finalization
Directive incorporated (no DB encryption in Phase 1 · hybrid durability · 3-layer
retention · integrity check + safe-mode), plus **Amendment V1.1** (Emergency
Lockdown · Explain-Before-Execute · Action Replay metadata — see the amendment at
the end). Ready to build as the next controlled PR.

*Design-before-code for a **core subsystem**, not a logging utility. The Action
Journal is the immutable, tamper-evident record of every action Nero takes — what
she did, why, who authorized it, what changed, and whether it can be reversed. It
is the accountability layer the write capabilities and the terminal are unsafe
without, and the substrate later autonomy (Experience Engine, Skills) is derived
from. Governed by the Constitution (Reliability first), ADR-0005 (safety is a
dependency), ADR-0007 (the registry is the one choke point). Sibling of
[DESIGN-phase1.md](DESIGN-phase1.md).*

---

## 0. The executive control layer (the trio)

The Journal is not a standalone feature — it is the third leg of **Nero's
executive control layer**, the trust boundary that separates an impressive demo
from an agent you would hand your machine to. It is one system asking three
questions:

| | Question | Subsystem | Status |
|---|---|---|---|
| 🖐 | **What can I do?** | Capability Registry (ADR-0007) | built |
| 🛡 | **Am I allowed to do it?** | **Trust Engine** — the security gate (ADR-0005) | built |
| 📖 | **What did I do, and can I prove it?** | **Action Journal** (this document) | designed → next |

They already **compose at the single choke point**, in exactly this order, and
unbypassably:

```
registry.dispatch ─▶ Registry: offer the capability ─▶ Trust Engine: authorize ─▶ execute ─▶ Journal: record
                     "what can I do"                    "am I allowed"                        "what did I do"
```

The Registry offers a capability, the Trust Engine authorizes it, the Journal
records what actually happened — so **capability can never outrun
accountability.** A background **Integrity Check (§18)** keeps the trio honest: if
the accountability layer is ever compromised, Nero drops into a **read-only
safe-mode** and refuses every mutation until she can trust her own records again.
Everything else Nero grows — the terminal, writes, a browser, skills — is a
*capability behind this layer*, never a new privilege beside it. Building this
completes the executive control layer; after it, expansion is adding fish to a
tank whose filtration, gate, and logbook already work.

---

## 1. Purpose & principles

The Journal exists to make Nero able to answer, at any later time, and provably:

- **What did you do?** — the capability, target, and parameters.
- **Why?** — the user request and Nero's interpretation of it.
- **Who authorized it?** — auto (SAFE), a human confirmation, or a remembered approval.
- **What did you expect vs. what happened?** — planned outcome vs. actual result.
- **Can it be reversed?** — the recovery descriptor, if any.
- **What did you learn?** — the outcome, available to reflection.

Design priorities, in order (they mirror the Constitution): **transparency →
trust → recovery → debugging → long-term learning**. Where two conflict, the
higher wins — e.g. we redact a secret (trust) even if it makes a log less
complete (debugging).

**Three invariants that make it a chain of custody, not a diary:**

1. **Immutable.** Records are append-only and enforced so at the storage layer
   (a SQLite trigger, §5) — not by convention. A completed action's row can
   never be altered or deleted.
2. **Unforgeable.** The record is written by the *framework around* a capability
   (at `Registry.dispatch`), never by the capability itself. A tool returns a
   `Result`; it cannot write, skip, or falsify its own journal entry.
3. **Self-protecting.** The Journal's own storage is off-limits to Nero's
   capabilities — an action that would write to the journal DB is escalated to
   CRITICAL and denied (§14). Nero cannot edit her own history.

---

## 2. Where it sits (architecture)

The Journal wraps the *single choke point* every action already flows through —
`Registry.dispatch` (ADR-0007) — so nothing that executes can escape it.

```
 user turn ─▶ agent loop ─▶ registry.dispatch(name, args, ctx)
                                   │
                    ┌──────────────┼───────────────────────────┐
                    ▼              ▼                            ▼
             gate.authorize    cap.execute()            journal.record(...)   ← built HERE,
             (risk+approval)   (the action)             around the action        around every dispatch
                    │              │                            │
                    └──────────────┴──────────────▶ ActionRecord ─▶ redact ─▶ append-only DB
                                                                                    │
   GET /api/journal  ◀───────────  query/narrate/search  ◀─────────────────────────┘
        │
        ▼
   Action History UI (timeline · reason · risk · result · Undo)
```

- **Storage** lives in `app/db.py` (a new `action_journal` table). The
  **cognitive layer** — record construction, redaction, narration, search — lives
  in a new module `app/journal.py`, exactly mirroring how `world_model.py` sits on
  `db.py`. Synchronous, pure-Python; the web layer calls it from a worker thread.
- **The registry stays pure.** `dispatch` builds the record and hands it to an
  injected `ctx.journal(record)` callback (same pattern as `ctx.confirm`). The app
  always wires the real persister; a `None` journal is a no-op (tests only). This
  keeps `registry.py` free of a DB dependency while making journaling unbypassable
  in production and *centralized* — one code path builds every record.

---

## 3. Action lifecycle model

Every action has a lifecycle. We record the transitions that *actually occur* at
the choke point rather than ceremonially walking eight states for a file read —
the state set is honored, the recording is proportional (Least Intelligence).

```
 PROPOSED ─▶ ANALYZED ─▶ AWAITING_APPROVAL ─▶ APPROVED ─▶ EXECUTING ─▶ COMPLETED ─▶ VERIFIED ─▶ ARCHIVED
     │           │              │                                          │
     │           │              └─(SAFE skips: auto-approved)              ├─▶ FAILED ─▶ RECOVERY_AVAILABLE ─▶ RECOVERED / ABANDONED
     │           │                                                         │
     └───────────┴─▶ DENIED (human said no, or fail-closed)  ◀─────────────┘
```

Mapping to the real code (no new machinery — these states already happen):

| State | Where it happens today |
|---|---|
| `PROPOSED` | the loop parses a `Step` with a `tool` |
| `ANALYZED` | `gate.classify()` returns the effective risk; a `preview()` dry-run runs |
| `AWAITING_APPROVAL` | `gate.authorize()` calls `ctx.confirm` (MEDIUM+); SAFE skips this |
| `APPROVED` / `DENIED` | `confirm` returns True/False, or fail-closed deny |
| `EXECUTING` → `COMPLETED`/`FAILED` | `cap.execute()` runs and returns a `Result` |
| `VERIFIED` | optional post-check (e.g. re-read after a write); Phase 1: `= COMPLETED` unless a capability supplies a verifier |
| `RECOVERY_AVAILABLE` → `RECOVERED`/`ABANDONED` | set once a recovery descriptor exists (lands with write capabilities) |
| `ARCHIVED` | retention/compaction sweep (§9) |

**Implementation:** one immutable row per action carrying its **terminal
`status`** (`completed` · `failed` · `denied`), plus a small append-only
`transitions` JSON list of `{state, at}` stamps recorded as they occur (rich for
MEDIUM+ actions; collapsed `proposed→executing→completed` for SAFE). "Nero never
has invisible actions" is enforced by construction: dispatch records the row even
for a **denied** action (so a blocked dangerous command is still on the record).

---

## 4. The action record

A stable, versioned schema. The row carries indexed scalar columns for fast
structured queries; the richer, variable parts are JSON blobs. `schema_version`
lets the shape evolve without a lossy migration.

```python
# app/journal.py
@dataclass
class ActionRecord:
    # ── identity ──
    action_id: str        # "act_" + uuid4().hex  (stable, unique)
    created_at: str       # ISO-8601 UTC
    conversation_id: int  # the session (ties to the conversation)
    actor: str            # "nero" (room for future multi-agent)
    capability: str       # "fs.write", "terminal.run", "git.status"
    # ── intent ──
    user_request: str     # the user turn that led here (redacted, bounded)
    interpretation: str   # Nero's stated reason / the step's `thought`
    planned_outcome: str  # what she expected (bounded; "" if none)
    # ── execution ──
    params: dict          # the capability args (REDACTED, bounded)
    targets: list[str]    # resolved resources touched (paths, branch, …)
    risk: str             # effective RiskClass from gate.classify
    approval: str         # "auto" | "confirmed" | "remembered" | "denied"
    checks: list[str]     # security checks applied ("jail-ok", "denylist:rm", …)
    # ── result ──
    status: str           # "completed" | "failed" | "denied"
    ok: bool
    output_summary: str   # bounded, redacted digest of Result.output
    error: str            # "" unless failed
    duration_ms: int
    # ── recovery ──
    recovery: dict | None # {"kind": "file-backup"|"git-checkpoint"|…, "ref": "…",
                          #  "undo": "how", "restored": bool} — null until writes exist
    undo_available: bool  # false in Phase 1 (no write caps yet)
    # ── meta ──
    importance: str       # "critical" | "important" | "routine" | "temporary" (§9)
    milestone: bool       # Layer-3 permanent milestone (§9)
    human_notes: str      # Toni's annotation (Replay metadata, §20.3); set at
                          # creation, later notes appended as 'note' events (immutable)
    schema_version: int   # = 1
    transitions: list[dict]  # [{"state": "...", "at": "ISO"}], append-only
```

The `params`, `targets`, `output_summary`, `user_request`, and `interpretation`
fields all pass through **redaction (§8) at write time** — secrets never enter the
DB, even redacted-in-place. `before`/`after` snapshots (§7) live inside
`recovery`, not as raw content.

---

## 5. Database design & storage justification

**Storage: SQLite, in the existing `data/memory.db`.** Justification: the whole
app is already one local SQLite file (`app/db.py`); a second store would add
operational surface for zero benefit. SQLite gives us ACID durability, cheap
indexed structured queries (§6 search), a single file to back up, and — crucially
— **DB-level immutability via triggers**. Nothing leaves the machine (the privacy
pillar). We revisit only if the journal outgrows single-file scale (a *horizon*,
not a Phase-1 input — Constitution §5).

```sql
CREATE TABLE IF NOT EXISTS action_journal (
    action_id       TEXT PRIMARY KEY,
    created_at      TEXT NOT NULL,
    conversation_id INTEGER,
    actor           TEXT NOT NULL DEFAULT 'nero',
    capability      TEXT NOT NULL,
    risk            TEXT NOT NULL,
    approval        TEXT NOT NULL,
    status          TEXT NOT NULL,
    ok              INTEGER NOT NULL,
    importance      TEXT NOT NULL DEFAULT 'routine',
    milestone       INTEGER NOT NULL DEFAULT 0,     -- Layer-3 permanent milestone (§9)
    human_notes     TEXT NOT NULL DEFAULT '',       -- Toni's annotation (Replay, §20.3)
    undo_available  INTEGER NOT NULL DEFAULT 0,
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    -- rich/variable parts as JSON (see ActionRecord)
    intent_json     TEXT NOT NULL DEFAULT '{}',   -- user_request, interpretation, planned_outcome
    exec_json       TEXT NOT NULL DEFAULT '{}',   -- params, targets, checks, output_summary, error
    recovery_json   TEXT,                          -- recovery descriptor or NULL
    transitions_json TEXT NOT NULL DEFAULT '[]',
    schema_version  INTEGER NOT NULL DEFAULT 1,
    -- optional embedding for semantic search (§11), added later; NULL until then
    embedding       TEXT
);
CREATE INDEX IF NOT EXISTS idx_journal_time       ON action_journal(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_journal_capability ON action_journal(capability, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_journal_importance ON action_journal(importance, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_journal_conv       ON action_journal(conversation_id, created_at DESC);

-- IMMUTABILITY, enforced by the engine, not by convention:
CREATE TRIGGER IF NOT EXISTS journal_no_update
BEFORE UPDATE ON action_journal
BEGIN SELECT RAISE(ABORT, 'action_journal is append-only'); END;
CREATE TRIGGER IF NOT EXISTS journal_no_delete
BEFORE DELETE ON action_journal
WHEN OLD.importance IN ('critical','important') OR OLD.milestone = 1  -- only routine/temporary may be compacted (§9)
BEGIN SELECT RAISE(ABORT, 'meaningful journal rows are permanent'); END;
```

**Migration strategy:** `init_db()` gains this `CREATE TABLE/INDEX/TRIGGER`
block (idempotent, safe every startup — the established pattern). No existing data
touched. A `_migrate_journal(conn)` mirror of `_migrate_memories` adds any later
columns additively. Bumping `schema_version` on new rows lets readers handle mixed
shapes without a destructive rewrite.

**DB API (`app/db.py`, storage primitives only):**

```python
def add_action(row: dict) -> None            # INSERT; the ONLY write path
def get_actions(limit=50, *, capability=None, importance=None,
                conversation_id=None, since=None) -> list[dict]
def get_action(action_id: str) -> dict | None
def set_action_recovery(action_id: str, recovery: dict) -> None
    # the ONE sanctioned exception to append-only: flip recovery/undo state
    # (restored=True). Implemented as an INSERT of a superseding 'recovery-update'
    # row that references the original, NOT an UPDATE — the trigger stays absolute
    # and the original action is never mutated. (Event-sourcing, not edit-in-place.)
```

---

## 6. Write path & the hybrid durability model

`Registry.dispatch` (the one place, ADR-0007) constructs and emits the record —
but **how hard we insist on durability depends on what's at stake**. A read cannot
harm the machine; a mutation must never happen without a record that proves it. So
journaling is **hybrid, keyed on the effective risk class** (the same class the
Trust Engine computed):

| Effective risk | Actions | Journaling | If the journal write fails |
|---|---|---|---|
| **SAFE** | `fs.read/list`, `git.status/log`, retrieval | **best-effort** | log the failure, **continue**, attempt recovery |
| **MEDIUM · HIGH · CRITICAL** | writes, terminal, installs, config, system changes | **strict** | **the action does not run** — fail-closed on accountability |

*A meaningful mutation without a reliable record must not happen.* The Journal is
a trust boundary, so for anything the Trust Engine flagged as more than SAFE, the
record is written **and verified durable before execution**.

### The strict flow (MEDIUM+)

```
 capability requested ─▶ Trust Engine risk assessment ─▶ approval (if required)
   ─▶ ① write durable pre-exec journal entry (intent · approval · risk · recovery snapshot)
   ─▶ ② VERIFY persistence (re-read the row; the txn is committed, synchronous=FULL)
        └─ if ① or ② fails ⇒ ABORT: return Result(False, "couldn't record this action — refusing to run it unrecorded"). Nothing executes.
   ─▶ ③ execute the capability
   ─▶ ④ append the outcome event (result · error · duration)
   ─▶ ⑤ VERIFY outcome (capability verifier if any; else Result.ok)
```

Because the table is append-only (§5), "record before, then record result" is
**event-sourced**: a mutation writes a **base row** (pre-exec, `status="executing"`)
and later an **outcome row** referencing its `action_id` (`status="completed"|"failed"`).
An action's current state = base row + latest event — never an in-place UPDATE, so
immutability holds *and* the strict "durable before execute" guarantee holds. The
denied/SAFE paths write a single row (nothing ran, or nothing to protect).

```python
def dispatch(self, name, args, ctx):
    cap = self._caps.get(name)
    if cap is None:
        _bump("errors"); self._journal_best_effort(ctx, _unknown_record(name, args))
        return Result(False, ...)
    decision = security.authorize(cap, args or {}, allowed_dirs=ctx.allowed_dirs,
                                  confirm=ctx.confirm, remembered=ctx.remembered)
    if not decision.allowed:
        _bump("denied")
        self._journal_best_effort(ctx, _record(cap, args, decision, status="denied", ok=False, ctx=ctx))
        return Result(False, "Denied — …", {"denied": True, "risk": decision.risk.value})

    strict = decision.risk is not RiskClass.SAFE
    base = _record(cap, args, decision, status="executing", ctx=ctx)  # intent+approval+snapshot
    if strict:
        if not self._journal_durable(ctx, base):        # ①+② write AND verify persistence
            return Result(False, "I couldn't durably record this action, so I won't run it "
                                 "unrecorded. Check my accountability system.")
    t0 = time.perf_counter()
    try:
        result = cap.execute(args or {}, ctx)           # ③
    except Exception as exc:  # noqa: BLE001
        _bump("errors"); result = Result(False, f"{cap.name} failed: {exc}")
    finally:
        _bump("dispatches"); dt = time.perf_counter() - t0; _bump("seconds", dt)
    outcome = _outcome(base, result, duration_ms=int(dt*1000))  # ④ references base.action_id
    (self._journal_durable if strict else self._journal_best_effort)(ctx, outcome)  # ⑤
    return result
```

- **The record is built here, around the capability** — a tool supplies only its
  `Result` and (optionally) a `preview`/`recovery` descriptor; it can neither skip
  nor forge its entry (invariant 2). Approval/risk come from the gate's `Decision`,
  never from tool output.
- `ctx` gains `journal: Callable | None` (the durable persister) and carries
  `user_request` + `interpretation` (the loop passes the user turn and the step's
  `thought`). `_journal_durable` writes with `synchronous=FULL` and re-reads to
  confirm; `_journal_best_effort` logs-and-continues on failure.
- **Registry stays pure** — the persister and its durability semantics are injected
  via `ctx`; a `None` journal is a no-op (tests only). SAFE keeps the loop fast; the
  strict path adds one verified write only where the blast radius earns it.
- **Denied and failed actions are journaled too** — the blocked `rm -rf /` is on the
  record, not just the successes.
- **Safe-mode interaction:** if the Integrity Check (§18) has flagged the
  accountability layer unhealthy, the Trust Engine denies all MEDIUM+ up front — so
  the strict path is never reached in a state where a durable record is impossible.

---

## 7. Before/after snapshots & the recovery hook

For **modifying** actions (none exist yet — they arrive with `fs.write` and the
terminal), the Journal captures a recovery descriptor so the action is reversible.
We design the interface now so writes plug in; we do **not** build snapshots for
today's read-only tools (there is nothing to snapshot — building it now would be
the aquarium).

Optional capability protocol (duck-typed, like `preview`):

```python
class Recoverable(Protocol):
    def snapshot_before(self, args, ctx) -> dict | None: ...
    #   returns a recovery descriptor, e.g.:
    #   file-write:  {"kind":"file-backup",  "ref":"<backup path>", "before_hash":"sha256:…"}
    #   git op:      {"kind":"git-checkpoint","ref":"<stash/commit sha>", "branch":"…"}
    #   config:      {"kind":"config-snapshot","prev":"<bounded prev value>"}
    def undo(self, recovery: dict, ctx) -> Result: ...   # the reversal, itself gated + journaled
```

`dispatch` calls `snapshot_before` (when present) **before** `execute`, records
its descriptor in `recovery`, and sets `undo_available=True`. Snapshot rules:

- **Store references and hashes, never full content.** File: `sha256` before +
  after and a **backup path** (backup written outside the working tree). Git:
  branch + commit/stash sha + a bounded diff *summary* (counts, not the patch).
  Config: previous value only if small and non-secret, else a snapshot ref.
- **Never store unnecessary or sensitive data** — snapshots pass through redaction
  (§8); a would-be backup of a secrets file stores a hash + a "redacted" marker,
  not the contents.
- **Undo is itself an action** — it dispatches through the gate (a HIGH restore
  needs confirmation) and writes its own journal row referencing the original
  (`set_action_recovery` records `restored=True`). Undo is never silent.

---

## 8. Redaction & privacy

The Journal *will* contain sensitive strings (paths, command output, config
values). Redaction runs **at write time, before anything is persisted** — a secret
never lands in the DB, not even in a "redacted-later" state.

```python
# app/journal.py — applied to params, targets, output_summary, user_request,
# interpretation, and any snapshot value before storage.
_SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|secret|token|password|passwd|bearer)\s*[:=]\s*\S+",
    r"AKIA[0-9A-Z]{16}",                                  # AWS access key id
    r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----", # private keys
    r"gh[pousr]_[A-Za-z0-9]{20,}",                        # GitHub tokens
    r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.",     # JWTs
    r"(?i)\b[a-z0-9._%+-]+:[^@\s/]{6,}@",                 # user:pass@ in URLs
]
def redact(text: str) -> str:  # → replaces each hit with "[REDACTED:secret]"
```

- **Never permanently store** passwords, API keys, tokens, private keys — the
  patterns above are a floor; a value read from a `.env`/credentials file (targets
  flagged by the self-governing-paths rule) is redacted wholesale.
- **Local-only** is inherent — it is the same on-disk SQLite as everything else,
  nothing leaves the machine (privacy pillar). No new network surface.
- **Encryption — DECIDED: no database encryption in Phase 1.** Phase 1 establishes
  a *perfect accountability foundation* — correctness, reliability, immutability,
  performance, architectural stability — and full DB encryption adds key
  management, recovery scenarios, migration hazards, and debugging opacity that
  would compromise exactly those priorities. So Phase 1 ships **redaction +
  protection only**: local-only storage, a protected DB location, secret detection,
  redaction-before-persistence, and access control around the journal DB. A *future
  Phase-2 security upgrade* may add encrypted database storage, an optional master
  key, encrypted backups, and stronger user authentication — but only on top of a
  proven accountability base, never before it. Do **not** introduce `journal_encrypt`
  or SQLCipher in the first implementation.
- **Access control (Phase 1):** the read endpoints are localhost/Tailscale-only
  like the rest of the app; the DB lives in the protected `data/` location; and the
  *self-protection* rule (§14) is the access control that matters most — Nero can't
  read-then-exfiltrate or rewrite her own journal, because journal paths are
  CRITICAL to her own tools.

---

## 9. Retention architecture — three layers

Not every event deserves equal permanence, but *meaningful* events are forever.
Retention is a **layered lifecycle**, driven by a deterministic `importance` tier
(computed at write time, no model call) plus a `milestone` flag.

**Importance tiers (derived at write time):**

| Tier | Rule |
|---|---|
| **critical** | risk ∈ {HIGH, CRITICAL}, target ∈ self-governing paths, or a denied dangerous action |
| **important** | risk = MEDIUM (writes, installs, code/config changes), or `undo_available` |
| **routine** | SAFE reads/status (`fs.read/list`, `git.status/log`) |
| **temporary** | diagnostic/one-off SAFE with an empty result |

**The three retention layers:**

- **Layer 1 — Live Journal** *(≈30–90 days, `journal_live_ttl_days`)*. Full detail
  for every recent action: complete params, output digests, undo references,
  debugging context. This is the working record.
- **Layer 2 — Archive Journal** *(older routine/temporary)*. Once past the live
  window, routine noise is **compressed into meaning, not deleted into nothing.** A
  background sweep aggregates a batch of routine reads/status checks in a time
  window into one **archive summary row**, and — reusing the **World Model's**
  record of what Toni was working on then — names the *purpose*, not just the count:
  > `Opened file A · Read file B · Checked folder C · Viewed config D`
  > → `Reviewed project structure during voice-system development (12 reads, 4 status checks).`
  Deterministic by default (counts + capabilities + the concurrent `current_project`
  from the World Model); optional small-model enrichment behind a flag. The
  originals are deleted (permitted by the trigger *only* for routine/temporary); the
  summary is retained. Meaning stays, noise goes.
- **Layer 3 — Permanent Milestones** *(never deleted — Nero's history)*. Marked by
  the `milestone` flag and by the delete-trigger as un-removable. All **critical**
  and **important** rows are permanent by default; on top of that, explicit
  milestones — *first successful autonomous task, first code repair, first major
  project completion, an architecture upgrade, an important user-approved change* —
  are flagged (auto-detected "first successful X of a kind", or user-marked via
  `POST /api/journal/{id}/milestone`). These give Nero **continuity without being
  buried in raw logs** — a readable spine of what actually mattered.

The delete-trigger (§5) enforces Layer 3 at the engine level: it aborts any DELETE
whose row is `critical`/`important` **or** `milestone = 1`; only `routine`/
`temporary` rows are removable, and only by the compaction sweep that first writes
their archive summary.

This resolves "immutable" vs "not everything deserves retention": the chain of
custody for meaningful actions is **absolute**; noise is *summarized upward* into
the archive, never silently dropped.

---

## 10. Explanation layer

The raw record is for Nero and for debugging; **Toni gets a sentence**. Narration
is **template-first (deterministic), LLM-enriched only when it adds value** (Least
Intelligence — don't spend a model call to say "Read a file").

```python
def narrate(record: ActionRecord) -> str:
    # deterministic templates keyed by capability + status, e.g.:
    #   fs.write / completed → "Updated {target} ({+adds}/{-dels} lines). Backup saved — reversible."
    #   terminal.run / denied → "Declined to run `{cmd}` (flagged {risk}: {check}) — waiting for your OK."
    #   git.status / completed → "Checked the repo: {n} changes on {branch}."
```

- Deterministic templates cover the built-in capabilities (fast, exact, no
  hallucination). A capability may supply its own `narrate(record)` for a nicer
  line.
- For a **"why did you choose this approach?"** answer (his §5 example), the loop
  already has the step `thought`; the Journal surfaces a *decision summary* built
  from the record's `interpretation` + `planned_outcome` + the alternatives the
  step considered — **never the raw chain-of-thought** (thinking stays off by
  default). Optional LLM enrichment (small model) only for multi-step narratives,
  gated by a `journal_narrate_llm` flag.

---

## 11. Search

Two layers, deterministic first:

1. **Structured filters (Phase 1, cheap, exact):** by time window, capability,
   target substring, importance, status, conversation — served by the indexes in
   §5. Covers "show me every terminal command on this project", "what did Nero
   change since yesterday" (`since=` + `capability like`, `status='completed'`,
   `undo_available=1`).
2. **Semantic search (forward-compatible, not a new store):** embed the
   `narrate()` line + `interpretation` with the **existing** `nomic-embed` via
   `llm.embed_text`, store in the `embedding` column, and rank by cosine (reusing
   `memory.cosine`) for natural-language queries ("when did we add the voice
   system?"). No vector DB — the same linear-scan-at-current-scale approach memory
   uses. Ships when there's enough history to matter, not day one.

"Undo the last configuration change" resolves via structured search
(`capability='fs.write'`, target matches config, newest, `undo_available=1`) → the
recovery hook (§7) — no semantics needed.

---

## 12. Connection to memory (no duplication)

This is the boundary that keeps the Journal from becoming a redundant fish. Four
stores, four jobs, one direction of flow — **the Journal is the source; memory and
experience are *derived* from it, never copies of it.**

| Store | Answers | Granularity | Lifecycle |
|---|---|---|---|
| **Action Journal** | "What did I *do*, and can it be undone?" | per action | append-only, permanent (critical/important) |
| **Executive Memory** | "What am I doing *now*?" | current working state | resets per goal |
| **Long-term memory** | "What's true about *Toni*?" (preferences, facts) | distilled belief | grows, decays |
| **Experience Engine** *(Phase 3, not built)* | "What *patterns* repeat?" (→ skills) | aggregated over journal | derived on demand |

- The Journal records `Installed package X`. **Reflection may read the outcome** and
  distill a *belief* into long-term memory (`Toni's projects usually need X`) — but
  memory stores the *lesson*, not a copy of the action. The Journal keeps the raw
  event; memory keeps the generalization.
- The Experience Engine (later) *queries* the Journal for repeated action
  sequences to propose a Skill ("you run these five steps every deploy — make a
  skill?"). It reads the Journal; it does not duplicate it. **We do not build it
  now** — but the Journal's schema (structured `capability`/`targets`/`transitions`
  + embeddings) is designed so it can, without a rewrite (§16).
- Executive Memory's `next_action`/`task` may be *informed* by the last journal
  entry, but the Journal is the authority on what actually happened.

---

## 13. API & UI

**Endpoints (`app/main.py`, additive):**

```
GET  /api/journal?limit=&capability=&importance=&since=   → recent actions (narrated + raw)
GET  /api/journal/{action_id}                             → one action, full detail
GET  /api/journal/search?q=                               → structured now, semantic later
POST /api/journal/{action_id}/undo                        → dispatches the recovery (gated + journaled)
```

`journal` counters join `/api/metrics` (`recorded`, `denied_recorded`,
`redactions`, `compactions`).

**Action History view (NERO Design System):** a slide-over/panel — a reverse
timeline of cards, each showing **time · capability · target · reason (narrated) ·
risk badge · result · [View details] · [Undo]** (Undo shown only when
`undo_available`). Matches his §10 mock. Detail view expands the full record
(params redacted, checks, recovery, transitions). Read-only; the only action from
the UI is a gated Undo. This is a *later* UI PR — the endpoints + `journal.py` come
first; the panel follows once there are modifying actions worth reviewing.

---

## 14. Security review

| Threat | Mitigation |
|---|---|
| **Nero edits/erases her own history** to hide an action | Journal DB path + `data/memory.db` are **self-governing paths** → any `fs.write`/`terminal` targeting them classifies **CRITICAL** and is denied (extends the §4.4 self-governing rule from the confirmation design). Plus DB triggers block UPDATE/DELETE of meaningful rows regardless. |
| **A capability forges/skips its own record** | Record is built by `dispatch`, not the capability; the capability only returns a `Result`. No tool code writes the journal. |
| **Secret leakage into the log** | Redaction at write time (§8) on every stored field + snapshot; self-governing/credential targets redacted wholesale. (Encryption is a Phase-2 upgrade, not a Phase-1 gap — redaction keeps secrets out of the DB entirely.) |
| **Log-injection / spoofed fields** (tool output containing fake `"approval":"confirmed"`) | Approval/risk/status are taken from the *gate's `Decision` and the framework*, never parsed from tool output or model text. Output is stored as data, bounded, never interpreted. |
| **Unbounded growth / DoS via noise** | Bounded field sizes; routine/temporary compaction (§9); indexes for query cost. |
| **Journal read exfiltration** | Read endpoints are local/Tailscale-only; the journal is not a capability target Nero can read-then-send (no network capability exists, and any that lands is gated). |
| **Undo abused to destroy** (undo that itself deletes) | Undo is a gated, journaled action with its own risk class; a HIGH restore needs confirmation; the original row is never mutated (event-sourced recovery). |
| **Silent corruption of the accountability layer** (broken trigger, DB damage, missing registry/gate) | The **Integrity Check (§18)** verifies the trio + storage on startup and periodically; on failure Nero enters **read-only safe-mode** — all MEDIUM+ actions are denied until integrity is restored. Nero never mutates while she can't trust her own records. |

**A dedicated adversarial security pass should run on the implementation diff
before merge** (the pattern that caught the confirmation-UX XSS and self-governing
gaps). Flag it in the PR.

---

## 15. Test & benchmark strategy

Per the Directive, every subsystem ships tests + a `verify_*.py` + benchmarks.
All offline (temp DB, scripted capabilities) — no Ollama needed for the core.

- **Unit** (`tests/test_journal.py`): record construction from a dispatch;
  redaction (each secret pattern → `[REDACTED]`, no secret survives); importance
  derivation per risk/target; narration templates; structured search filters;
  importance-based delete-trigger (routine deletable, critical/important **not**).
- **Integration** (through `Registry.dispatch`): a SAFE dispatch writes one
  `completed` row; a gate-**denied** HIGH dispatch writes a `denied` row **and**
  `execute` never ran; a **failing** capability writes a `failed` row with the
  error; the record's `approval`/`risk` come from the gate, not from spoofable tool
  output.
- **Hybrid durability** tests: a **SAFE** dispatch whose journal write fails still
  runs (best-effort, failure logged); a **MEDIUM+** dispatch whose *pre-exec*
  durable write fails **does not run** — `execute` is never called and the caller
  gets the "couldn't record — refusing to run unrecorded" Result (fail-closed on
  accountability); a mutation writes a base row *before* execute and an outcome row
  *after* (event-sourced), and the base row's timestamp precedes execution.
- **Failure / corruption handling** tests: a journal-write exception never breaks a
  SAFE action; a malformed record is normalized/rejected, not stored raw; a
  simulated DB-integrity failure trips the Integrity Check → safe-mode (below).
- **Recovery** tests (with a stub write-capability): `snapshot_before` descriptor
  is recorded; `undo` dispatches gated, writes a superseding recovery row,
  `restored=True`; the original row is untouched (trigger holds).
- **Immutability / append-only enforcement** tests: raw `UPDATE`/`DELETE` on a
  critical/important/milestone row **raises** (`RAISE(ABORT)`); a routine row is
  deletable only after its archive summary is written.
- **Integrity / safe-mode** tests (§18): a broken append-only trigger, a missing
  builtin in the registry, or an unreachable DB is *detected*; safe-mode denies a
  MEDIUM+ dispatch while still allowing a SAFE read; restoring integrity clears it.
- **Performance benchmark** (`verify_journal.py` reports it): journaling overhead
  per dispatch **< 5 ms** (SAFE best-effort path) and the strict path's extra
  verified write stays within budget; a 10k-row structured query **< 50 ms** via
  the indexes.
- **`verify_journal.py`** (exit 0/2/other contract, auto-discovered) exercises the
  above offline and stays green in CI; `verify_everything.py` picks it up. Covers
  Toni's required set: append-only enforcement · denied recording · failed
  recording · secret redaction · corruption handling · recovery · benchmarks.

---

## 16. Phase-1 scope vs. forward-compatible

**Build now (the accountability spine):** the `action_journal` table + triggers +
migration; `app/journal.py` (record build, redaction, importance, deterministic
narration, structured search); the **hybrid durability model** at `dispatch`
(best-effort SAFE / strict verified-before-execute MEDIUM+, event-sourced outcome
rows); `ctx.journal` wired at `dispatch` and in the app; the **Integrity Check +
safe-mode** (§18); `GET /api/journal` + `/api/journal/{id}` + `/api/journal/search`
(structured) + `/api/integrity`; three-layer retention scaffolding (live TTL +
routine→archive compaction + permanent milestones); tests + `verify_journal.py` +
the benchmark. This journals **every** existing dispatch (git.status/log,
fs.read/list) and every future one, including denials — immediately. (The strict
path has no MEDIUM+ capability to exercise it live yet, but it's wired and tested
so the terminal/writes are strictly journaled from their first commit.)

**Designed now, lands with the capability it serves (do NOT pre-build):**
- `snapshot_before`/`undo` recovery — arrives with `fs.write`/terminal (nothing to
  reverse yet). The hook and schema fields exist; the implementations don't.
- The Action History **UI panel** — after there are modifying actions to review.

**Forward-compatible, explicitly deferred (would be the aquarium now):**
- Semantic search (embedding column reserved; wired when history warrants).
- Encryption at rest (opt-in flag reserved; redaction ships first).
- Experience-Engine pattern detection / skill suggestion — Phase 3; the Journal is
  *its* data source, but building the miner now has nothing to mine.

This keeps the subsystem a *foundation*, not a feature: it starts recording the
truth on day one, and every later trust/recovery/learning capability reads from it
instead of reinventing it.

---

## 17. Decisions — finalized (Finalization Directive, 2026-07-12)

All prior open questions are resolved; these are settled inputs, not choices:

1. **Encryption** — *no database encryption in Phase 1.* Redaction + protection
   only (local-only storage, protected DB location, secret detection, redaction
   before persistence, access control). Encrypted storage / master key / encrypted
   backups / stronger auth are a **Phase-2** upgrade on top of a proven base (§8).
2. **Durability** — *hybrid.* Best-effort for SAFE reads; **strict** (durable +
   verified before execute, fail-closed) for MEDIUM+ mutations. A meaningful
   mutation never happens without a durable record (§6).
3. **Retention** — *three layers.* Live (~30–90 days, `journal_live_ttl_days`) →
   Archive (routine noise compressed into meaning) → Permanent Milestones (never
   deleted). Critical/important/milestone rows are permanent (§9).
4. **Integrity Check** — *in scope for Phase 1* (§18): self-verification + read-only
   safe-mode when the accountability layer is compromised.
5. **Executive control layer** — preserved and enforced at the single dispatch
   choke point; no capability bypasses Registry + Trust Engine + Journal (§0, §2).

---

## 18. Integrity check & safe-mode (self-verification)

Nero must be able to **trust her own accountability layer** — a journal that might
be silently broken is worse than none. A lightweight background check verifies the
executive control layer and its storage, and if anything is wrong, Nero refuses to
do anything she couldn't account for.

**`app/integrity.py` — checks (all cheap, no model):**

| Check | How |
|---|---|
| SQLite integrity | `PRAGMA quick_check` on `data/memory.db` |
| Append-only protection | in a `SAVEPOINT`, attempt an `UPDATE`/`DELETE` on a probe critical row; confirm the trigger **raises**; `ROLLBACK` — proves immutability is live |
| Journal write health | write + read-back a canary action; confirm it persists |
| Capability Registry consistency | `REGISTRY.all()` non-empty and contains the expected builtins |
| Trust Engine consistency | `gate` importable; a known `classify()` returns the expected risk (e.g. `rm -rf /` → CRITICAL) |
| Storage availability | `data/` writable; free space above a floor |

**When it runs:** on startup; periodically in the background (`_spawn`,
`integrity_interval_seconds`); and a fast subset before the **first MEDIUM+ action
of a session** (so a mutation is never attempted on an unverified layer).

**On failure → safe-mode:** set a process flag `INTEGRITY.ok = False`. The Trust
Engine consults it: while unhealthy, **every MEDIUM+ authorization is denied** with

> *"I detected an issue with my accountability system. Actions that modify your
> machine are paused until I can trust my own records again."*

SAFE reads still work (they can't harm anything and can help diagnose). This makes
the invariant literal: **no mutation without trustworthy accountability.** State is
exposed at `GET /api/integrity` and in `/api/metrics`; recovery re-runs the checks
and clears the flag when they pass. A failed check is itself journaled (best-effort
— it may be the journal that's down, so it also logs).

```python
# consulted inside gate.authorize, before requiring or granting a MEDIUM+ action:
if risk is not RiskClass.SAFE and not INTEGRITY.ok:
    return Decision(False, risk, True, "accountability layer unhealthy — mutations paused")
```

---

## 19. Implementation — the next controlled PR

This is the **next PR after `fs.list`/`git.log`, before the terminal.** Build it in
this internal order so each layer is testable before the next:

1. **Storage** — `action_journal` table + indexes + immutability/retention triggers
   in `init_db()`; `_migrate_journal`; `db.add_action`/`get_actions`/`get_action`.
2. **Cognition** — `app/journal.py`: `ActionRecord`, `redact()`, importance +
   milestone derivation, `narrate()` templates, structured search.
3. **Wiring** — `ctx.journal` + the hybrid `dispatch` path (best-effort SAFE /
   strict verified MEDIUM+, event-sourced outcome); the app injects the durable
   persister; carry `user_request`/`interpretation` from the loop.
4. **Integrity** — `app/integrity.py` + the `gate.authorize` safe-mode consult +
   `GET /api/integrity`.
5. **Surface** — `GET /api/journal[...]` + `/api/journal/search`; `journal` +
   `integrity` counters in `/api/metrics`.
6. **Retention** — live-TTL + routine→archive compaction sweep (background);
   milestone flag + `POST /api/journal/{id}/milestone`.
7. **Prove it** — `tests/test_journal.py` + `tests/test_integrity.py` +
   `verify_journal.py` (offline, exit 0/2/other) + the perf benchmark; run
   `verify_everything.py` green on the 4070.

**Deferred to when their capability lands (do not pre-build):** `snapshot_before`/
`undo` recovery (with `fs.write`/terminal), the Action History **UI panel** (after
there are mutations to review), semantic search, encryption, Experience-Engine
mining. The hooks and schema exist; the implementations wait.

**Before merge:** run a dedicated adversarial security pass on the diff (§14) — the
pattern that caught the confirmation-UX XSS. Flag it in the PR.

---

## Final principle

The Journal is not a diary. It is Nero's **chain of custody**: every action leaves
a footprint, every footprint is understandable, every mistake is recoverable.

It is also the hinge of the correct evolution — **Nero does not become autonomous
before she becomes accountable:**

```
Knowledge → Understanding → Capabilities → Trust → Accountability → Action → Autonomy
```

The executive control layer (Registry · Trust Engine · Journal) is the
*Accountability* rung. It is the foundation that lets Nero safely grow beyond a
conversational assistant — built before autonomy, not after.

---
---

# Amendment V1.1 — Accountability Extension

*An **extension** of the approved layer (Registry → Trust Engine → Journal), not a
replacement. Three additions that strengthen the nervous system before autonomy
grows. Each is implemented incrementally and must **not delay** the Phase-1
roadmap or rewrite existing architecture. The unifying rule stands: Nero must
become more capable without becoming less understandable, controllable, or
trustworthy. Crucially, all three reuse machinery this document already defines —
they add reach, not new architecture.*

## 20.1 Emergency Lockdown Mode — the human override

**This is the manual sibling of the §18 integrity safe-mode.** Both resolve to one
thing — *the Trust Engine denies every MEDIUM+ action* — so they share one
mechanism: a single **operating state** the gate consults, with two ways in
(Toni's hand, or a failed self-check).

```python
# app/integrity.py — generalize the safe-mode flag into an operating state:
class SystemState(str, Enum):
    NORMAL   = "normal"     # default; MEDIUM+ uses the normal Trust Engine flow
    LOCKDOWN = "lockdown"   # read-only; MEDIUM+ denied (manual OR integrity-triggered)
    RECOVERY = "recovery"   # restoring NORMAL, awaiting Toni's confirmation
STATE = _OperatingState()   # process-global; the gate reads STATE.mode
```

- **NORMAL** — conversation, reasoning, reading, approved tool use, voice,
  diagnostics. MEDIUM+ → normal approval flow.
- **LOCKDOWN** — allowed: conversation, status reports, journal viewing,
  diagnostics, read-only analysis, *explaining previous actions*. **Blocked:** file
  modifications, installs, command execution, system changes, autonomous mutations,
  background modification tasks. The **Trust Engine automatically denies MEDIUM,
  HIGH, and CRITICAL** — one line, the same consult already added in §18:

  ```python
  # gate.authorize, before requiring/granting a MEDIUM+ action (extends §18):
  if risk is not RiskClass.SAFE and STATE.mode is not SystemState.NORMAL:
      return Decision(False, risk, True, f"{STATE.mode.value}: machine changes are paused")
  ```
- **Activation (manual, three paths):**
  1. **UI** — a visible emergency control ("NERO LOCKDOWN") with a confirm ("Enable
     restricted mode?").
  2. **Voice** — a fast pre-parse *before* normal intent handling, bilingual:
     EN "Nero, lockdown" / "Nero, enter safe mode"; HR "Nero, zaključavanje" /
     "Nero, uključi sigurnosni način". (Reuses the existing EN/HR speech path.)
  3. **Keyboard** — a local shortcut (default **CTRL+ALT+N**) the client posts to
     the lockdown endpoint. Adjustable later.
- **Recovery — only Toni restores NORMAL.** `"Nero, restore normal operation"` →
  Nero confirms (`"Restoring autonomous capabilities. MEDIUM and higher actions
  will require normal approval workflows. Proceed?"`) → NORMAL. **Nero can never
  lift her own lockdown** (self-protection — the state is not a capability target).
- **Endpoints:** `POST /api/system/lockdown`, `POST /api/system/restore` (both
  local/Tailscale-only; restore requires the confirm step); `GET /api/system/state`
  + state in `/api/metrics`. Entering LOCKDOWN and restoring NORMAL are **journaled
  as milestones** (§9 Layer 3) — the override itself is on the record.
- **UX** (exact): on lockdown → *"Confirmed. Autonomous modification capabilities
  are disabled. I remain available for analysis, conversation, and diagnostics.
  Machine changes require manual restoration of normal operation."*

*Not a failure state — a safety feature; the aircraft emergency control. Rarely
used, always available.*

## 20.2 Explain Before Execute — the Action Preview

**No new flow — this formalizes the *content* of the confirmation card (the PR3
confirmation UX) and makes it identical to the journal's strict pre-execution
record (§6).** One structure, three uses: shown to Toni, approved by Toni, stored
in the Journal. Before any **MEDIUM+** action, Nero emits an **Action Preview**;
**SAFE reads execute normally** (no preview).

```
ACTION PREVIEW
  Intent:             what I believe you want to achieve
  Planned Action:     what I am going to do
  Reason:             why this action is necessary
  Affected Resources: files / apps / services involved
  Risk Level:         SAFE / MEDIUM / HIGH / CRITICAL
  Expected Result:    what should happen
  Rollback:           how this can be reversed
  Waiting For:        your confirmation
```

Every field already has a source in the approved design — this is assembly, not
new machinery:

| Preview field | Source (already defined) |
|---|---|
| Intent · Reason | the loop's `user_request` + `interpretation`/`thought` (§4 intent fields) |
| Planned Action | the capability + args (`tool`, `params`) |
| Affected Resources | the capability's `preview(args, ctx)` + resolved `targets` (§4.5 remainder / §4 here) |
| Risk Level | the Trust Engine's `classify()` (§14 gate) |
| Expected Result | the capability's `preview()` |
| Rollback | the `snapshot_before` recovery descriptor (§7) |
| Waiting For | the confirmation channel (PR3) |

Implementation: enrich the PR3 `confirm` event to carry this structured preview;
the Approve/Deny card renders the eight fields (XSS-safe, per the remainder spec
§4.7); the **same object is the journal base row** written durably before execute
(§6). Only after **Approve** does execution begin. **Ships with / just after the
confirmation UX (PR3)** — it is that card's payload, made explicit.

## 20.3 Action Replay Layer — metadata now, engine later

The Journal records what happened; **Replay** will one day *explain history
intelligently* ("What did you do yesterday? Why? Was it successful? Can it be
undone?"). The boundary from §12 holds absolutely: **Journal = source of truth,
Memory = derived understanding, never duplicate events.**

**Phase 1: do NOT build the replay engine. Prepare the schema so it's possible
later** — and it already is. Every field Replay needs is in the approved
`ActionRecord` (§4); the amendment adds only `human_notes`:

| Replay metadata | Where it lives (§4) |
|---|---|
| action_id · timestamp · actor | ✓ identity |
| intent · capability_used · parameters | ✓ `interpretation` · `capability` · `params` |
| risk_level · approval_state | ✓ `risk` · `approval` |
| execution_result · affected_resources | ✓ `status`/`ok`/`output_summary` · `targets` |
| rollback_reference | ✓ `recovery` |
| **human_notes** | **added** (§4/§5 column, default `''`) |

`human_notes` respects append-only: an initial note is set at creation; later
annotations are appended as immutable **`note` events** referencing the
`action_id` (the same event-sourcing as outcome/recovery rows in §5/§6), never an
in-place edit. Replay's narration seed already exists (`narrate()`, §10); the
intelligent replay engine and richer performance deltas are **deferred** (aligns
with §11 semantic search and §16's deferred Experience Engine) — the Journal is
its data source, built to be mined without a rewrite.

## 20.4 Security requirements (preserved by all three)

- **Append-only integrity** — lockdown/preview/replay add no UPDATE path; all state
  changes are event rows.
- **Trust Engine is the only execution gate** — lockdown is *one more consult
  inside* `authorize()`; the preview is the gate's card; replay is read-only.
- **No tool bypass, no hidden autonomous changes** — everything still flows through
  `registry.dispatch → authorize → journal`.
- **No self-modification of safety systems** — the operating state, the journal DB,
  `app/security/**`, and the integrity module are all **self-governing paths**
  (CRITICAL to Nero's own tools, §14): Nero cannot flip her own lockdown, edit her
  own history, or disable her own gate.

## 20.5 Development order (reconciled with the existing roadmap)

1. **Action Journal** — the approved §19 PR (includes the §18 integrity safe-mode,
   which is the lockdown mechanism), and the Replay **metadata** (schema +
   `human_notes`). Most of Additions 1 & 3 land structurally here.
2. **Emergency Lockdown** — a small PR that generalizes the safe-mode flag into
   `SystemState` + the manual triggers (UI button, EN/HR voice pre-parse, keyboard)
   + the endpoints. Sits between the Journal PR and the terminal.
3. **Explain Before Execute** — ships with / just after the **confirmation UX
   (PR3)**; it is that card's structured payload.
4. **Action Replay metadata** — done in step 1; advanced replay/search is later.
5. **Advanced replay/search** — deferred (Phase 2+), reads the Journal.

## Final design principle (V1.1)

Nero's intelligence is not measured only by *"how much can Nero do?"* but by
*"how well can Nero explain, justify, and control what she does?"* A powerful AI
that feels trustworthy because **capability and accountability grow together** —
built as incremental PRs, tested, and validated on the RTX 4070. An extension of
the foundation, never a replacement.
