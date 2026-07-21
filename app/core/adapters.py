"""Provider-neutral worker adapter contracts.

Milestone 1 prepares bounded packets and normalizes results. It intentionally
does not call Claude/Codex APIs and grants no remote-write capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .contracts import AgentResult, Task, TaskPacket, WorkerDescriptor, WorkerStatus


class AdapterError(ValueError):
    """Raised when a worker result cannot satisfy the normalized contract."""


class WorkerAdapter(Protocol):
    adapter_id: str
    provider: str
    display_name: str

    def descriptor(self) -> WorkerDescriptor: ...

    def prepare_packet(
        self,
        task: Task,
        *,
        lease_owner: str | None,
        lease_id: str | None = None,
        lease_fencing_token: int | None = None,
        lease_expires_at: str | None = None,
        bounded_context: Mapping[str, Any] | None = None,
    ) -> TaskPacket: ...

    def normalize_result(self, payload: Mapping[str, Any]) -> AgentResult: ...


@dataclass(slots=True)
class ManualWorkerAdapter:
    adapter_id: str
    provider: str
    display_name: str

    def descriptor(self) -> WorkerDescriptor:
        return WorkerDescriptor(
            adapter_id=self.adapter_id,
            provider=self.provider,
            display_name=self.display_name,
            status=WorkerStatus.IDLE,
            remote_writes=False,
            local_repository_access=False,
        )

    def prepare_packet(
        self,
        task: Task,
        *,
        lease_owner: str | None,
        lease_id: str | None = None,
        lease_fencing_token: int | None = None,
        lease_expires_at: str | None = None,
        bounded_context: Mapping[str, Any] | None = None,
    ) -> TaskPacket:
        context = dict(bounded_context or {})
        validate_bounded_context(context)
        return TaskPacket(
            packet_version="1",
            context_version=task.context_version,
            task_id=task.task_id,
            provider=self.provider,
            objective=task.objective,
            acceptance_criteria=task.acceptance_criteria,
            repository=task.repository,
            branch=task.branch,
            worktree=task.worktree,
            write_allowed=bool(
                task.write_required
                and lease_owner
                and lease_id
                and lease_fencing_token is not None
                and lease_expires_at
            ),
            lease_owner=lease_owner,
            lease_id=lease_id,
            lease_fencing_token=lease_fencing_token,
            lease_expires_at=lease_expires_at,
            requires_action_time_lease_validation=True,
            bounded_context=context,
        )

    def normalize_result(self, payload: Mapping[str, Any]) -> AgentResult:
        summary = str(payload.get("summary", "")).strip()
        if not summary:
            raise AdapterError("worker result requires a summary")
        return AgentResult(
            summary=summary,
            files_changed=_strings(payload.get("files_changed")),
            tests_run=_strings(payload.get("tests_run")),
            risks=_strings(payload.get("risks")),
            unresolved_questions=_strings(payload.get("unresolved_questions")),
            recommended_next_action=str(
                payload.get("recommended_next_action", "")
            ).strip(),
            raw_reference=_optional_string(payload.get("raw_reference")),
        )


class ClaudeAdapter(ManualWorkerAdapter):
    def __init__(self) -> None:
        super().__init__(
            adapter_id="claude",
            provider="Anthropic",
            display_name="Claude worker",
        )


class CodexAdapter(ManualWorkerAdapter):
    def __init__(self) -> None:
        super().__init__(
            adapter_id="codex",
            provider="OpenAI",
            display_name="Codex worker",
        )


def default_adapters() -> dict[str, ManualWorkerAdapter]:
    adapters = (ClaudeAdapter(), CodexAdapter())
    return {adapter.adapter_id: adapter for adapter in adapters}


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise AdapterError("worker result list fields must be arrays of strings")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "credentials",
    "database_dump",
    "password",
    "private_memory",
    "secret",
    "token",
    "tokens",
    "api_key",
}


def _normalized_key(value: Any) -> str:
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")


def _is_sensitive_key(value: Any) -> bool:
    key = _normalized_key(value)
    compact = key.replace("_", "")
    if key in _SENSITIVE_KEYS or compact in {
        "apikey",
        "clientsecret",
        "privatememory",
        "databasedump",
    }:
        return True
    return key.endswith(
        ("_token", "_password", "_secret", "_credentials", "_api_key")
    )


def _sensitive_paths(value: Any, path: str = "context") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            child = f"{path}.{key}"
            if _is_sensitive_key(key):
                found.append(child)
            else:
                found.extend(_sensitive_paths(nested, child))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found.extend(_sensitive_paths(nested, f"{path}[{index}]"))
    return sorted(found)


def validate_bounded_context(context: Mapping[str, Any] | None) -> None:
    sensitive = _sensitive_paths(context or {})
    if sensitive:
        raise AdapterError(
            "bounded context contains forbidden private fields at: "
            + ", ".join(sensitive)
        )
