"""The web server that ties everything together.

Serves the chat web app and exposes a small API the browser talks to:

  GET  /                  -> the chat page
  GET  /mission-control   -> the Mission Control operating screen
  GET  /api/host          -> honest host telemetry (measured or unavailable)
  POST /api/council/dispatch -> stage files for Claude · Architect (adapter)
  GET  /api/config        -> your AI's name / your name (for the UI)
  GET  /api/status        -> is the local model reachable?
  GET  /api/history       -> messages in the current conversation
  POST /api/chat          -> send a message, stream back the reply
  POST /api/new           -> start a fresh conversation
  GET  /api/memories      -> list long-term memories
  POST /api/memories      -> add a memory
  DELETE /api/memories/id -> forget a memory
"""
from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.datastructures import UploadFile

import io
import socket

try:  # optional dependency — powers honest /api/host telemetry when installed
    import psutil  # type: ignore
except Exception:  # noqa: BLE001 - contained; telemetry is honestly "unavailable" without it
    psutil = None  # type: ignore

try:  # optional — renders a scan-to-open QR on /connect when installed
    import segno  # type: ignore
except Exception:  # noqa: BLE001 - contained; /connect still shows the URL without it
    segno = None  # type: ignore

from . import collaboration, db, memory, tts, world_model
from .agent import loop as agent_loop, state as agent_state
from .capabilities import Context, Registry
from .capabilities.builtin import register_builtins
from .config import ROOT, load_config, set_override
from .llm import check_ollama, embed_text, stream_chat
from .prompt import build_system_prompt

# One Capability Registry for the process, populated with the built-in provider
# at import (ADR-0007). MCP / Skills register here later, no loop changes needed.
REGISTRY = Registry()
register_builtins(REGISTRY)


def _project_dir(cfg) -> str:
    """The directory the agent is jailed to and observes (default: repo root)."""
    return (cfg.agent_project_dir or "").strip() or str(ROOT)

# Keep references to fire-and-forget reflection tasks so they aren't GC'd.
_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Your Personal AI")


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


# ---- Request bodies ----

class ChatIn(BaseModel):
    message: str


class MemoryIn(BaseModel):
    content: str


class SpeakIn(BaseModel):
    text: str


class SettingsIn(BaseModel):
    humor: int | None = None
    voice: str | None = None


class AgentIn(BaseModel):
    message: str


class CollaborationIn(BaseModel):
    task: str
    mode: str = "plan-build-review"


# ---- Pages & basic info ----

@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/mission-control")
def mission_control() -> FileResponse:
    """The Mission Control operating screen (the Companion's command surface)."""
    return FileResponse(STATIC_DIR / "mission-control.html")


@app.get("/connect")
def connect_page() -> FileResponse:
    """A device-connect helper: how to reach this Companion from phone/tablet."""
    return FileResponse(STATIC_DIR / "connect.html")


@app.get("/api/config")
def get_config_info() -> dict:
    cfg = load_config()
    return {"ai_name": cfg.ai_name, "owner_name": cfg.owner_name, "model": cfg.model}


@app.get("/api/settings")
def get_settings() -> dict:
    cfg = load_config()
    return {
        "humor": cfg.humor,
        "languages": cfg.languages,
        "voice": cfg.voice,
        "thinking": cfg.thinking,
    }


@app.post("/api/settings")
def update_settings(payload: SettingsIn) -> dict:
    if payload.humor is not None:
        set_override("humor", max(0, min(100, int(payload.humor))))
    if payload.voice is not None:
        set_override("voice", payload.voice.strip())
    cfg = load_config()
    return {"humor": cfg.humor, "voice": cfg.voice}


@app.get("/api/status")
async def status() -> dict:
    cfg = load_config()
    ok, message = await check_ollama(cfg.ollama_host, cfg.model)
    return {"ok": ok, "message": message, "model": cfg.model}


# ---- Conversation ----

@app.get("/api/history")
def history() -> dict:
    conv_id = db.get_or_create_active_conversation()
    return {"messages": db.get_messages(conv_id)}


@app.post("/api/new")
def new_conversation() -> dict:
    conv_id = db.start_new_conversation()
    return {"conversation_id": conv_id}


@app.post("/api/chat")
async def chat(payload: ChatIn) -> StreamingResponse:
    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty.")

    # Reload config each turn so edits to personality/model apply live.
    cfg = load_config()

    conv_id = db.get_or_create_active_conversation()
    db.add_message(conv_id, "user", text)

    # Recall the memories most relevant to this message (off the event loop).
    retrieved = await asyncio.to_thread(memory.retrieve, cfg, text)
    memories = [m["content"] for m in retrieved]
    # Nero's live picture of what Toni's working on, for continuity. Best-effort
    # and off the event loop: continuity is optional, so a world-read hiccup
    # (e.g. the DB briefly locked) must degrade to "no block", never 500 the chat.
    try:
        world = await asyncio.to_thread(
            lambda: world_model.render(db.get_world(), cfg.owner_name)
        )
    except Exception:  # noqa: BLE001 - never break the reply over continuity
        world = ""
    system_prompt = build_system_prompt(cfg, memories, world=world)
    history_msgs = db.get_messages(conv_id, limit=cfg.history_limit)

    messages = [{"role": "system", "content": system_prompt}, *history_msgs]

    async def generate():
        collected: list[str] = []
        try:
            async for chunk in stream_chat(
                cfg.ollama_host, cfg.model, messages, cfg.temperature,
                think=cfg.thinking,
            ):
                collected.append(chunk)
                yield chunk
        except Exception as exc:  # noqa: BLE001 - surface any error to the user
            note = (
                f"\n\n[Sorry — I couldn't reach my brain just now. {exc}]"
            )
            collected.append(note)
            yield note
        finally:
            # Persist whatever was generated so history stays consistent.
            reply = "".join(collected).strip()
            if reply:
                db.add_message(conv_id, "assistant", reply)
                # In the background: decide what to remember, and update the
                # live picture of what Toni's working on.
                _spawn(asyncio.to_thread(memory.reflect, cfg, text, reply))
                _spawn(asyncio.to_thread(world_model.update, cfg, text, reply))

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


# ---- Long-term memories ----

@app.get("/api/memories")
def list_memories() -> dict:
    return {"memories": db.get_memories()}


@app.post("/api/memories")
def create_memory(payload: MemoryIn) -> dict:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Memory is empty.")
    cfg = load_config()
    embedding = embed_text(cfg, content)  # best-effort; None if embedder is down
    mem_id = db.add_memory(content, source="user", embedding=embedding)
    return {"id": mem_id, "content": content}


@app.get("/api/world")
def world_state() -> dict:
    """Nero's live picture of what Toni is working on (for the Home dashboard)."""
    return {"world": db.get_world()}


@app.delete("/api/world")
def clear_world_state() -> dict:
    """Wipe Nero's live picture — a clean-slate reset (owner remediation)."""
    db.clear_world()
    return {"ok": True}


@app.delete("/api/world/{key}")
def clear_world_field(key: str) -> dict:
    """Clear a single field from Nero's live picture."""
    db.delete_world_key(key)
    return {"ok": True}


# ---- Agent (Phase 1: the hands) ----

@app.get("/api/agent/capabilities")
def agent_capabilities() -> dict:
    """What Nero can currently do — the live registry the model reasons over."""
    return {"capabilities": REGISTRY.specs()}


@app.get("/api/executive")
def executive_state() -> dict:
    """Nero's working-state register — what she's doing now, and where (ADR-0008)."""
    cfg = load_config()
    ws = agent_state.read(_project_dir(cfg))
    return {"working_state": ws.as_dict()}


@app.delete("/api/executive")
def clear_executive_state() -> dict:
    """Reset the working-state register (a fresh start for a new goal)."""
    agent_state.clear()
    return {"ok": True}


@app.post("/api/agent")
async def agent_run(payload: AgentIn) -> dict:
    """Run the agent loop on a task: reason → use a capability → observe → answer.

    Read-only capabilities run freely; anything MEDIUM+ needs confirmation, and
    this non-interactive endpoint has no confirm channel yet, so such actions are
    safely denied (fail-closed) until the confirmation UX lands. The working-state
    register is observed before and updated after the turn.
    """
    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty.")
    cfg = load_config()
    if not cfg.agent_enabled:
        raise HTTPException(status_code=403, detail="Agent mode is disabled.")

    project_dir = _project_dir(cfg)
    # Deterministic working-state: read (observes branch/project), record the
    # task, then re-read so the response shows the live register.
    await asyncio.to_thread(agent_state.update, {"task": text})
    ws = await asyncio.to_thread(agent_state.read, project_dir)
    ctx = Context(allowed_dirs=[project_dir], conversation_id=None, confirm=None)

    result = await asyncio.to_thread(
        agent_loop.run, cfg, REGISTRY, ctx, text,
        system_extra=agent_state.render(ws),
    )
    return {
        "answer": result.answer,
        "steps": result.steps,
        "stopped": result.stopped_reason,
        "working_state": ws.as_dict(),
    }


@app.get("/api/metrics")
def metrics() -> dict:
    """Lightweight observability into every subsystem."""
    from .capabilities import METRICS as cap_metrics
    return {
        "memory": memory.METRICS,
        "world": world_model.METRICS,
        "voice": tts.METRICS,
        "agent": agent_loop.METRICS,
        "capabilities": cap_metrics,
    }


# ---- Explicit cloud collaboration (ordinary chat stays local) ----

@app.get("/api/collaboration/status")
def collaboration_status() -> dict:
    return collaboration.status(load_config())


@app.post("/api/collaboration")
async def collaboration_run(payload: CollaborationIn) -> dict:
    try:
        return await collaboration.coordinate(load_config(), payload.task, payload.mode)
    except collaboration.CollaborationConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except collaboration.CollaborationProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except collaboration.CollaborationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---- Mission Control (honest host telemetry + Council dispatch) ----

@app.get("/api/host")
def host_telemetry() -> dict:
    """Real, measured host telemetry for the Mission Control panel.

    Honesty is the whole point of this endpoint (see the acceptance directive):
    a gauge is drawn by the UI **only** when the response attests
    ``"simulated": false`` — which we return **exclusively** for values we have
    actually measured. CPU/RAM/disk come from ``psutil``; there is no
    vendor-neutral GPU source, so ``gpu`` is ``null`` with a stated reason (the
    UI then draws no GPU gauge). When no measurement source exists we do **not**
    fabricate a fallback — we return ``503`` so the panel shows "Disconnected".
    """
    if psutil is None:
        # No measured source. Per the contract, fail rather than invent values.
        raise HTTPException(
            status_code=503,
            detail="No measured host telemetry source is connected (install psutil).",
        )
    vm = psutil.virtual_memory()
    du = psutil.disk_usage(str(ROOT))
    return {
        "simulated": False,  # attested: every value below is measured, not invented
        "cpu": psutil.cpu_percent(interval=None),
        "ram": vm.percent,
        "ram_total_gb": round(vm.total / 1_000_000_000, 1),
        "disk": du.percent,
        "disk_total_gb": round(du.total / 1_000_000_000),
        "gpu": None,
        "gpu_reason": "No vendor-neutral GPU source is connected on this host.",
        "local_runtime": "Active",  # this Companion process is serving
    }


@app.get("/api/council/status")
def council_dispatch_status() -> dict:
    return collaboration.architect_status(load_config())


@app.post("/api/council/dispatch")
async def council_dispatch(request: Request) -> dict:
    """Send one explicit task and selected files to Claude Architect.

    Configuration is checked before multipart parsing. Supported files are sent
    inline in one Messages request; no persistent Files API upload is created.
    """
    cfg = load_config()
    try:
        collaboration.ensure_architect_ready(cfg)
    except collaboration.CollaborationConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > collaboration.MAX_MULTIPART_BYTES:
                raise HTTPException(status_code=413, detail="Council request exceeds 24 MiB.")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from exc

    try:
        form = await request.form(max_files=collaboration.MAX_FILES, max_fields=8)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid multipart Council request.") from exc

    target = str(form.get("target") or "").strip().lower()
    role = str(form.get("role") or "").strip().lower()
    if target != "claude" or role != "architect":
        raise HTTPException(status_code=400, detail="Only target=claude and role=architect are supported.")
    prompt = str(form.get("prompt") or "")

    attachments: list[collaboration.Attachment] = []
    for value in form.getlist("files"):
        if not isinstance(value, UploadFile):
            raise HTTPException(status_code=400, detail="Invalid file attachment.")
        name = value.filename or "attachment"
        guessed_type = mimetypes.guess_type(name)[0]
        media_type = value.content_type or guessed_type or "application/octet-stream"
        if media_type == "application/octet-stream" and guessed_type:
            media_type = guessed_type
        try:
            data = await value.read(collaboration.MAX_FILE_BYTES + 1)
        finally:
            await value.close()
        attachments.append(collaboration.Attachment(name, media_type, data))

    try:
        return await collaboration.dispatch_architect(cfg, prompt, attachments)
    except collaboration.CollaborationAttachmentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except collaboration.CollaborationProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except collaboration.CollaborationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _lan_ipv4s() -> list[str]:
    """This host's LAN IPv4 addresses (for reaching Nero from phone/tablet).

    Best-effort and offline: resolves the hostname and asks the OS which local
    address it would route out of. Loopback and link-local are excluded.
    """
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith(("127.", "169.254.")):
                ips.add(ip)
    except Exception:  # noqa: BLE001 - contained; discovery is best-effort
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.168.255.255", 1))  # selects the egress iface; sends nothing
            ip = s.getsockname()[0]
            if not ip.startswith(("127.", "169.254.")):
                ips.add(ip)
        finally:
            s.close()
    except Exception:  # noqa: BLE001 - contained
        pass
    return sorted(ips)


@app.get("/api/connect")
def connect_info() -> dict:
    """Where to reach Mission Control from other devices on this network.

    Returns this host's LAN URLs (and localhost), plus an optional scan-to-open
    QR SVG for the primary device URL when the optional ``segno`` package is
    installed. Nothing is measured or invented — these are this machine's own
    addresses. Off-network access is via Tailscale (see docs/REMOTE_ACCESS.md).
    """
    cfg = load_config()
    port = cfg.port
    ips = _lan_ipv4s()
    hosts = ["localhost", *ips]
    urls = [{"label": ("This PC" if h == "localhost" else h), "host": h,
             "mission_control": f"http://{h}:{port}/mission-control",
             "base": f"http://{h}:{port}/"} for h in hosts]
    primary = f"http://{ips[0]}:{port}/mission-control" if ips else f"http://localhost:{port}/mission-control"

    qr_svg = None
    if segno is not None and ips:
        try:
            buf = io.BytesIO()
            segno.make(primary, error="m").save(
                buf, kind="svg", scale=5, border=2, dark="#c9f6ff", light="#141414"
            )
            qr_svg = buf.getvalue().decode("utf-8")
        except Exception:  # noqa: BLE001 - QR is a bonus; never break the page
            qr_svg = None

    return {
        "hostname": socket.gethostname(),
        "port": port,
        "lan_ips": ips,
        "urls": urls,
        "primary_url": primary,
        "qr_svg": qr_svg,
    }


# ---- Voice (local neural text-to-speech) ----

@app.get("/api/voice")
def voice_status() -> dict:
    """Whether Nero's local neural voice is available (for the UI to decide)."""
    cfg = load_config()
    return {
        "enabled": cfg.tts_enabled,
        "engine": cfg.tts_engine,
        "voice": cfg.tts_voice,
        "available": tts.available(cfg),
    }


@app.post("/api/speak")
async def speak(payload: SpeakIn) -> Response:
    """Synthesize `text` in Nero's local voice.

    Returns audio/wav on success, or 204 No Content when the neural voice isn't
    installed/enabled — the browser then falls back to its own voice.
    """
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Nothing to speak.")
    cfg = load_config()
    audio = await asyncio.to_thread(tts.synthesize, cfg, text)
    if not audio:
        return Response(status_code=204)
    return Response(content=audio, media_type="audio/wav")


@app.delete("/api/memories/{memory_id}")
def remove_memory(memory_id: int) -> dict:
    db.delete_memory(memory_id)
    return {"ok": True}


# Serve the JS/CSS. Mounted last so it doesn't shadow the API routes.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
