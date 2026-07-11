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

    languages = data.get("languages") or ["English", "Croatian"]
    if isinstance(languages, str):
        languages = [languages]

    # Every field below is written to tolerate a present-but-blank key in
    # config.yaml (which YAML parses as None). `or` handles strings; `_num`
    # handles numbers (so a valid 0.0 temperature is NOT turned into a default).
    humor = _clamp(_num(overrides.get("humor", data.get("humor")), 75, int), 0, 100)

    return Config(
        ai_name=(data.get("ai_name") or "Nero"),
        owner_name=(data.get("owner_name") or "friend"),
        personality=(data.get("personality") or "You are a helpful personal AI.").strip(),
        languages=[str(l).strip() for l in languages if str(l).strip()],
        humor=humor,
        voice=(str(overrides.get("voice") or data.get("voice") or "female").strip() or "female"),
        model=(data.get("model") or "qwen2.5:14b"),
        ollama_host=(data.get("ollama_host") or "http://localhost:11434"),
        history_limit=_num(data.get("history_limit"), 20, int),
        temperature=_num(data.get("temperature"), 0.7, float),
        host=(data.get("host") or "0.0.0.0"),
        port=_num(data.get("port"), 8080, int),
    )
