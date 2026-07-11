# 🧠 mbd-AI — Your Personal, Local AI

A private AI companion that runs **entirely on your own machine**, remembers
you, has its own personality, and is reachable from anywhere on any network —
without your data ever touching the cloud.

> The idea: build the **body and nervous system** (memory, personality,
> interface, remote access) once, and let the **brain** get smarter over time
> by swapping in better local models as they're released.

---

## What it does today (v0.1)

- 💬 **Natural chat** with a local model through a clean web app (phone + desktop)
- 🎙️ **Voice** — talk to it and hear it back; hands-free conversation mode
- 🗣️ **"Hey Siri, ask Niro…"** — an iPhone Siri Shortcut for true hands-free access
- 🧠 **Runs locally** on your NVIDIA GPU via [Ollama](https://ollama.com) — fully offline, fully private
- 📝 **Remembers you** — conversations persist, plus a long-term "memory" of facts about you that shape every reply
- 🎭 **Its own personality** — a name and character you define
- 🌍 **Reachable anywhere** — securely, over [Tailscale](https://tailscale.com), from any network
- 📱 **Installable** — "Add to Home Screen" for a full-screen, app-like launch
- ⚡ **Streaming replies** — watch it think, token by token

## Architecture at a glance

```
   Your phone / laptop  ──(Tailscale, encrypted)──►  Your PC
                                                       │
                                        ┌──────────────┴───────────────┐
                                        │   mbd-AI  (this project)      │
                                        │                              │
                                        │   web app  ─►  FastAPI  ─►  Ollama (the brain)
                                        │                   │                            │
                                        │                   └─►  SQLite (memory)         └─ your GPU
                                        └──────────────────────────────┘
```

Nothing leaves your machine. Tailscale just lets *your own devices* reach it.

## Quick start

Full walkthrough in **[docs/SETUP.md](docs/SETUP.md)**. The short version:

```bash
# 1. Install Ollama from https://ollama.com, then pull Niro's brain:
ollama pull qwen2.5:14b     # see docs/MODELS.md to match your GPU

# 2. Set up this project:
python -m venv .venv
# Windows:  .venv\Scripts\activate     macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

# 3. Run it:
python run.py
```

Open **http://localhost:8080** and say hi.

- Make it yours → edit **`config.yaml`** (name, personality, model).
- Talk to it / "Hey Siri" → **[docs/VOICE_AND_SIRI.md](docs/VOICE_AND_SIRI.md)**.
- Reach it from anywhere → **[docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md)**.
- Keep it always on → **[docs/ALWAYS_ON.md](docs/ALWAYS_ON.md)**.

## Project layout

```
mbd-AI/
├── run.py                 # start here
├── config.example.yaml    # template; copied to config.yaml on first run
├── requirements.txt
├── app/
│   ├── main.py            # web server + API
│   ├── config.py          # loads your settings
│   ├── db.py              # memory: conversations + facts (SQLite)
│   ├── llm.py             # streams from your local Ollama model
│   ├── prompt.py          # builds the AI's identity/system prompt
│   └── static/            # the web app (HTML/CSS/JS)
└── docs/                  # setup, remote access, always-on guides
```

## Where this is going (the roadmap)

- [x] **Voice** — talk to it and hear it back (in-app + Siri Shortcut)
- [ ] **Automatic memory** — the AI decides on its own what's worth remembering
- [ ] **Multiple conversations** with a browsable history sidebar
- [ ] **Tools** — let it search your files, run tasks, check the weather, etc.
- [ ] **Smarter retrieval** — semantic search over everything it knows (embeddings)
- [ ] **Bigger brains** — plug in larger/newer local models as your hardware allows

Built step by step. This is v0.1 — the foundation everything else grows from.
