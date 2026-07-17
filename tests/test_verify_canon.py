from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "verify" / "verify_canon.py"
SPEC = importlib.util.spec_from_file_location("nero_verify_canon_test", SCRIPT)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


class VerifyCanonTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_frontmatter_catches_bad_values_and_duplicate_ids(self):
        write(self.root, "docs/good.md",
              "---\nid: a.one\nlayer: core\nstatus: active\nowner: shared\n---\n# G\n")
        write(self.root, "docs/bad.md",
              "---\nid: a.two\nlayer: cosmic\nstatus: active\nowner: shared\n---\n# B\n")
        write(self.root, "docs/dup.md",
              "---\nid: a.one\nlayer: core\nstatus: active\nowner: shared\n---\n# D\n")
        with self.assertRaises(AssertionError) as ctx:
            M.check_frontmatter(self.root)
        msg = str(ctx.exception)
        self.assertIn("bad layer", msg)
        self.assertIn("duplicate id", msg)

    def test_supersession_needs_visible_banner(self):
        write(self.root, "docs/old.md",
              "---\nid: a.old\nlayer: archival\nstatus: archived\nowner: shared\n"
              "superseded_by: docs/new.md\n---\n# Old doc\n\nplain body text\n")
        with self.assertRaises(AssertionError):
            M.check_supersession_banners(self.root)
        write(self.root, "docs/old.md",
              "---\nid: a.old\nlayer: archival\nstatus: archived\nowner: shared\n"
              "superseded_by: docs/new.md\n---\n\n> Archived 2026-07-17: superseded.\n\n# Old doc\n")
        self.assertIn("banner", M.check_supersession_banners(self.root))

    def test_supersession_needs_superseded_by(self):
        write(self.root, "docs/old.md",
              "---\nid: a.old\nlayer: archival\nstatus: archived\nowner: shared\n---\n"
              "\n> Archived: gone.\n")
        with self.assertRaises(AssertionError) as ctx:
            M.check_supersession_banners(self.root)
        self.assertIn("superseded_by", str(ctx.exception))

    def test_links_finds_broken(self):
        write(self.root, "docs/a.md", "[ok](b.md) and [broken](missing.md)\n")
        write(self.root, "docs/b.md", "# B\n")
        with self.assertRaises(AssertionError) as ctx:
            M.check_links(self.root)
        self.assertIn("missing.md", str(ctx.exception))

    def test_adr_consistency_both_directions(self):
        write(self.root, "docs/adr/0001-first.md", "# ADR-0001\n")
        write(self.root, "docs/adr/README.md", "| [0001](0001-first.md) | First | Accepted |\n"
                                               "| [0002](0002-ghost.md) | Ghost | Proposed |\n")
        with self.assertRaises(AssertionError) as ctx:
            M.check_adr_consistency(self.root)
        self.assertIn("log rows without files", str(ctx.exception))

    def test_read_order_ignores_frontmatter_mentions(self):
        write(self.root, "docs/canon/README.md",
              "---\nid: canon.readme\nlayer: core\nstatus: active\nowner: shared\n"
              "related: docs/canon/INDEX.md\n---\n"
              "# Start\n1. [Constitution](../CONSTITUTION.md)\n"
              "2. [INDEX.md](INDEX.md)\n3. [PROJECT_BRIEF.md](../PROJECT_BRIEF.md)\n")
        self.assertIn("intact", M.check_read_order(self.root))

    def test_real_repo_is_green(self):
        for name, fn in M.CHECKS:
            fn(M.ROOT)  # raises on failure


if __name__ == "__main__":
    unittest.main()
