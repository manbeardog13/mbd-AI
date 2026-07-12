"""Unit tests for the fs.read capability — jailed, bounded, read-only.

Run directly:  python tests/test_fs_read.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.capabilities import Context, Registry
from app.capabilities.builtin.fs_read import FsRead
from app.capabilities.builtin import register_builtins

CAP = FsRead()


def _jail():
    d = Path(tempfile.mkdtemp())
    return d, Context(allowed_dirs=[str(d)])


def test_reads_a_file_in_the_jail():
    d, ctx = _jail()
    (d / "hello.txt").write_text("hi Toni", encoding="utf-8")
    r = CAP.execute({"path": "hello.txt"}, ctx)
    assert r.ok and "hi Toni" in r.output and r.data["bytes"] == 7


def test_missing_file_is_a_clean_failure():
    d, ctx = _jail()
    r = CAP.execute({"path": "nope.txt"}, ctx)
    assert not r.ok and "No such file" in r.output


def test_directory_is_rejected():
    d, ctx = _jail()
    (d / "sub").mkdir()
    r = CAP.execute({"path": "sub"}, ctx)
    assert not r.ok and "directory" in r.output


def test_missing_path_arg():
    _, ctx = _jail()
    assert not CAP.execute({}, ctx).ok


def test_binary_is_refused():
    d, ctx = _jail()
    (d / "blob.bin").write_bytes(b"\x00\x01\x02binary\x00")
    r = CAP.execute({"path": "blob.bin"}, ctx)
    assert not r.ok and "binary" in r.output


def test_large_file_is_truncated():
    d, ctx = _jail()
    (d / "big.txt").write_text("x" * 300_000, encoding="utf-8")
    r = CAP.execute({"path": "big.txt"}, ctx)
    assert r.ok and r.data["truncated"] and "truncated" in r.output


def test_gate_denies_out_of_jail_read_without_confirm():
    # Through the registry: a path escaping the jail is HIGH; no confirm ⇒ denied,
    # and execute() never runs (we'd otherwise leak /etc/passwd).
    d, _ = _jail()
    reg = Registry()
    reg.register(CAP)
    ctx = Context(allowed_dirs=[str(d)], confirm=None)
    r = reg.dispatch("fs.read", {"path": "/etc/passwd"}, ctx)
    assert not r.ok and r.data.get("denied") and r.data.get("risk") == "high"


def test_in_jail_read_runs_freely_through_registry():
    d, _ = _jail()
    (d / "note.md").write_text("safe content", encoding="utf-8")
    reg = Registry()
    reg.register(CAP)
    r = reg.dispatch("fs.read", {"path": "note.md"}, Context(allowed_dirs=[str(d)]))
    assert r.ok and "safe content" in r.output


def test_registered_as_a_builtin():
    reg = Registry()
    register_builtins(reg)
    assert reg.get("fs.read") is not None and reg.get("git.status") is not None


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} fs.read tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
