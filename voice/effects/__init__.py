"""Presentation-layer audio effects for Nero's voice.

Each effect module exposes a pure function:  fn(samples, sample_rate, cfg) -> samples

Effects are OFF by default and only invoked when a voice profile explicitly
requests them. They never modify Kokoro's synthesis behavior; they are pure
post-processing on the WAV samples.
"""
