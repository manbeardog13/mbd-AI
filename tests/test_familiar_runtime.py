from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from presence.runtime_bridge.familiar import FamiliarRuntime
from presence.types import PresenceIntent, PresenceState


class FamiliarRuntimeTests(unittest.TestCase):
    @staticmethod
    def _payloads(command: Path) -> list[dict]:
        spool = command.parent / f"{command.stem}.d"
        return [json.loads(path.read_text(encoding="utf-8"))
                for path in sorted(spool.glob("*.cmd"))]

    @staticmethod
    def _envelope(event: str, label: str = "", confirmed: bool = False,
                  provenance: str = "") -> dict:
        return {"event": event, "label": label, "confirmed": confirmed,
                "provenance": provenance}

    def test_cold_bridge_never_launches_and_writes_semantic_state(self):
        with tempfile.TemporaryDirectory() as td:
            command = Path(td) / "command.txt"
            runtime = FamiliarRuntime(command)
            self.assertFalse(runtime.is_running())
            runtime.set_intent(PresenceIntent(PresenceState.THINKING))
            self.assertFalse(command.exists())
            runtime.start()
            runtime.set_intent(PresenceIntent(
                PresenceState.THINKING,
                metadata={"activity": "working", "label": "Codex + Claude review"},
            ))
            self.assertEqual(self._payloads(command), [self._envelope(
                "codex.started", "Codex + Claude review")])

    def test_activity_vocabulary_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            command = Path(td) / "command.txt"
            runtime = FamiliarRuntime(command)
            runtime.start()
            runtime.set_intent(PresenceIntent(
                PresenceState.ALERT,
                metadata={"activity": "shell-command", "label": "review\nnow"},
            ))
            self.assertEqual(self._payloads(command), [self._envelope(
                "user.action_required", "review now")])

    def test_critical_and_dual_agent_events_use_contract_ids(self):
        with tempfile.TemporaryDirectory() as td:
            command = Path(td) / "command.txt"
            runtime = FamiliarRuntime(command)
            runtime.start()
            runtime.set_intent(PresenceIntent(
                PresenceState.ALERT,
                metadata={"activity": "critical", "label": "Runtime unavailable"},
            ))
            self.assertEqual(self._payloads(command), [self._envelope(
                "system.critical", "Runtime unavailable")])
            runtime.set_intent(PresenceIntent(
                PresenceState.THINKING,
                metadata={"activity": "dual_agent"},
            ))
            self.assertEqual(self._payloads(command), [
                self._envelope("system.critical", "Runtime unavailable"),
                self._envelope("agents.dual_active"),
            ])

    def test_stop_dismisses_without_launching_any_process(self):
        with tempfile.TemporaryDirectory() as td:
            command = Path(td) / "command.txt"
            runtime = FamiliarRuntime(command)
            runtime.start()
            runtime.stop()
            self.assertFalse(runtime.is_running())
            self.assertEqual(self._payloads(command), [self._envelope("pet.dismiss")])

    def test_burst_events_are_durable_and_ordered(self):
        with tempfile.TemporaryDirectory() as td:
            command = Path(td) / "command.txt"
            runtime = FamiliarRuntime(command)
            runtime.start()
            for number in range(12):
                runtime.set_intent(PresenceIntent(
                    PresenceState.THINKING,
                    metadata={"label": f"event-{number:02d}"},
                ))
            payloads = self._payloads(command)
            self.assertEqual(len(payloads), 12)
            self.assertEqual(payloads[0], self._envelope("nero.thinking", "event-00"))
            self.assertEqual(payloads[-1], self._envelope("nero.thinking", "event-11"))

    def test_spool_backpressure_is_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            command = Path(td) / "command.txt"
            runtime = FamiliarRuntime(command)
            runtime.start()
            for number in range(32):
                runtime.set_intent(PresenceIntent(
                    PresenceState.THINKING, metadata={"label": str(number)}))
            with self.assertRaisesRegex(RuntimeError, "spool is full"):
                runtime.set_intent(PresenceIntent(PresenceState.THINKING))

    def test_all_supported_activity_aliases_resolve_to_v2_events(self):
        cases = {
            "claude": "claude.started",
            "claude_channel": "claude.started",
            "codex": "codex.started",
            "working": "codex.started",
            "codex_build": "codex.started",
            "heavy": "agents.dual_active",
            "dual": "agents.dual_active",
            "dual_agent": "agents.dual_active",
            "failed": "task.failed",
            "review": "user.action_required",
            "waiting": "user.action_required",
            "critical": "system.critical",
        }
        for activity, expected in cases.items():
            with self.subTest(activity=activity):
                intent = PresenceIntent(
                    PresenceState.THINKING,
                    metadata={"activity": activity},
                )
                self.assertEqual(FamiliarRuntime._command(intent), expected)

    def test_success_and_push_require_confirmation_provenance(self):
        unconfirmed = PresenceIntent(
            PresenceState.CELEBRATING,
            metadata={"activity": "success"},
        )
        self.assertEqual(FamiliarRuntime._command(unconfirmed),
                         "all.work_complete")

        missing_provenance = PresenceIntent(
            PresenceState.CELEBRATING,
            metadata={"activity": "repository_push", "confirmed": True},
        )
        self.assertEqual(FamiliarRuntime._command(missing_provenance),
                         "all.work_complete")

        succeeded = PresenceIntent(
            PresenceState.CELEBRATING,
            metadata={
                "activity": "success",
                "confirmed": True,
                "provenance": "verify_nero_familiar:exit-0",
            },
        )
        self.assertEqual(FamiliarRuntime._command(succeeded), "task.succeeded")

        pushed = PresenceIntent(
            PresenceState.IDLE,
            metadata={
                "activity": "repository_push",
                "confirmed": True,
                "provenance": "git:origin/main@abc1234",
            },
        )
        self.assertEqual(FamiliarRuntime._command(pushed), "git.push_succeeded")

        with tempfile.TemporaryDirectory() as td:
            command = Path(td) / "command.txt"
            runtime = FamiliarRuntime(command)
            runtime.start()
            runtime.set_intent(succeeded)
            self.assertEqual(self._payloads(command), [self._envelope(
                "task.succeeded", confirmed=True,
                provenance="verify_nero_familiar:exit-0")])

    def test_generic_celebration_never_claims_success(self):
        intent = PresenceIntent(PresenceState.CELEBRATING)
        self.assertEqual(FamiliarRuntime._command(intent), "all.work_complete")


if __name__ == "__main__":
    unittest.main()
