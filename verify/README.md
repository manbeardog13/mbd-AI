# Nero — Verification System

Per the [Development Directive](../docs/DIRECTIVE.md): **no feature is complete
until it can verify itself automatically**, and **your local PC is the source of
truth.** Every subsystem ships a `verify_<subsystem>.py` here.

## Run everything

Inside the project's virtualenv (so `app` imports resolve):

```bash
# Windows
.venv\Scripts\python verify\verify_everything.py

# macOS / Linux
.venv/bin/python verify/verify_everything.py
```

It runs every `verify_*.py` and prints a summary.

## The contract

Each `verify_*.py` is a standalone script that prints human-readable checks and
exits with:

| Exit code | Meaning |
|-----------|---------|
| `0` | **pass** |
| `2` | **skip** — not applicable on this machine (e.g. `verify_gpu` in a CPU-only cloud box) |
| other | **fail** — with an exact fix-it line |

`verify_everything.py` fails the run only if something actually **failed**;
skips are fine.

## Current checks

| Script | What it verifies |
|--------|------------------|
| `verify_config.py` | `config.yaml` loads cleanly (name, model, humor, goals, principles) |
| `verify_gpu.py` | NVIDIA GPU present + VRAM (skips on CPU-only machines) |
| `verify_ollama.py` | Ollama installed, running, and Nero's model pulled |

## Coming as each subsystem lands

`verify_embeddings.py` · `verify_memory.py` · `verify_reflection.py` ·
`verify_voice.py` · `verify_vector_db.py` · `verify_context.py` ·
`verify_tools.py` · `verify_scheduler.py` · `verify_performance.py`

Each new subsystem adds its script here and to the table above — that's part of
its Definition of Done.
