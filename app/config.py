"""Loads your configuration from config.yaml.

On first run, if config.yaml doesn't exist yet, it's created by copying
config.example.yaml. That keeps your personal settings out of git while
still shipping sensible defaults.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
EXAMPLE_PATH = ROOT / "config.example.yaml"


@dataclass
class Config:
    """Everything that makes the AI *yours* — identity, brain, and server."""

    ai_name: str
    owner_name: str
    personality: str
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
        print(f"  Created {CONFIG_PATH.name} from the example. Edit it to make the AI yours.")


def load_config() -> Config:
    """Read config.yaml fresh. Called on each message so edits apply live."""
    ensure_config()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return Config(
        ai_name=data.get("ai_name", "Niro"),
        owner_name=data.get("owner_name", "friend"),
        personality=data.get("personality", "You are a helpful personal AI.").strip(),
        model=data.get("model", "llama3.1:8b"),
        ollama_host=data.get("ollama_host", "http://localhost:11434"),
        history_limit=int(data.get("history_limit", 20)),
        temperature=float(data.get("temperature", 0.7)),
        host=data.get("host", "0.0.0.0"),
        port=int(data.get("port", 8080)),
    )
