"""FastAPI shell for the explicitly launched Mission Control control plane."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.core.contracts import RiskLevel, TaskStatus
from app.core.service import (
    GitInspectionError,
    MissionControlService,
    SafeModeError,
    ScheduleError,
    StoreConflict,
    StoreError,
    VerificationPolicyError,
)


STATIC_DIR = Path(__file__).resolve().parent / "static"


class StrictRequest(BaseModel):
    """Reject fields outside the fixed Mission Control request contract."""

    model_config = ConfigDict(extra="forbid")


class TaskCreate(StrictRequest):
    objective: str = Field(min_length=1, max_length=2000)
    priority: int = Field(default=50, ge=0, le=100)
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    write_required: bool = False
    verification_profile_id: str | None = Field(
        default=None, min_length=1, max_length=200
    )


class TaskAssign(StrictRequest):
    adapter_id: str = Field(min_length=1, max_length=100)
    expected_version: int = Field(ge=0)
    bounded_context: dict[str, Any] = Field(default_factory=dict)


class TaskTransition(StrictRequest):
    status: TaskStatus
    expected_version: int = Field(ge=0)
    blocker: str | None = Field(default=None, max_length=2000)
    result: dict[str, Any] | None = None


class VersionedTaskAction(StrictRequest):
    expected_version: int = Field(ge=0)


class VerificationPolicy(StrictRequest):
    profile_id: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=0)


class ApprovalCreate(StrictRequest):
    action: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=2000)
    risk: RiskLevel = RiskLevel.HIGH


class ApprovalDecision(StrictRequest):
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
        version="2.0.0-m2",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.nero_core = core

    @app.middleware("http")
    async def loopback_browser_boundary(request: Request, call_next):
        """Reject DNS-rebinding hosts and hostile browser mutation origins."""
        request_host, request_port = _authority(request.headers.get("host"))
        if request_host not in _LOOPBACK_HOSTS:
            return JSONResponse(
                status_code=400,
                content={"detail": "Mission Control accepts loopback Host headers only"},
            )
        if (
            request.url.path.startswith("/api/mc/")
            and request.headers.get("x-nero-local") != "1"
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Mission Control API requires the local request header"
                },
            )
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin:
                try:
                    parsed = urlsplit(origin)
                    origin_host = (parsed.hostname or "").lower()
                    origin_port = parsed.port
                except ValueError:
                    origin_host = ""
                    origin_port = None
                    parsed = None
                if (
                    parsed is None
                    or parsed.scheme != "http"
                    or origin_host not in _LOOPBACK_HOSTS
                    or origin_host != request_host
                    or (origin_port or 80) != (request_port or 80)
                    or request.headers.get("x-nero-local") != "1"
                ):
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": (
                                "Mutation rejected by the local browser-origin boundary"
                            )
                        },
                    )
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "style-src 'self'; script-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

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

    @app.post("/api/mc/reconcile")
    def reconcile() -> dict[str, Any]:
        return _call(core.reconcile)

    @app.post("/api/mc/tasks", status_code=201)
    def queue_task(payload: TaskCreate) -> dict[str, Any]:
        task = _call(
            lambda: core.queue_task(
                objective=payload.objective,
                priority=payload.priority,
                dependencies=tuple(payload.dependencies),
                acceptance_criteria=tuple(payload.acceptance_criteria),
                write_required=payload.write_required,
                verification_profile_id=payload.verification_profile_id,
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

    @app.get("/api/mc/verification/profiles")
    def verification_profiles() -> dict[str, Any]:
        catalog = _call(core.verification_profiles)
        return _record(catalog)

    @app.get("/api/mc/verification/runs")
    def verification_runs(
        task_id: str | None = Query(default=None, max_length=100),
        status: str | None = Query(default=None, max_length=100),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, Any]:
        runs = _call(
            lambda: core.verification_runs(
                task_id=task_id,
                status=status,
                limit=limit,
            )
        )
        return {"runs": [_record(run) for run in runs]}

    @app.get("/api/mc/verification/runs/{run_id}")
    def verification_run(run_id: str) -> dict[str, Any]:
        run = _call(lambda: core.verification_run(run_id))
        if run is None:
            raise HTTPException(status_code=404, detail="Verification run not found")
        return {"run": _record(run)}

    @app.post("/api/mc/tasks/{task_id}/verification-policy")
    def bind_verification_policy(
        task_id: str, payload: VerificationPolicy
    ) -> dict[str, Any]:
        task = _call(
            lambda: core.bind_verification_profile(
                task_id,
                payload.profile_id,
                expected_version=payload.expected_version,
            )
        )
        return {"task": _record(task)}

    @app.post("/api/mc/tasks/{task_id}/verify")
    def run_verification(
        task_id: str, payload: VersionedTaskAction
    ) -> dict[str, Any]:
        run = _call(
            lambda: core.run_verification(
                task_id,
                expected_version=payload.expected_version,
            )
        )
        return {"run": _record(run)}

    @app.get("/api/mc/attention")
    def attention(
        after_sequence: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, Any]:
        feed = _call(
            lambda: core.attention(
                after_sequence=after_sequence,
                limit=limit,
            )
        )
        return _record(feed)

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
            "message": "Mission Control records approval evidence but exposes no remote mutation.",
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
            "verification_authority": (
                "Core-owned receipt required; caller identity is not authenticated"
            ),
            "direct_completion_enabled": False,
            "verification_request_surface": "fixed profile and task version only",
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
    except (
        ScheduleError,
        StoreConflict,
        StoreError,
        VerificationPolicyError,
    ) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _record(value: Any) -> dict[str, Any]:
    """Serialize Core records without weakening their request boundary."""

    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"Unsupported Core record type: {type(value).__name__}")


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _authority(value: str | None) -> tuple[str, int | None]:
    """Parse an HTTP Host header without accepting user-info or path syntax."""

    text = (value or "").strip().lower()
    if not text or any(character in text for character in "/?#@"):
        return "", None
    try:
        parsed = urlsplit("//" + text)
        return (parsed.hostname or "").lower(), parsed.port
    except ValueError:
        return "", None
