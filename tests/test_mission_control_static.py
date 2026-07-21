"""Static safety and accessibility checks for the Mission Control shell."""
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HTML = (ROOT / "mission_control" / "static" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "mission_control" / "static" / "app.css").read_text(encoding="utf-8")
JS = (ROOT / "mission_control" / "static" / "app.js").read_text(encoding="utf-8")


class MissionControlStaticTests(unittest.TestCase):
    def test_remote_write_control_is_visible_and_disabled(self) -> None:
        self.assertIn(">Push</button>", HTML)
        self.assertIn("disabled aria-describedby=\"remote-write-note\"", HTML)
        self.assertIn("Approval evidence alone never executes it", HTML)

    def test_accessibility_and_responsive_guards_are_present(self) -> None:
        self.assertIn("class=\"skip-link\"", HTML)
        self.assertIn("aria-live=\"polite\"", HTML)
        self.assertIn(":focus-visible", CSS)
        self.assertIn("prefers-reduced-motion: reduce", CSS)
        self.assertIn("prefers-reduced-transparency: reduce", CSS)
        self.assertIn("forced-colors: active", CSS)
        self.assertIn("@media", CSS)
        self.assertIn(".topbar, .panel-head", CSS)
        self.assertIn(".button-row { flex-wrap: wrap; }", CSS)
        self.assertIn(".event-item > * { min-width: 0; }", CSS)

    def test_external_data_uses_text_nodes_not_html_injection(self) -> None:
        self.assertNotIn("innerHTML", JS)
        self.assertIn("element.textContent = content", JS)
        self.assertIn("root.replaceChildren()", JS)

    def test_ui_does_not_expose_git_mutation_calls(self) -> None:
        for forbidden in (
            "/api/mc/git/push",
            "/api/mc/git/commit",
            "/api/mc/git/merge",
            "/api/mc/git/pull",
            "/api/mc/git/rebase",
        ):
            self.assertNotIn(forbidden, JS)

    def test_async_form_handlers_do_not_reuse_event_current_target(self) -> None:
        self.assertNotIn("event.currentTarget.reset()", JS)


if __name__ == "__main__":
    unittest.main()
