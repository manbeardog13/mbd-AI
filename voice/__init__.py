"""Nero voice package — presentation-layer voice architecture.

Home for the future Voice Director, engine adapters, casting logic, and
audio effects. See docs/adr/0009-voice-rendering-and-backend-architecture.md
for the design proposal this package implements incrementally.

Nothing in this package is imported by app/tts.py, app/main.py, or the
current production voice path — those remain untouched during migration.
"""
