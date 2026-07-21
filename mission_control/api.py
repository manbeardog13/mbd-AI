"""FastAPI shell for the explicitly launched Mission Control control plane."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.core.contracts import RiskLevel, TaskStatus
from app.core.service import (
    GitInspectionError,
    MissionControlService,
    SafeModeError,
    ScheduleError,
    StoreConflict,
    StoreError,
)


STATIC_DIR = Path(__file__).resolve().parent / "static"


class TaskCreate(BaseModel):
    objective: str = Field(min_length=1, max_length=2000)
    priority: int = Field(default=50, ge=0, le=100)
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    write_required: bool = False


class TaskAssign(BaseModel):
    adapter_id: str
    expected_version: int = Field(ge=0)
    bounded_context: dict[str, Any] = Field(default_factory=dict)


class TaskTransition(BaseModel):
    status: TaskStatus
    expected_version: int = Field(ge=0)
    blocker: str | None = Field(default=None, max_length=2000)
    result: dict[str, Any] | None = None


class VersionedTaskAction(BaseModel):
    expected_version: int = Field(ge=0)


class ApprovalCreate(BaseModel):
    action: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    risk: RiskLevel = RiskLevel.HIGH


class ApprovalDecision(BaseModel):
    approved: bool
    note: str = Field(default="", max_length=2000)


def create_app(
    repository: str | Path,
    db_path: str | Path | None = None,
    *,
    service: MissionControlService | None = None,
) -> FastAPI:
    core = service or MissionControlService(repository, db_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        core.initialize()
        yield

    app = FastAPI(
        title="Nero Mission Control",
        version="1.0.0-m1",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.nero_core = core

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/mc/overview")
    def overview() -> dict[str, Any]:
        return _call(core.overview)

    @app.get("/api/mc/git")
    def git_state() -> dict[str, Any]:
        return _call(lambda: core.git_state(refresh_remote=False).as_dict())

    @app.post("/api/mc/git/refresh")
    def refresh_git() -> dict[str, Any]:
        return _call(lambda: core.git_state(refresh_remote=True).as_dict())

    @app.get("/api/mc/tasks")
    def tasks() -> dict[str, Any]:
        return {"tasks": [task.as_dict() for task in _call(core.tasks)]}

    @app.post("/api/mc/tasks", status_code=201)
    def queue_task(payload: TaskCreate) -> dict[str, Any]:
        task = _call(
            lambda: core.queue_task(
                objective=payload.objective,
                priority=payload.priority,
                dependencies=tuple(payload.dependencies),
                acceptance_criteria=tuple(payload.acceptance_criteria),
                write_required=payload.write_required,
            )
        )
        return {"task": task.as_dict()}

    @app.post("/api/mc/tasks/{task_id}/assign")
    def assign_task(task_id: str, payload: TaskAssign) -> dict[str, Any]:
        assignment = _call(
            lambda: core.assign_task(
                task_id,
                payload.adapter_id,
                expected_version=payload.expected_version,
                bounded_context=payload.bounded_context,
            )
        )
        return {"assignment": assignment.as_dict()}

    @app.post("/api/mc/tasks/{task_id}/transition")
    def transition_task(task_id: str, payload: TaskTransition) -> dict[str, Any]:
        task = _call(
            lambda: core.transition_task(
                task_id,
                payload.status,
                expected_version=payload.expected_version,
                blocker=payload.blocker,
                result=payload.result,
            )
        )
        return {"task": task.as_dict()}

    @app.post("/api/mc/tasks/{task_id}/retry")
    def retry_task(
        task_id: str, payload: VersionedTaskAction
    ) -> dict[str, Any]:
        return {
            "task": _call(
                lambda: core.retry_task(
                    task_id, expected_version=payload.expected_version
                )
            ).as_dict()
        }

    @app.post("/api/mc/tasks/{task_id}/lease/heartbeat")
    def heartbeat_task_lease(
        task_id: str, payload: VersionedTaskAction
    ) -> dict[str, Any]:
        lease = _call(
            lambda: core.heartbeat_task_lease(
                task_id, expected_version=payload.expected_version
            )
        )
        return {"lease": lease.as_dict()}

    @app.get("/api/mc/workers")
    def workers() -> dict[str, Any]:
        return {"workers": [worker.as_dict() for worker in _call(core.workers)]}

    @app.get("/api/mc/approvals")
    def approvals() -> dict[str, Any]:
        return {
            "approvals": [approval.as_dict() for approval in _call(core.approvals)]
        }

    @app.post("/api/mc/approvals", status_code=201)
    def request_approval(payload: ApprovalCreate) -> dict[str, Any]:
        approval = _call(
            lambda: core.request_approval(
                action=payload.action,
                summary=payload.summary,
                risk=payload.risk,
            )
        )
        return {"approval": approval.as_dict(), "executed": False}

    @app.post("/api/mc/approvals/{approval_id}/decision")
    def decide_approval(
        approval_id: str, payload: ApprovalDecision
    ) -> dict[str, Any]:
        approval = _call(
            lambda: core.decide_approval(
                approval_id, approved=payload.approved, note=payload.note
            )
        )
        return {
            "approval": approval.as_dict(),
            "executed": False,
            "message": "Milestone 1 records approval evidence but exposes no remote mutation.",
        }

    @app.get("/api/mc/events")
    def events(
        event_type: str | None = Query(default=None, max_length=200),
        task_id: str | None = Query(default=None, max_length=100),
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> dict[str, Any]:
        rows = _call(
            lambda: core.events(
                event_type=event_type, task_id=task_id, limit=limit
            )
        )
        return {"events": [event.as_dict() for event in rows]}

    @app.get("/api/mc/health")
    def health() -> dict[str, Any]:
        return _call(core.health)

    @app.get("/api/mc/policy")
    def policy() -> dict[str, Any]:
        return {
            "authority": "Nero Core",
            "workers": ["claude", "codex"],
            "remote_mutations_enabled": False,
            "remote_write_controls": "visible but disabled",
            "approval_required_for_future_remote_mutations": True,
            "host_presence_autostart": False,
            "lease_scope": "canonical Git common directory",
            "lease_heartbeat": "explicit only",
            "task_mutations": "compare-and-set versioned",
        }

    app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="mission-assets")
    return app


def _call(function):
    try:
        return function()
    except SafeModeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GitInspectionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (ScheduleError, StoreConflict, StoreError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
