"""The web server that ties everything together.

Serves the chat web app and exposes a small API the browser talks to:

  GET  /                  -> the chat page
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
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, memory, world_model
from .config import load_config, set_override
from .llm import check_ollama, embed_text, stream_chat
from .prompt import build_system_prompt

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


class SettingsIn(BaseModel):
    humor: int | None = None
    voice: str | None = None


# ---- Pages & basic info ----

@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


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


@app.get("/api/metrics")
def metrics() -> dict:
    """Lightweight observability into the memory + world-model subsystems."""
    return {"memory": memory.METRICS, "world": world_model.METRICS}


@app.delete("/api/memories/{memory_id}")
def remove_memory(memory_id: int) -> dict:
    db.delete_memory(memory_id)
    return {"ok": True}


# Serve the JS/CSS. Mounted last so it doesn't shadow the API routes.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
