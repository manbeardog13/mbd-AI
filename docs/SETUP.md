# Setup Guide

> [!IMPORTANT]
> **Historical only:** this local setup path is hard-disabled under ADR-0014.
> Do not install, start, or configure Ollama, local models, the project server,
> or local voice for Nero. Use zero-start Codex Host Presence instead.

Getting your personal AI running on your NVIDIA PC. Takes about 15 minutes.

---

## 1. Install Ollama (the engine that runs the model)

Ollama runs the language model on your GPU and handles all the heavy lifting.

1. Download it from **https://ollama.com/download** and install.
2. Ollama runs in the background automatically. Confirm it works:

   ```bash
   ollama --version
   ```

### Pull a model (the "brain")

Your GPU's VRAM decides how big a model you can run. Bigger = smarter but heavier.

```bash
ollama pull qwen3:14b     # Nero's default brain, great on a 10–12 GB GPU
```

Pick the right size for your card (full guide in **[MODELS.md](MODELS.md)**):

| Model             | Approx VRAM | Notes                                  |
|-------------------|-------------|----------------------------------------|
| `qwen3:8b`      | ~5 GB       | Fast, capable (8 GB cards)             |
| `qwen3:14b`     | ~9–10 GB    | Noticeably smarter (**the default**)   |
| `qwen3:32b`     | ~20 GB      | Excellent, if you have 24 GB+          |

> Not sure how much VRAM you have? On Windows, open Task Manager → Performance →
> GPU. Or run `nvidia-smi` in a terminal.

Test the model directly (optional):

```bash
ollama run qwen3:14b "Say hello in one sentence."
```

---

## 2. Install Python

You need **Python 3.10 or newer**. Check:

```bash
python --version
```

If you don't have it, get it from **https://python.org/downloads** (on Windows,
tick *"Add Python to PATH"* during install).

---

## 3. Set up this project

From the `mbd-AI` folder:

```bash
# Create an isolated environment for the project's dependencies
python -m venv .venv

# Activate it:
#   Windows (PowerShell):
.venv\Scripts\Activate.ps1
#   Windows (Command Prompt):
.venv\Scripts\activate.bat
#   macOS / Linux:
source .venv/bin/activate

# Install the dependencies
pip install -r requirements.txt
```

---

## 4. Run it

```bash
python run.py
```

You'll see something like:

```
  ── Nero ──
  Brain:  qwen3:14b  (via Ollama at http://localhost:11434)
  Open:   http://localhost:8080
```

Open **http://localhost:8080** in your browser and start chatting. The dot in
the top-left turns **green** when it's connected to your model.

---

## 5. Make it yours

Open **`config.yaml`** (created automatically on first run) and edit:

- **`ai_name`** — what your AI is called
- **`owner_name`** — what it calls you
- **`personality`** — who it is and how it talks
- **`model`** — which Ollama model it thinks with

Restart `python run.py` after changing the name or model. Personality and
memories reload automatically on the next message.

You can also add long-term **memories** right in the web app's left panel —
facts about you it should always keep in mind.

---

## Troubleshooting

**Status dot is red / "Can't reach Ollama"**
Make sure Ollama is running (open the Ollama app, or run `ollama serve`).

**"model … isn't installed"**
Run `ollama pull <model-name>` for whatever is set in `config.yaml`.

**Port 8080 already in use**
Change `port:` in `config.yaml` to something else, e.g. `8090`.

**It's slow**
Try a smaller model (e.g. `llama3.1:8b`), and confirm Ollama is using your GPU
(`nvidia-smi` should show activity while it's replying).

---

Next: reach your AI from anywhere → **[REMOTE_ACCESS.md](REMOTE_ACCESS.md)**.
