# 🧠 mbd-AI — Your Personal, Local AI

> [!IMPORTANT]
> **Hosted-only lock (2026-07-14):** the standalone local Nero runtime and all
> launch paths are hard-disabled under ADR-0014. The local-runtime material
> below is retained as historical architecture only; do not run it. Nero's
> active interface is zero-start Codex Host Presence from the global capsule.

**Start here (humans and models):** the canonical knowledge base is
**[docs/canon/README.md](docs/canon/README.md)** — read order, master index,
standards, migration plan. The law is [docs/CONSTITUTION.md](docs/CONSTITUTION.md).

A private AI companion that runs **entirely on your own machine**, remembers
you, has its own personality, and is reachable from anywhere on any network —
without your data ever touching the cloud.

> The idea: build the **body and nervous system** (memory, personality,
> interface, remote access) once, and let the **brain** get smarter over time
> by swapping in better local models as they're released.

---

## What it does today (v0.1)

- 💬 **Natural chat** with a local model through a clean web app (phone + desktop)
- 🌐 **Bilingual** — understands and replies in **English *and* Croatian**, auto-detecting each message
- 😄 **Humor dial** — a live, TARS-from-Interstellar style slider from all-business to full comedian
- 🎙️ **Voice** — talk to it and hear it back; hands-free conversation mode (in English or Croatian)
- 🗣️ **"Hey Siri, ask Nero…"** — an iPhone Siri Shortcut for true hands-free access
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

**The one-command way** (Windows / macOS / Linux) — sets up everything and launches Nero:

```bash
git clone https://github.com/manbeardog13/mbd-AI.git
cd mbd-AI
python bootstrap.py
```

`bootstrap.py` creates the environment, installs dependencies, checks that
Ollama is installed and running, downloads Nero's brain, and starts him — with
clear fix-it steps if anything's missing. Then open **http://localhost:8080**.

> New to this / on Windows without Python or Ollama yet? The full click-by-click
> guide is in **[docs/SETUP.md](docs/SETUP.md)**. After the first setup, just run
> **`start.bat`** (Windows) or **`./start.sh`** (macOS/Linux) to launch Nero.

<details>
<summary>Prefer to set it up by hand?</summary>

```bash
ollama pull qwen3:14b     # see docs/MODELS.md to match your GPU
python -m venv .venv
# Windows:  .venv\Scripts\activate     macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

</details>

- Make it yours → edit **`config.yaml`** (name, personality, model).
- Talk to it / "Hey Siri" → **[docs/VOICE_AND_SIRI.md](docs/VOICE_AND_SIRI.md)**.
- Reach it from anywhere → **[docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md)**.
- Keep it always on → **[docs/ALWAYS_ON.md](docs/ALWAYS_ON.md)**.

## Project layout

```
mbd-AI/
├── bootstrap.py           # one-command setup & launch
├── start.bat / start.sh   # quick relaunch (Windows / macOS-Linux)
├── run.py                 # runs the server directly
├── config.example.yaml    # template; copied to config.yaml on first run
├── requirements.txt
├── app/
│   ├── main.py            # web server + API
│   ├── config.py          # loads your settings (+ live humor override)
│   ├── db.py              # memory: conversations + facts (SQLite)
│   ├── llm.py             # streams from your local Ollama model
│   ├── prompt.py          # builds Nero's identity, languages & humor
│   └── static/            # the web app (HTML/CSS/JS)
├── verify/                # self-check scripts — `python verify/verify_everything.py`
└── docs/                  # setup, models, voice/Siri, remote access, DIRECTIVE, VISION
```

## Where this is going (the roadmap)

> The full architecture — turning Nero from a chatbot into a **cognitive
> companion** (layered memory, identity, reflection, world model, continuity) —
> is mapped in **[docs/VISION.md](docs/VISION.md)**. A living snapshot of the
> current state (and open questions) lives in
> **[docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md)**. The governing philosophy —
> local-first, verification-first — is in **[docs/DIRECTIVE.md](docs/DIRECTIVE.md)**.


- [x] **Voice** — talk to it and hear it back (in-app + Siri Shortcut)
- [x] **Bilingual** (English + Croatian) and a live **humor dial**
- [ ] **Studio-quality local voice** — a fully-offline neural voice (Piper) for a smoother, "glassier" Nero
- [ ] **Automatic memory** — the AI decides on its own what's worth remembering
- [ ] **Multiple conversations** with a browsable history sidebar
- [ ] **Tools** — let it search your files, run tasks, check the weather, etc.
- [ ] **Smarter retrieval** — semantic search over everything it knows (embeddings)
- [ ] **Bigger brains** — plug in larger/newer local models as your hardware allows

Built step by step. This is v0.1 — the foundation everything else grows from.
