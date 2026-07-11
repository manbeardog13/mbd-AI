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

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db
from .config import load_config, set_override
from .llm import check_ollama, stream_chat
from .prompt import build_system_prompt

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
    return {"humor": cfg.humor, "languages": cfg.languages, "voice": cfg.voice}


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

    memories = [m["content"] for m in db.get_memories()]
    system_prompt = build_system_prompt(cfg, memories)
    history_msgs = db.get_messages(conv_id, limit=cfg.history_limit)

    messages = [{"role": "system", "content": system_prompt}, *history_msgs]

    async def generate():
        collected: list[str] = []
        try:
            async for chunk in stream_chat(
                cfg.ollama_host, cfg.model, messages, cfg.temperature
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
    mem_id = db.add_memory(content)
    return {"id": mem_id, "content": content}


@app.delete("/api/memories/{memory_id}")
def remove_memory(memory_id: int) -> dict:
    db.delete_memory(memory_id)
    return {"ok": True}


# Serve the JS/CSS. Mounted last so it doesn't shadow the API routes.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
