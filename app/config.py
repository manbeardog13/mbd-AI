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


@dataclass
class Config:
    """Everything that makes Nero *yours* — identity, languages, humor, brain."""

    ai_name: str
    owner_name: str
    personality: str
    languages: list[str]
    humor: int
    voice: str
    model: str
    ollama_host: str
    history_limit: int
    temperature: float
    host: str
    port: int


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


def load_config() -> Config:
    """Read config.yaml (plus any live overrides). Called on each message."""
    ensure_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    overrides = load_overrides()

    languages = data.get("languages") or ["English", "Croatian"]
    if isinstance(languages, str):
        languages = [languages]

    humor = int(overrides.get("humor", data.get("humor", 75)))

    return Config(
        ai_name=data.get("ai_name", "Nero"),
        owner_name=data.get("owner_name", "friend"),
        personality=data.get("personality", "You are a helpful personal AI.").strip(),
        languages=[str(l).strip() for l in languages if str(l).strip()],
        humor=_clamp(humor, 0, 100),
        voice=str(overrides.get("voice", data.get("voice", "female"))).strip() or "female",
        model=data.get("model", "qwen2.5:14b"),
        ollama_host=data.get("ollama_host", "http://localhost:11434"),
        history_limit=int(data.get("history_limit", 20)),
        temperature=float(data.get("temperature", 0.7)),
        host=data.get("host", "0.0.0.0"),
        port=int(data.get("port", 8080)),
    )
