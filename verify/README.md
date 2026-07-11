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

| Script | What it verifies | Needs Ollama? |
|--------|------------------|:---:|
| `verify_config.py` | `config.yaml` loads cleanly (name, model, humor, goals, principles) | no |
| `verify_gpu.py` | NVIDIA GPU present + VRAM (skips on CPU-only machines) | no |
| `verify_ollama.py` | Ollama installed, running, and Nero's model pulled | — |
| `verify_memory.py` | Memory storage, decay, ranking, dedup, parsing (offline self-test) | no |
| `verify_world_model.py` | World state upsert/merge/clear, parsing, rendering (offline self-test) | no |
| `verify_embeddings.py` | Local embeddings (`nomic-embed-text`) return vectors | yes |
| `verify_reflection.py` | Nero extracts a memory from a sample exchange | yes |
| `verify_tts.py` | Nero's local neural voice synthesizes a playable WAV (skips if the optional voice deps aren't installed) | — |

The `no`/offline checks pass on any machine (including CI); the `yes` checks
skip when Ollama isn't running and pass on your PC once it is.

## Coming as each subsystem lands

`verify_voice.py` · `verify_vector_db.py` · `verify_context.py` ·
`verify_tools.py` · `verify_scheduler.py` · `verify_performance.py`

Each new subsystem adds its script here and to the table above — that's part of
its Definition of Done.
