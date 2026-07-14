"""Offline test for Nero's opportunistic voice warmup."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import nero_voice_warmup as warmup


def test_warmup_is_hard_disabled_even_with_legacy_settings():
    config = {
        "voice_enabled": True,
        "desktop_voice_warmup": True,
        "endpoint": "http://127.0.0.1:8080/api/speak",
    }
    with (
        patch.object(warmup, "load_config", return_value=config),
        patch.object(warmup, "synthesize", return_value=b"RIFFaudio") as synthesize,
    ):
        result = warmup.warm_voice()
    assert result["warmed"] is False
    assert "hard-disabled" in result["reason"]
    synthesize.assert_not_called()


if __name__ == "__main__":
    test_warmup_is_hard_disabled_even_with_legacy_settings()
    print("  OK test_warmup_is_hard_disabled_even_with_legacy_settings")
