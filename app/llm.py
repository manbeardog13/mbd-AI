"""The bridge to your local brain: talking to Ollama.

Ollama runs the actual language model on your machine and exposes a small
HTTP API. This module streams responses from it token-by-token so the web
UI can show the reply as it's being written, just like chatting with me.
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, AsyncGenerator

import httpx

if TYPE_CHECKING:
    from .config import Config


async def stream_chat(
    host: str,
    model: str,
    messages: list[dict],
    temperature: float,
) -> AsyncGenerator[str, None]:
    """Stream the model's reply as a series of text chunks.

    `messages` is the full conversation in OpenAI/Ollama format:
    [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
    """
    url = f"{host.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {"temperature": temperature},
    }

    # No timeout: a long thoughtful answer shouldn't get cut off.
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    yield chunk
                if data.get("done"):
                    break


async def check_ollama(host: str, model: str) -> tuple[bool, str]:
    """Health check: is Ollama up, and is the chosen model available?

    Returns (ok, human_readable_message).
    """
    base = host.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{base}/api/tags")
            r.raise_for_status()
            installed = [m.get("name", "") for m in r.json().get("models", [])]
    except Exception as exc:  # noqa: BLE001 - we want any failure to be friendly
        return False, (
            f"Can't reach Ollama at {host}. Is it running? "
            f"Start it with `ollama serve` (or open the Ollama app). [{exc}]"
        )

    # Match the exact tag (allowing Ollama's implicit ":latest"), not just the
    # family — otherwise a sibling tag like qwen3:8b would make us claim
    # qwen3:14b is ready when chat would actually fail.
    wanted = {model}
    if ":" not in model:
        wanted.add(f"{model}:latest")
    if not any(name in wanted for name in installed):
        return False, (
            f"Ollama is running, but the model '{model}' isn't installed yet. "
            f"Pull it with:  ollama pull {model}"
        )

    return True, "Connected and ready."


# --------------------------------------------------------------------------
# Synchronous helpers for the memory subsystem (embeddings + reflection).
# These return a safe empty value on any failure, so callers degrade
# gracefully instead of crashing when the model or embedder is unavailable.
# --------------------------------------------------------------------------

def embed_text(cfg: "Config", text: str) -> list[float] | None:
    """Embed text with the local embedding model. Returns None if unavailable."""
    if not text or not text.strip():
        return None
    url = f"{cfg.ollama_host.rstrip('/')}/api/embeddings"
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(url, json={"model": cfg.embed_model, "prompt": text})
            r.raise_for_status()
            emb = r.json().get("embedding")
            return emb if emb else None
    except Exception:
        return None


def complete_chat(
    cfg: "Config",
    messages: list[dict],
    temperature: float = 0.0,
    model: str | None = None,
    num_predict: int | None = None,
    keep_alive: str | None = None,
) -> str:
    """Non-streaming completion for reflection/utility calls. '' on failure.

    `keep_alive` controls how long Ollama keeps the model in VRAM after the
    call (e.g. "0" to unload immediately — handy for a secondary reflection
    model so it doesn't crowd the main chat model on a small GPU).
    """
    options: dict = {"temperature": temperature}
    if num_predict is not None:
        options["num_predict"] = num_predict
    payload = {
        "model": model or cfg.model,
        "messages": messages,
        "stream": False,
        "options": options,
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    url = f"{cfg.ollama_host.rstrip('/')}/api/chat"
    try:
        with httpx.Client(timeout=120) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "") or ""
    except Exception:
        return ""
