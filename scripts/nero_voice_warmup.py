"""Legacy Nero voice warmup, hard-disabled by hosted-only Host Mode."""
from __future__ import annotations

import json

from nero_host_voice import load_config, synthesize


HOSTED_ONLY_HARD_DISABLED = True
HOSTED_ONLY_REASON = "local Nero voice warmup is hard-disabled by hosted-only Host Mode"


def warm_voice() -> dict:
    if HOSTED_ONLY_HARD_DISABLED:
        return {"warmed": False, "reason": HOSTED_ONLY_REASON}
    config = load_config()
    if config.get("voice_enabled") is not True:
        return {"warmed": False, "reason": "voice-disabled"}
    if config.get("desktop_voice_warmup") is not True:
        return {"warmed": False, "reason": "warmup-disabled"}
    audio = synthesize("Ready.", str(config.get("endpoint", "")), timeout_seconds=120.0)
    return {"warmed": True, "bytes": len(audio)}


def main() -> int:
    try:
        result = warm_voice()
        print(json.dumps(result))
        return 0
    except Exception as exc:  # Warmup is opportunistic and must never block startup.
        print(json.dumps({"warmed": False, "reason": type(exc).__name__}))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
