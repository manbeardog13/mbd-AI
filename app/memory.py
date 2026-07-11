"""Nero's cognitive memory layer.

Built on the storage primitives in `app/db.py`. Two jobs:

  * **retrieve(...)** — given the current message, return the handful of most
    relevant memories, weighted by confidence, time-decay, and (when available)
    semantic similarity via a local embedding model. Degrades gracefully to
    confidence+recency when embeddings aren't available.

  * **reflect(...)** — after an exchange, ask the model what's worth remembering
    about Toni, then store/merge those memories. This is how Nero learns without
    being told to.

Everything here is synchronous and pure-Python (no numpy), so it's easy to test
and cheap to run; the web layer calls it from a worker thread.
"""
from __future__ import annotations

import json
import logging
import math
import re
import threading
import time
from datetime import datetime, timezone

from . import db
from .config import Config
from .llm import complete_chat, embed_text

log = logging.getLogger("nero.memory")

# Serializes memory writes + metric updates across background reflection threads
# (reflection runs in a worker thread per reply). Reentrant so helpers can nest.
_lock = threading.RLock()

# Simple in-process metrics (surfaced by /api/metrics and the future dashboard).
METRICS: dict[str, float] = {
    "retrievals": 0,
    "last_retrieval_ms": 0.0,
    "last_retrieved": 0,
    "reflections": 0,
    "memories_added": 0,
    "memories_reinforced": 0,
}


def _bump(key: str, n: float = 1) -> None:
    with _lock:
        METRICS[key] = METRICS.get(key, 0) + n


_SIMILAR_THRESHOLD = 0.90  # cosine ≥ this ⇒ treat as the same memory (reinforce)


# ---- math helpers -----------------------------------------------------

def _parse_ts(ts: str) -> datetime:
    try:
        dt = datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    # Always return an aware datetime so arithmetic with now(utc) never raises.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def decay_factor(last_reinforced: str, half_life_days: float) -> float:
    """0..1 multiplier: 1.0 when fresh, 0.5 after one half-life, → 0 with age."""
    if half_life_days <= 0:
        return 1.0
    age_days = (datetime.now(timezone.utc) - _parse_ts(last_reinforced)).total_seconds() / 86400.0
    age_days = max(0.0, age_days)
    return 0.5 ** (age_days / half_life_days)


def cosine(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


_WORD = re.compile(r"[a-zA-Z0-9']+")


def _keyword_overlap(query: str, content: str) -> float:
    qs = {w.lower() for w in _WORD.findall(query)}
    cs = {w.lower() for w in _WORD.findall(content)}
    if not qs or not cs:
        return 0.0
    return len(qs & cs) / len(qs)


# ---- retrieval --------------------------------------------------------

def _relevance(mem: dict, query: str, query_emb: list[float] | None) -> float:
    """Relevance of a memory to the query, in [0, 1], on ONE comparable scale.

    Uses semantic similarity only when the stored embedding is actually
    comparable to the query embedding (same model ⇒ same dimension); otherwise —
    no query embedding, no stored embedding, or a dimension mismatch after an
    embed-model change — it falls back to lexical overlap. This keeps embedded
    and non-embedded memories rankable against each other.
    """
    emb = mem.get("embedding")
    if query_emb and emb and len(query_emb) == len(emb):
        return max(0.0, cosine(query_emb, emb))
    return _keyword_overlap(query, mem["content"])


def score_memory(mem: dict, cfg: Config, query: str, query_emb: list[float] | None) -> float:
    """Rank score for one memory: (confidence × decay × importance) × relevance.

    A floor on the relevance term keeps a strongly-held memory from vanishing
    when nothing matches, while still ranking it below genuinely relevant ones.
    """
    base = mem["confidence"] * decay_factor(mem["last_reinforced"], cfg.memory_half_life_days)
    base *= 0.5 + 0.5 * mem.get("importance", 0.5)
    return base * (0.3 + 0.7 * _relevance(mem, query, query_emb))


def retrieve(cfg: Config, query: str, k: int | None = None) -> list[dict]:
    """Return the top-k memories for `query`, best first (decay-weighted)."""
    started = time.monotonic()
    mems = db.all_memories(include_embeddings=True)
    if not mems:
        return []
    k = k or cfg.memory_top_k

    query_emb = None
    if any(m.get("embedding") for m in mems):
        query_emb = embed_text(cfg, query)  # None if embedder unavailable

    scored = [(score_memory(m, cfg, query, query_emb), m) for m in mems]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = [m for score, m in scored[:k] if score >= cfg.memory_min_score]

    with _lock:
        METRICS["retrievals"] += 1
        METRICS["last_retrieval_ms"] = (time.monotonic() - started) * 1000.0
        METRICS["last_retrieved"] = len(top)
    log.info(
        "retrieve q=%r -> %d/%d memories (embed=%s, %.0fms)",
        query[:48], len(top), len(mems), bool(query_emb), METRICS["last_retrieval_ms"],
    )
    return top


# ---- reflection (automatic memory capture) ----------------------------

# Token budget for a reflection pass. Generous on purpose: reflection runs on a
# small model with think=False, but if a given Ollama/model build still slips in
# some reasoning, a tight budget can get cut off *before* the JSON is emitted —
# yielding zero memories. Extra headroom costs a little latency, never accuracy.
REFLECTION_NUM_PREDICT = 1024

_REFLECTION_SYSTEM = (
    "You extract durable, useful facts to remember about a person (the user) from a "
    "short slice of their conversation with their AI. Only capture things that will "
    "still matter days from now: preferences, goals, projects, relationships, skills, "
    "decisions, and outcomes. Ignore small talk and anything ephemeral.\n\n"
    "Respond with ONLY a JSON array (no prose). Each item:\n"
    '{"content": "<concise fact, third person about the user>", '
    '"type": "semantic|preference|episodic|experience|procedural", '
    '"importance": 0.0-1.0, "confidence": 0.0-1.0, "entities": ["..."]}\n'
    "If there is nothing worth remembering, respond with []."
)


def _reflection_user_prompt(owner: str, user_text: str, assistant_text: str) -> str:
    return (
        f"The user is {owner}.\n\n"
        f"{owner} said:\n{user_text}\n\n"
        f"Nero replied:\n{assistant_text}\n\n"
        "Extract the durable facts worth remembering (JSON array only)."
    )


def strip_think(text: str) -> str:
    """Remove <think>…</think> reasoning blocks a model might emit.

    Also drops an *unterminated* trailing ``<think>`` — a reasoning block cut off
    by a tight token budget never gets its closing tag, and its half-formed
    contents (often a draft JSON guess) would otherwise leak into parsing and be
    mistaken for the real answer.
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<think>.*$", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _first_balanced_json(text: str, open_ch: str, close_ch: str):
    """Return the first balanced ``open_ch…close_ch`` span that parses as JSON.

    Scans candidate start positions left-to-right. If a balanced span fails to
    parse — or never balances (e.g. a stray emoticon brace) — it advances to the
    next candidate instead of giving up, so real JSON that follows
    bracket-containing prose (``example {like this}: {"real": 1}``) is still
    recovered. Returns the parsed value, or ``None`` if no candidate parses.
    """
    start = text.find(open_ch)
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break  # malformed span — try the next candidate start
        start = text.find(open_ch, start + 1)
    return None


def _extract_json_array(text: str) -> list | None:
    """Pull the first JSON array out of a model reply, tolerating fences/prose.

    Robust to bracketed prose on either side of the real payload (e.g.
    `example [ignore]. [{...}]` or `[...]. Note: [nothing else]`) by scanning
    for the first *balanced* `[...]` span that actually parses.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()

    try:
        whole = json.loads(text)
        if isinstance(whole, list):
            return whole
    except json.JSONDecodeError:
        pass

    value = _first_balanced_json(text, "[", "]")
    return value if isinstance(value, list) else None


def parse_memories(raw: str) -> list[dict]:
    """Parse the model's JSON array of memories, tolerating extra prose/fences."""
    if not raw:
        return []
    data = _extract_json_array(strip_think(raw))
    if not isinstance(data, list):
        return []

    cleaned: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        mtype = str(item.get("type", "semantic")).strip().lower()
        if mtype not in db.MEMORY_TYPES:
            mtype = "semantic"
        entities = item.get("entities") or []
        if not isinstance(entities, list):
            entities = []
        cleaned.append({
            "content": content,
            "type": mtype,
            "importance": _to_float(item.get("importance"), 0.5),
            "confidence": _to_float(item.get("confidence"), 0.7),
            "entities": [str(e).strip() for e in entities if str(e).strip()],
        })
    return cleaned


def _to_float(value, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def store_memory(cfg: Config, item: dict) -> str:
    """Add a reflected memory, or reinforce a near-duplicate. Returns the action.

    The dedup read + write are done under `_lock` so two concurrent reflections
    can't both pass the duplicate check and insert the same fact twice. The slow
    embedding call is done *before* taking the lock.
    """
    emb = embed_text(cfg, item["content"])
    norm = item["content"].strip().lower()

    with _lock:
        for m in db.all_memories(include_embeddings=True):
            same_text = m["content"].strip().lower() == norm
            stored = m.get("embedding")
            similar = (
                bool(emb and stored and len(emb) == len(stored))
                and cosine(emb, stored) >= _SIMILAR_THRESHOLD
            )
            if same_text or similar:
                db.reinforce_memory(m["id"])
                METRICS["memories_reinforced"] += 1
                return "reinforced"

        db.add_memory(
            content=item["content"],
            mtype=item["type"],
            importance=item["importance"],
            confidence=item["confidence"],
            source="reflection",
            entities=item["entities"],
            embedding=emb,
        )
        METRICS["memories_added"] += 1
        return "added"


def reflect(cfg: Config, user_text: str, assistant_text: str) -> dict:
    """Look at the latest exchange and remember what matters. Best-effort.

    Returns a small summary dict (also useful for tests/observability).
    """
    summary = {"added": 0, "reinforced": 0, "skipped": False}
    if not cfg.reflection_enabled or not user_text.strip():
        summary["skipped"] = True
        return summary
    try:
        reflect_model = cfg.reflection_model or cfg.model
        # If reflection uses a *separate* model, unload it right after so it
        # doesn't sit in VRAM alongside the (larger) chat model on a small GPU.
        keep_alive = "0" if reflect_model != cfg.model else None
        raw = complete_chat(
            cfg,
            [
                {"role": "system", "content": _REFLECTION_SYSTEM},
                {"role": "user", "content": _reflection_user_prompt(
                    cfg.owner_name, user_text, assistant_text)},
            ],
            temperature=0.0,
            model=reflect_model,
            num_predict=REFLECTION_NUM_PREDICT,
            keep_alive=keep_alive,
            think=False,  # reflection must emit clean JSON, not reasoning
        )
        for item in parse_memories(raw):
            action = store_memory(cfg, item)
            summary[action] = summary.get(action, 0) + 1
        _bump("reflections")
        log.info("reflect -> +%d added, %d reinforced", summary["added"], summary["reinforced"])
    except Exception as exc:  # noqa: BLE001 - reflection must never break chat
        log.warning("reflection failed: %s", exc)
        summary["skipped"] = True
    return summary
