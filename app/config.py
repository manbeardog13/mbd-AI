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
    host: str
    port: int
    # Memory subsystem
    embed_model: str
    memory_top_k: int
    memory_half_life_days: float
    memory_min_score: float
    reflection_enabled: bool
    reflection_model: str


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
    )
