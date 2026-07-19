"""Language detection + profile-compatibility helpers.

The Voice Director owns language routing (per the Phase-3 direction: "The
Brain should not know language-specific implementation details"). This
module provides the primitives; the Director uses them to decide whether
a given voice profile can voice a given text.

Kept intentionally small — a diacritic-based heuristic is enough for the
en / hr distinction Nero actually has. If more languages join (or more
disambiguation is needed) this is the one place to grow.
"""
from __future__ import annotations

import re
from typing import Any

# Croatian diacritics that don't appear in English. Sufficient signal —
# any of these in the text means "this is Croatian, not English."
_CROATIAN_RE = re.compile(r"[čćđšž]", re.IGNORECASE)


def detect_language(text: str) -> str:
    """Return a BCP-47-like language tag guessed from `text`.

    Heuristic: Croatian diacritics -> "hr-HR". Otherwise "en-US".
    Deliberately conservative — the goal is to reject non-English text
    when the active profile can only voice English, not to be an LID model.
    """
    if not text:
        return "en-US"
    if _CROATIAN_RE.search(text):
        return "hr-HR"
    return "en-US"


def _lang_prefix(tag: str | None) -> str:
    """'en-us' -> 'en', 'hr-HR' -> 'hr', None -> ''. Used only for comparison."""
    if not tag:
        return ""
    return tag.split("-", 1)[0].strip().lower()


def profile_supports_text(profile: Any, text: str) -> bool:
    """True iff `profile.lang`'s primary tag matches the detected language of `text`.

    `profile` is duck-typed — anything with a `.lang` attribute (typically a
    ``VoiceProfile`` from ``voice.profiles``). Kept loose so this module has
    no cycle with the profile package.
    """
    detected = detect_language(text)
    return _lang_prefix(detected) == _lang_prefix(getattr(profile, "lang", None))
