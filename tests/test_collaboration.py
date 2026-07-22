"""Offline tests for Nero's human-triggered External Council."""
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import collaboration


@dataclass
class Config:
    collaboration_enabled: bool = True
    collaboration_openai_api_key: str = "openai-test-key"
    collaboration_openai_model: str = "openai-test-model"
    collaboration_anthropic_api_key: str = "anthropic-test-key"
    collaboration_anthropic_model: str = "anthropic-test-model"
    collaboration_timeout_seconds: float = 5.0
    collaboration_max_output_tokens: int = 200
    collaboration_max_handoff_chars: int = 600


def _async_test(coro):
    return asyncio.run(coro)


def test_council_is_off_by_default_and_rejects_runs():
    cfg = Config(collaboration_enabled=False)
    state = collaboration.status(cfg)
    assert state["enabled"] is False and state["configured"] is False
    try:
        _async_test(collaboration.coordinate(cfg, "Design a private memory system."))
    except collaboration.CollaborationConfigurationError:
        pass
    else:
        raise AssertionError("Disabled council accepted a run")


def test_full_council_hands_off_in_order_without_network():
    calls: list[httpx.Request] = []

    def responder(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.host == "api.openai.com":
            count = sum(1 for call in calls if call.url.host == "api.openai.com")
            return httpx.Response(200, json={"id": f"openai-{count}", "output_text": f"OpenAI handoff {count}"})
        return httpx.Response(200, json={"id": "claude-1", "content": [{"type": "text", "text": "Claude handoff"}]})

    async def run():
        transport = httpx.MockTransport(responder)
        async with httpx.AsyncClient(transport=transport) as client:
            return await collaboration.coordinate(
                Config(), "Design Nero's memory bridge.", client=client
            )

    result = _async_test(run())
    assert [turn["stage"] for turn in result["turns"]] == ["architect", "builder", "reviewer"]
    assert [call.url.host for call in calls] == ["api.openai.com", "api.anthropic.com", "api.openai.com"]
    assert "Architect brief" in result["transmissions"][1]["project_content"]
    assert "Builder response" in result["transmissions"][2]["project_content"]


def test_direct_architect_sends_only_explicit_inline_content():
    seen: dict = {}

    def responder(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "claude-architect-1",
                "content": [{"type": "text", "text": "Verified brief"}],
            },
        )

    async def run():
        attachment = collaboration.Attachment("plan.md", "text/markdown", b"# Explicit plan")
        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as client:
            return await collaboration.dispatch_architect(
                Config(collaboration_openai_api_key="", collaboration_openai_model=""),
                "Audit this plan.",
                [attachment],
                client=client,
            )

    result = _async_test(run())
    assert result["text"] == "Verified brief"
    assert result["attachments"][0]["name"] == "plan.md"
    content = seen["messages"][0]["content"]
    assert "Audit this plan." in content[0]["text"]
    assert "# Explicit plan" in content[1]["text"]
    assert seen["model"] == "anthropic-test-model"


def test_unsupported_attachment_is_rejected_before_network():
    calls = 0

    def responder(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500)

    async def run():
        attachment = collaboration.Attachment("archive.zip", "application/zip", b"PK\x03\x04")
        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as client:
            return await collaboration.dispatch_architect(
                Config(), "Inspect this archive.", [attachment], client=client
            )

    try:
        _async_test(run())
    except collaboration.CollaborationAttachmentError as exc:
        assert exc.status_code == 415
    else:
        raise AssertionError("Unsupported attachment reached the provider")
    assert calls == 0


def test_http_dispatch_parses_explicit_multipart_without_network():
    from app import main

    captured: dict = {}

    async def fake_dispatch(cfg, task, attachments):
        captured["task"] = task
        captured["attachments"] = attachments
        return {
            "message": "Claude Architect completed the dispatch.",
            "text": "Route-level response",
            "model": cfg.collaboration_anthropic_model,
        }

    with (
        patch.object(main, "load_config", return_value=Config()),
        patch.object(collaboration, "dispatch_architect", side_effect=fake_dispatch),
    ):
        response = TestClient(main.app).post(
            "/api/council/dispatch",
            data={"prompt": "Audit this plan.", "target": "claude", "role": "architect"},
            files={"files": ("plan.md", b"# Explicit plan", "text/markdown")},
        )

    assert response.status_code == 200
    assert response.json()["text"] == "Route-level response"
    assert captured["task"] == "Audit this plan."
    assert captured["attachments"][0].name == "plan.md"
    assert captured["attachments"][0].data == b"# Explicit plan"


def test_empty_and_oversized_tasks_are_rejected():
    for task in ("", "x" * (collaboration.MAX_TASK_CHARS + 1)):
        try:
            collaboration._validate(task, "plan-build-review")
        except collaboration.CollaborationError:
            pass
        else:
            raise AssertionError("Invalid task was accepted")


def _run() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print(f"  OK {fn.__name__}")
    print(f"\n  {len(tests)} collaboration tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run())
