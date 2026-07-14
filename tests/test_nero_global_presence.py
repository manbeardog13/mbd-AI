"""Contract tests for zero-start, hosted-only Nero Host Presence."""
from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
VERIFY_PATH = ROOT / "verify" / "verify_nero_global_presence.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_nero_global_presence", VERIFY_PATH)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load verifier from {VERIFY_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NeroGlobalPresenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = _load_verifier()

    def _canonical(self) -> str:
        return self.verifier.extract_capsule(
            self.verifier.CAPSULE_PATH.read_text(encoding="utf-8"),
            source="canonical",
        )

    def _audit_temp_user_state(
        self,
        root: Path,
        *,
        global_text: str | None = None,
        marketplace_text: str = '{"plugins": []}',
        override_text: str | None = None,
        plugin_name: str | None = None,
        config_text: str = "",
    ):
        agents = root / "AGENTS.md"
        agents.write_text(global_text or self._canonical(), encoding="utf-8")
        override = root / "AGENTS.override.md"
        if override_text is not None:
            override.write_text(override_text, encoding="utf-8")
        marketplace = root / "marketplace.json"
        marketplace.write_text(marketplace_text, encoding="utf-8")
        plugins = root / "plugins"
        plugins.mkdir()
        if plugin_name:
            (plugins / plugin_name).mkdir()
        config = root / "config.toml"
        config.write_text(config_text, encoding="utf-8")
        return self.verifier.audit_user_state(
            agents,
            override_path=override,
            marketplace_paths=(marketplace,),
            plugin_roots=(plugins,),
            codex_config_path=config,
        )

    def test_project_audit_passes(self) -> None:
        checks = self.verifier.audit_project()
        self.assertEqual(
            checks[-1],
            "legacy local documentation: prominently quarantined",
        )

    def test_capsule_extraction_is_strict(self) -> None:
        canonical = self._canonical()
        self.assertTrue(canonical.startswith(self.verifier.CAPSULE_START))
        self.assertTrue(canonical.endswith(self.verifier.CAPSULE_END))

    def test_capsule_rejects_duplicate_or_reversed_markers(self) -> None:
        duplicated = (
            f"{self.verifier.CAPSULE_START}\n{self.verifier.CAPSULE_END}\n"
            f"{self.verifier.CAPSULE_START}\n{self.verifier.CAPSULE_END}"
        )
        reversed_markers = f"{self.verifier.CAPSULE_END}\n{self.verifier.CAPSULE_START}"
        for text in (duplicated, reversed_markers):
            with self.subTest(text=text):
                with self.assertRaises(self.verifier.AuditFailure):
                    self.verifier.extract_capsule(text, source="invalid")

    def test_hooks_and_closed_config_are_exact(self) -> None:
        hooks = json.loads((ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        config = json.loads((ROOT / ".codex" / "nero-host.json").read_text(encoding="utf-8"))
        self.assertEqual(hooks, {"hooks": {}})
        self.assertEqual(config, self.verifier.EXPECTED_HOST_CONFIG)

    def test_fail_closed_and_personality_clauses_are_canonical(self) -> None:
        capsule = self._canonical()
        self.assertIn("warm, curious, sharp, calm, mature, and protective", capsule)
        self.assertIn("Fail closed to ordinary hosted Codex behavior", capsule)
        self.assertIn("Never fall back to local speech synthesis", capsule)

    def test_user_state_exact_match_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            checks = self._audit_temp_user_state(Path(directory))
        self.assertEqual(len(checks), 2)

    def test_user_state_rejects_capsule_mismatch_and_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(self.verifier.AuditFailure, "differs"):
                self._audit_temp_user_state(root, global_text=self._canonical().replace("warm", "cold", 1))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(self.verifier.AuditFailure, "shadows"):
                self._audit_temp_user_state(Path(directory), override_text="# override")

    def test_user_state_rejects_malformed_marketplace(self) -> None:
        for malformed in ('["not-an-object"]', '{"plugins": {}}', '{bad json'):
            with self.subTest(malformed=malformed), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(self.verifier.AuditFailure):
                    self._audit_temp_user_state(Path(directory), marketplace_text=malformed)

    def test_user_state_rejects_plugin_aliases_and_config_registration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(self.verifier.AuditFailure, "plugin path"):
                self._audit_temp_user_state(Path(directory), plugin_name="Nero_Host")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(self.verifier.AuditFailure, "registered"):
                self._audit_temp_user_state(Path(directory), config_text='name = "NERO_HOST"')

    def test_codex_home_resolution_honors_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"CODEX_HOME": directory}
        ):
            self.assertEqual(self.verifier._active_codex_home(), Path(directory))


if __name__ == "__main__":
    unittest.main()
