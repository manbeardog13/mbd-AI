"""Loads your configuration from config.yaml.

On first run, if config.yaml doesn't exist yet, it's created by copying
config.example.yaml. That keeps your personal settings out of git while
still shipping sensible defaults.

Some settings (like the humor dial) can be changed live from the web app.
Those live overrides are stored in data/settings.json so your nicely
commented config.yaml is never rewritten.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
EXAMPLE_PATH = ROOT / "config.example.yaml"
SETTINGS_PATH = ROOT / "data" / "settings.json"

# Fallbacks used only if config.yaml omits these (or leaves them blank).
DEFAULT_GOALS = [
    "Help your person think clearly and work faster",
    "Protect your person's privacy and data",
    "Learn your person's habits and preferences over time",
    "Reduce repetitive work",
    "Never interrupt unnecessarily",
]
DEFAULT_PRINCIPLES = [
    "Be honest; never pretend or make things up",
    "Say when you're unsure — and roughly how sure you are",
    "Be concise unless depth is wanted",
    "Explain before doing anything consequential",
    "Remember what matters; let trivia fade",
]


@dataclass
class Config:
    """Everything that makes Nero *yours* — identity, languages, humor, brain."""

    ai_name: str
    owner_name: str
    personality: str
    goals: list[str]
    principles: list[str]
    languages: list[str]
    humor: int
    voice: str
    model: str
    ollama_host: str
    history_limit: int
    temperature: float
    thinking: bool
    host: str
    port: int
    # Memory subsystem
    embed_model: str
    memory_top_k: int
    memory_half_life_days: float
    memory_min_score: float
    reflection_enabled: bool
    reflection_model: str
    world_model_enabled: bool
    # Voice (local neural text-to-speech)
    tts_enabled: bool
    tts_engine: str
    tts_voice: str
    tts_speed: float
    tts_model_dir: str
    # Agent (Phase 1: the hands — agent loop, capabilities, executive memory)
    agent_enabled: bool
    agent_max_steps: int
    agent_max_seconds: float
    agent_project_dir: str
    # Human-triggered External Council and direct Claude Architect dispatch.
    collaboration_enabled: bool = False
    collaboration_openai_api_key: str = ""
    collaboration_openai_model: str = ""
    collaboration_anthropic_api_key: str = ""
    collaboration_anthropic_model: str = ""
    collaboration_timeout_seconds: float = 90.0
    collaboration_max_output_tokens: int = 1800
    collaboration_max_handoff_chars: int = 12000


def ensure_config() -> None:
    """Create config.yaml from the example the first time the app runs."""
    if not CONFIG_PATH.exists():
        if not EXAMPLE_PATH.exists():
            raise FileNotFoundError(
                "config.example.yaml is missing — can't create your config.yaml."
            )
        shutil.copyfile(EXAMPLE_PATH, CONFIG_PATH)
        print(f"  Created {CONFIG_PATH.name} from the example. Edit it to make Nero yours.")


# ---- Live overrides (settings changed from the web app) ----

def load_overrides() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def set_override(key: str, value) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = load_overrides()
    data[key] = value
    SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _num(value, default, cast):
    """Coerce a config value to a number, falling back to default.

    Guards against a key being present but blank in config.yaml (parsed as
    None) or holding a non-numeric value — either would otherwise crash the
    whole backend, since load_config() runs on every request.
    """
    if value is None:
        return default
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def load_config() -> Config:
    """Read config.yaml (plus any live overrides). Called on each message."""
    ensure_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    overrides = load_overrides()

    def _list(key: str, default: list[str]) -> list[str]:
        value = data.get(key)
        if value is None:
            value = default
        if isinstance(value, str):
            value = [value]
        return [str(item).strip() for item in value if str(item).strip()]

    languages = _list("languages", ["English", "Croatian"])
    goals = _list("goals", DEFAULT_GOALS)
    principles = _list("principles", DEFAULT_PRINCIPLES)
    collaboration = _nested_mapping(data, "collaboration")
    collaboration_openai = _nested_mapping(collaboration, "openai")
    collaboration_anthropic = _nested_mapping(collaboration, "anthropic")

    # Every field below is written to tolerate a present-but-blank key in
    # config.yaml (which YAML parses as None). `or` handles strings; `_num`
    # handles numbers (so a valid 0.0 temperature is NOT turned into a default).
    humor = _clamp(_num(overrides.get("humor", data.get("humor")), 75, int), 0, 100)

    return Config(
        ai_name=(data.get("ai_name") or "Nero"),
        owner_name=(data.get("owner_name") or "friend"),
        personality=(data.get("personality") or "You are a helpful personal AI.").strip(),
        goals=goals,
        principles=principles,
        languages=languages,
        humor=humor,
        voice=(str(overrides.get("voice") or data.get("voice") or "female").strip() or "female"),
        model=(data.get("model") or "qwen3:14b"),
        ollama_host=(data.get("ollama_host") or "http://localhost:11434"),
        history_limit=_num(data.get("history_limit"), 20, int),
        temperature=_num(data.get("temperature"), 0.7, float),
        thinking=bool(data.get("thinking")),
        host=(data.get("host") or "0.0.0.0"),
        port=_num(data.get("port"), 8080, int),
        embed_model=(data.get("embed_model") or "nomic-embed-text"),
        memory_top_k=_num(data.get("memory_top_k"), 6, int),
        memory_half_life_days=_num(data.get("memory_half_life_days"), 30.0, float),
        memory_min_score=_num(data.get("memory_min_score"), 0.05, float),
        reflection_enabled=(
            True if data.get("reflection_enabled") is None
            else bool(data.get("reflection_enabled"))
        ),
        reflection_model=(data.get("reflection_model") or ""),
        world_model_enabled=(
            True if data.get("world_model_enabled") is None
            else bool(data.get("world_model_enabled"))
        ),
        tts_enabled=(
            True if data.get("tts_enabled") is None
            else bool(data.get("tts_enabled"))
        ),
        tts_engine=(data.get("tts_engine") or "kokoro"),
        tts_voice=(data.get("tts_voice") or "af_heart"),
        tts_speed=_num(data.get("tts_speed"), 1.0, float),
        tts_model_dir=(data.get("tts_model_dir") or "models"),
        agent_enabled=(
            True if data.get("agent_enabled") is None
            else bool(data.get("agent_enabled"))
        ),
        agent_max_steps=_clamp(_num(data.get("agent_max_steps"), 8, int), 1, 32),
        agent_max_seconds=_num(data.get("agent_max_seconds"), 60.0, float),
        agent_project_dir=(data.get("agent_project_dir") or ""),
        collaboration_enabled=_mapping_bool(collaboration, "enabled", False),
        collaboration_openai_api_key=(collaboration_openai.get("api_key") or "").strip(),
        collaboration_openai_model=(collaboration_openai.get("model") or "").strip(),
        collaboration_anthropic_api_key=(collaboration_anthropic.get("api_key") or "").strip(),
        collaboration_anthropic_model=(collaboration_anthropic.get("model") or "").strip(),
        collaboration_timeout_seconds=max(
            5.0, min(_num(collaboration.get("timeout_seconds"), 90.0, float), 300.0)
        ),
        collaboration_max_output_tokens=_clamp(
            _num(collaboration.get("max_output_tokens"), 1800, int), 128, 4096
        ),
        collaboration_max_handoff_chars=_clamp(
            _num(collaboration.get("max_handoff_chars"), 12000, int), 1000, 20000
        ),
    )


def _nested_mapping(block: dict, key: str) -> dict:
    value = block.get(key)
    return value if isinstance(value, dict) else {}


def _mapping_bool(block: dict, key: str, default: bool) -> bool:
    value = block.get(key)
    return default if value is None else bool(value)
