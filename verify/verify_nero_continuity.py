#!/usr/bin/env python3
"""Deterministic verifier for the Nero cross-host continuity ledger.

Follows the repository's verify/verify_*.py convention: it proves the subsystem
on the real machine and prints a machine-readable JSON result. It drives the
PUBLIC CLI as a cold subprocess (the exact path the Claude/Codex adapters use),
plus a 10k-event performance benchmark, plus a protected-file byte-identity
proof.

Exit 0 = every gate passed. Non-zero = a gate failed (details in JSON).

This verifier is Claude's BUILDER-lane evidence. It uses a simulated client for
both hosts; it is NOT proof of live cross-host continuity, which requires a
separate real Codex session. See the anti-false-completion rule in the ADR.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CTL = REPO / "continuity" / "continuityctl.py"
PY = sys.executable

GATED_PROTECTED = (
    "data/memory.db",
    "global_claude_md",
    "codex_agents_md",
    "codex_config_toml",
)
OBSERVED_ONLY = ()
COLD_SAMPLE_COUNT = 120


def cli(db, *args, stdin=None, host="claude", source_host=None, timeout=60):
    cmd = [PY, str(CTL), "--db", str(db), "--host", host]
    if source_host:
        cmd += ["--source-host", source_host]
    cmd += list(args)
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, input=(stdin.encode("utf-8") if stdin is not None else None),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    dt = (time.perf_counter() - t0) * 1000.0
    try:
        out = json.loads(proc.stdout.decode("utf-8"))
    except Exception:
        out = {"_raw_stdout": proc.stdout.decode("utf-8", "replace"),
               "_stderr": proc.stderr.decode("utf-8", "replace")}
    return proc.returncode, out, dt


def _load_module():
    spec = importlib.util.spec_from_file_location("continuityctl", CTL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha256_file(path: Path):
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _main_worktree_root(repo: Path) -> Path:
    """Return Git's primary worktree; source archives fall back to ``repo``.

    A linked worktree contains a ``.git`` *file*. The standalone Nero database
    belongs to the primary checkout, so resolving it relative to the linked
    verifier checkout would turn the protection gate into a vacuous check.
    """
    repo = repo.resolve()
    marker = repo / ".git"
    if marker.is_dir() or not marker.exists():
        return repo
    if not marker.is_file():
        raise RuntimeError(f"unsupported Git marker: {marker}")

    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "worktree", "list", "--porcelain", "-z"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"cannot resolve primary Git worktree: {exc}") from exc
    if proc.returncode != 0:
        error = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"cannot resolve primary Git worktree: {error}")
    fields = proc.stdout.split(b"\0")
    if not fields or not fields[0].startswith(b"worktree "):
        raise RuntimeError("cannot resolve primary Git worktree: malformed output")
    raw_primary = fields[0][len(b"worktree "):]
    if not raw_primary:
        raise RuntimeError("cannot resolve primary Git worktree: empty path")
    primary = Path(os.fsdecode(raw_primary)).resolve()
    return primary


def _protected_paths(
    repo: Path = REPO,
    *,
    home: Path | None = None,
) -> tuple[Path, dict[str, Path]]:
    primary = _main_worktree_root(repo)
    home = (home or Path.home()).resolve()
    return primary, {
        "data/memory.db": primary / "data" / "memory.db",
        "global_claude_md": home / ".claude" / "CLAUDE.md",
        "codex_agents_md": home / ".codex" / "AGENTS.md",
        "codex_config_toml": home / ".codex" / "config.toml",
    }


def _snapshot_files(paths: dict[str, Path]) -> dict[str, str | None]:
    return {name: _sha256_file(path) for name, path in paths.items()}


def _compare_protected(
    before: dict[str, str | None],
    after: dict[str, str | None],
    gated: tuple[str, ...] = GATED_PROTECTED,
) -> dict[str, object]:
    changed = sorted(name for name in gated if before.get(name) != after.get(name))
    absent = sorted(
        name for name in gated if before.get(name) is None or after.get(name) is None
    )
    observed_only_changed = sorted(
        name
        for name in OBSERVED_ONLY
        if before.get(name) != after.get(name)
    )
    return {
        "ok": not changed and not absent,
        "changed": changed,
        "absent": absent,
        "absent_unchanged": sorted(
            name
            for name in gated
            if before.get(name) is None and after.get(name) is None
        ),
        "observed_only_changed": observed_only_changed,
    }


def _cold_cli_gates(
    perf: dict[str, float],
    read_codes: list[int],
    write_codes: list[int],
    read_semantics: list[bool],
    write_semantics: list[bool],
) -> dict[str, bool]:
    read_succeeded = (
        len(read_codes) == COLD_SAMPLE_COUNT
        and len(read_semantics) == COLD_SAMPLE_COUNT
        and all(code == 0 for code in read_codes)
        and all(read_semantics)
    )
    write_succeeded = (
        len(write_codes) == COLD_SAMPLE_COUNT
        and len(write_semantics) == COLD_SAMPLE_COUNT
        and all(code == 0 for code in write_codes)
        and all(write_semantics)
    )
    return {
        "cold_cli_read_samples_succeeded": read_succeeded,
        "cold_cli_write_samples_succeeded": write_succeeded,
        "cold_cli_read_p95_within_250ms": (
            read_succeeded and perf["read_cold_p95"] <= 250
        ),
        "cold_cli_write_p95_within_250ms": (
            write_succeeded and perf["write_cold_p95"] <= 250
        ),
    }


def _cold_read_sample_ok(code: int, output: object, topic: str) -> bool:
    if not isinstance(output, dict):
        return False
    rows = output.get("results")
    return bool(
        code == 0
        and output.get("result") == "OK"
        and output.get("action") == "recall"
        and isinstance(rows, list)
        and any(isinstance(row, dict) and row.get("topic") == topic for row in rows)
    )


def _cold_write_sample_ok(code: int, output: object) -> bool:
    if not isinstance(output, dict):
        return False
    return bool(
        code == 0
        and output.get("result") == "OK"
        and output.get("action") == "capture"
        and isinstance(output.get("event_id"), str)
        and output.get("event_id")
        and isinstance(output.get("event_hash"), str)
        and output.get("event_hash")
    )


def build_corpus(mod, db_path, n):
    """Insert `n` valid, chained events directly (setup only, not the measured path)."""
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA synchronous=OFF")  # setup speed only; measured ops use FULL
    conn.execute("BEGIN IMMEDIATE")
    prev = conn.execute(
        "SELECT event_hash FROM events ORDER BY global_sequence DESC LIMIT 1").fetchone()
    prev_hash = prev["event_hash"] if prev else mod.GENESIS
    base = int(conn.execute(
        "SELECT COALESCE(MAX(global_sequence),0) m FROM events").fetchone()["m"])
    import uuid as _uuid
    for i in range(1, n + 1):
        seq = base + i
        payload = f"bounded corpus event {seq} topic-{seq % 500}"
        content = mod.sha256_text(payload)
        ev = {
            "event_id": _uuid.uuid4().hex, "schema_version": 1, "global_sequence": seq,
            "created_at_utc": mod.fmt_utc(mod.utc_now()),
            "recorded_at_utc": mod.fmt_utc(mod.utc_now()), "actor": "toni",
            "event_type": "capture", "scope": "handoff", "source_host_claim": "codex",
            "capture_method": "cli_explicit", "session_id": None, "topic": f"topic-{seq}",
            "content_sha256": content, "privacy_class": "user_shared",
            "consent_basis": "explicit_handoff", "expires_at_utc": None,
            "supersedes_event_id": None, "idempotency_key": f"corpus-{seq}",
            "previous_hash": prev_hash, "metadata": None,
        }
        ev["event_hash"] = mod.event_hash_of(ev)
        conn.execute(
            """INSERT INTO events
               (event_id,schema_version,global_sequence,created_at_utc,recorded_at_utc,actor,
                event_type,scope,source_host_claim,capture_method,session_id,topic,payload,
                content_sha256,privacy_class,consent_basis,expires_at_utc,status,
                supersedes_event_id,idempotency_key,previous_hash,event_hash,metadata)
               VALUES (:event_id,:schema_version,:global_sequence,:created_at_utc,:recorded_at_utc,
                :actor,:event_type,:scope,:source_host_claim,:capture_method,:session_id,:topic,
                :payload,:content_sha256,:privacy_class,:consent_basis,:expires_at_utc,'active',
                :supersedes_event_id,:idempotency_key,:previous_hash,:event_hash,:metadata)""",
            {**ev, "payload": payload})
        prev_hash = ev["event_hash"]
    conn.execute("INSERT INTO schema_meta(key,value) VALUES('event_count',?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(base + n),))
    conn.execute("INSERT INTO schema_meta(key,value) VALUES('head_hash',?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (prev_hash,))
    conn.execute("COMMIT")
    conn.close()


def pct(values, p):
    if not values:
        return None
    return round(statistics.quantiles(values, n=100)[p - 1], 2) if len(values) > 1 else round(values[0], 2)


def main():
    results = {"gates": {}, "details": {}}
    try:
        primary_root, protected_paths = _protected_paths()
    except RuntimeError as exc:
        results["gates"]["protected_paths_resolved"] = False
        results["details"]["protected_files"] = {
            "resolution_error": str(exc),
        }
        results["all_pass"] = False
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 1
    results["gates"]["protected_paths_resolved"] = True
    try:
        protected_before = _snapshot_files(protected_paths)
    except OSError as exc:
        results["gates"]["protected_files_byte_identical"] = False
        results["details"]["protected_files"] = {
            "primary_worktree_root": str(primary_root),
            "paths": {name: str(path) for name, path in protected_paths.items()},
            "gated": list(GATED_PROTECTED),
            "snapshot_error": str(exc),
            "snapshot_stage": "before",
        }
        results["all_pass"] = False
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 1
    tmp = tempfile.mkdtemp(prefix="verify_continuity_")
    try:
        mod = _load_module()

        # --- Gate 1: functional cross-host scenario (SIMULATED client) ----------
        db = os.path.join(tmp, "func.db")
        c, o, _ = cli(db, "init")
        assert c == 0, o
        # Codex-claimed write of a random-looking nonce under a challenge id.
        nonce = "a3f19c7e5b0d84621fe0ccab19d77f42d8e6"
        c, o, _ = cli(db, "capture", "--scope", "handoff", "--topic", "CHAL-VERIFY",
                      "--idempotency-key", "vk1", stdin=nonce, host="codex", source_host="codex")
        assert c == 0, o
        ev_id, ev_hash = o["event_id"], o["event_hash"]
        # Claude-claimed read returns the EXACT nonce + provenance.
        c, o, _ = cli(db, "recall", "--topic", "CHAL-VERIFY", stdin="", host="claude")
        got = o["results"][0]
        func_ok = (c == 0 and got["payload"] == nonce and got["source_host_claim"] == "codex"
                   and got["event_id"] == ev_id and got["event_hash"] == ev_hash)
        # Unknown challenge -> NOT_FOUND
        c2, o2, _ = cli(db, "recall", "--topic", "NEVER-WRITTEN", stdin="", host="claude")
        unknown_ok = (c2 == 4 and o2["result"] == "NOT_FOUND")
        # Guess trap: math beside a nonce -> retrieval returns the NONCE, not "5".
        c, o, _ = cli(db, "capture", "--topic", "TRAP", "--idempotency-key", "tk1",
                      stdin="2 + 3 = 5 and the secret is 771af0c2eb", host="codex", source_host="codex")
        c, o, _ = cli(db, "recall", "--topic", "TRAP", stdin="", host="claude")
        trap_ok = "771af0c2eb" in o["results"][0]["payload"]
        # Correction preserves the old as superseded.
        c, o, _ = cli(db, "correct", "--supersedes", ev_id, stdin="corrected-nonce",
                      host="claude", source_host="claude")
        c, oo, _ = cli(db, "show", "--event", ev_id, stdin="")
        corr_ok = (c == 0 and oo["event"]["status"] == "superseded")
        results["gates"]["functional_roundtrip_simulated"] = bool(
            func_ok and unknown_ok and trap_ok and corr_ok)
        results["details"]["functional"] = {
            "exact_recall": func_ok, "unknown_not_found": unknown_ok,
            "guess_trap": trap_ok, "correction_supersedes": corr_ok}

        # --- Gate 2: integrity fail-closed blocks recall of a tampered record ---
        idb = os.path.join(tmp, "integ.db")
        cli(idb, "init")
        c, o, _ = cli(idb, "capture", "--topic", "INTEG", "--idempotency-key", "ig1",
                      stdin="authentic value", host="codex", source_host="codex")
        integ_id = o["event_id"]
        con = sqlite3.connect(idb)
        con.execute("UPDATE events SET payload='TAMPERED' WHERE event_id=?", (integ_id,))
        con.commit(); con.close()
        c, o, _ = cli(idb, "recall", "--topic", "INTEG", stdin="", host="claude")
        recall_blocked = (c == 5 and o["result"] == "INTEGRITY_FAILED")
        # And a row DELETION (structural tamper) fails closed for ANY recall.
        ddb = os.path.join(tmp, "del.db")
        cli(ddb, "init")
        for i in range(3):
            cli(ddb, "capture", "--topic", f"D{i}", "--idempotency-key", f"dk{i}",
                stdin=f"v{i}", host="codex", source_host="codex")
        con = sqlite3.connect(ddb)
        con.execute("DELETE FROM events WHERE topic='D1'")
        con.commit(); con.close()
        c, o, _ = cli(ddb, "recall", "--topic", "D0", stdin="", host="claude")
        deletion_blocked = (c == 5 and o["result"] == "INTEGRITY_FAILED")
        results["gates"]["integrity_blocks_recall"] = recall_blocked and deletion_blocked
        results["details"]["integrity"] = {
            "tampered_record_recall_blocked": recall_blocked,
            "deletion_blocks_any_recall": deletion_blocked}

        # --- Gate 3: unavailable path fails closed (basis of disabled control) --
        c, o, _ = cli(os.path.join(tmp, "does_not_exist.db"), "recall", "--topic", "x", stdin="")
        results["gates"]["unavailable_fail_closed"] = (c == 3 and o["result"] == "UNAVAILABLE")

        # --- Gate 4: 10k-event performance benchmark ---------------------------
        perf_db = os.path.join(tmp, "perf.db")
        c, _, _ = cli(perf_db, "init")
        build_corpus(mod, perf_db, 10000)
        c, o, _ = cli(perf_db, "verify", stdin="")
        corpus_ok = (c == 0 and o["report"]["event_count"] == 10000)
        # cold-CLI read samples
        read_ms, write_ms = [], []
        read_codes, write_codes = [], []
        read_semantics, write_semantics = [], []
        for i in range(COLD_SAMPLE_COUNT):
            seq = 1 + (i * 83) % 10000
            topic = f"topic-{seq}"
            code, output, dt = cli(
                perf_db, "recall", "--topic", topic, stdin=""
            )
            read_codes.append(code)
            read_semantics.append(_cold_read_sample_ok(code, output, topic))
            read_ms.append(dt)
        for i in range(COLD_SAMPLE_COUNT):
            code, output, dt = cli(
                perf_db,
                "capture",
                "--topic",
                f"perf-w-{i}",
                "--idempotency-key",
                f"pw-{i}",
                stdin=f"perf write {i}",
            )
            write_codes.append(code)
            write_semantics.append(_cold_write_sample_ok(code, output))
            write_ms.append(dt)
        # Interpreter+import start floor (same interpreter, no DB work).
        start_samples = []
        for _ in range(30):
            t0 = time.perf_counter()
            subprocess.run([PY, "-c", "pass"], stdout=subprocess.DEVNULL)
            start_samples.append((time.perf_counter() - t0) * 1000.0)
        interp = statistics.median(start_samples)

        # TRUE continuity overhead, measured IN-PROCESS (no spawn, no AV scan):
        # this isolates the ledger's own read/write cost from process-launch tail.
        policy = mod.load_policy(mod.DEFAULT_POLICY_PATH)
        ip_read, ip_write = [], []
        for i in range(400):
            seq = 1 + (i * 83) % 10000
            t0 = time.perf_counter()
            conn = mod.connect(perf_db, policy)
            mod.integrity_preflight(conn)
            conn.execute("SELECT * FROM events WHERE topic=? AND status='active'",
                         (f"topic-{seq}",)).fetchall()
            conn.close()
            ip_read.append((time.perf_counter() - t0) * 1000.0)
        for i in range(400):
            t0 = time.perf_counter()
            conn = mod.connect(perf_db, policy)
            with mod.write_txn(conn, policy):
                mod.set_meta(conn, "_perf_probe", str(i))  # real durable fsync write
            conn.close()
            ip_write.append((time.perf_counter() - t0) * 1000.0)

        perf = {
            "corpus_events": 10000,
            "interpreter_start_median_ms": round(interp, 2),
            "read_cold_p50": pct(read_ms, 50), "read_cold_p95": pct(read_ms, 95),
            "read_cold_p99": pct(read_ms, 99),
            "write_cold_p50": pct(write_ms, 50), "write_cold_p95": pct(write_ms, 95),
            "write_cold_p99": pct(write_ms, 99),
            "read_inproc_p50": pct(ip_read, 50), "read_inproc_p95": pct(ip_read, 95),
            "read_inproc_p99": pct(ip_read, 99),
            "write_inproc_p50": pct(ip_write, 50), "write_inproc_p95": pct(ip_write, 95),
            "write_inproc_p99": pct(ip_write, 99),
        }
        results["details"]["performance"] = perf
        results["gates"]["corpus_10k_verifies"] = corpus_ok
        # The ledger's own in-process overhead gates at p95/p99. The real adapter
        # path also gates cold-CLI p95 and semantic success; cold p99 remains
        # contextual because Python process spawn and host AV dominate its tail.
        results["gates"]["read_p95_within_250ms"] = perf["read_inproc_p95"] <= 250
        results["gates"]["read_p99_within_500ms"] = perf["read_inproc_p99"] <= 500
        results["gates"]["write_p95_within_250ms"] = perf["write_inproc_p95"] <= 250
        results["gates"]["write_p99_within_500ms"] = perf["write_inproc_p99"] <= 500
        results["gates"].update(
            _cold_cli_gates(
                perf,
                read_codes,
                write_codes,
                read_semantics,
                write_semantics,
            )
        )
        results["details"]["cold_cli_context"] = {
            "p95_gating": True,
            "p99_gating": False,
            "expected_samples_per_operation": COLD_SAMPLE_COUNT,
            "read_sample_count": len(read_codes),
            "read_exit_zero_count": sum(code == 0 for code in read_codes),
            "read_semantic_success_count": sum(read_semantics),
            "read_success_count": sum(
                code == 0 and semantic
                for code, semantic in zip(read_codes, read_semantics)
            ),
            "write_sample_count": len(write_codes),
            "write_exit_zero_count": sum(code == 0 for code in write_codes),
            "write_semantic_success_count": sum(write_semantics),
            "write_success_count": sum(
                code == 0 and semantic
                for code, semantic in zip(write_codes, write_semantics)
            ),
            "read_p99_ms": perf["read_cold_p99"],
            "write_p99_ms": perf["write_cold_p99"],
            "note": "Cold-CLI p95 gates the adapter path; p99 remains contextual because Python startup and host AV dominate its tail.",
        }

        # --- Gate 5: protected files have identical start/end bytes ------------
        try:
            protected_after = _snapshot_files(protected_paths)
        except OSError as exc:
            results["gates"]["protected_files_byte_identical"] = False
            results["details"]["protected_files"] = {
                "primary_worktree_root": str(primary_root),
                "paths": {
                    name: str(path) for name, path in protected_paths.items()
                },
                "gated": list(GATED_PROTECTED),
                "before": protected_before,
                "snapshot_error": str(exc),
                "snapshot_stage": "after",
            }
            results["all_pass"] = False
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 1
        comparison = _compare_protected(protected_before, protected_after)
        results["gates"]["protected_files_byte_identical"] = bool(
            comparison["ok"]
        )
        results["details"]["protected_files"] = {
            "primary_worktree_root": str(primary_root),
            "paths": {name: str(path) for name, path in protected_paths.items()},
            "gated": list(GATED_PROTECTED),
            "observed_only": list(OBSERVED_ONLY),
            "before": protected_before,
            "after": protected_after,
            **comparison,
            "claim": "At the start and end of the gated workload, each required gated file was present and its SHA-256 byte content was identical. This does not prove the file was never touched between snapshots, and does not cover metadata or SQLite sidecar files.",
        }

        results["all_pass"] = all(results["gates"].values())
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0 if results["all_pass"] else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
