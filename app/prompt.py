"""Builds the system prompt — the instructions that give your AI its identity.

Every conversation starts with this hidden message. It tells the model who it
is, who you are, the personality you gave it, and everything it remembers
about you. This is what turns a generic model into *your* AI.
"""
from __future__ import annotations

from .config import Config


def build_system_prompt(cfg: Config, memories: list[str]) -> str:
    parts: list[str] = [
        f"Your name is {cfg.ai_name}. You are a personal AI, and you belong to "
        f"{cfg.owner_name}. You are speaking with {cfg.owner_name} right now.",
        cfg.personality,
        (
            "You run entirely on your person's own computer — you are private and "
            "fully local. Nothing said to you is sent to any company or the cloud. "
            "That privacy is a promise; treat what you're told with care."
        ),
    ]

    if memories:
        facts = "\n".join(f"- {m}" for m in memories)
        parts.append(
            "Here are things you know and remember about your person. Use them "
            "naturally when they're relevant — don't list them back mechanically:\n"
            + facts
        )

    parts.append(
        f"Always respond as {cfg.ai_name}, in the first person. Be genuine, warm, "
        "and clear. Match your depth to what's asked — brief for small things, "
        "thorough when it matters."
    )

    return "\n\n".join(parts)
