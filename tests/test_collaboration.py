"""Offline tests for Nero's human-triggered External Council."""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

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
