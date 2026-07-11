# Choosing Niro's Brain (the model)

Niro's intelligence comes from the model it runs. The rule of thumb:

> **More parameters = smarter, but needs more GPU memory (VRAM).**

The magic of this project is that the brain is swappable. Pick a bigger model
as your hardware allows, and Niro instantly gets smarter — everything else
(memory, voice, personality, remote access) stays exactly the same. As new,
stronger models are released, you just pull them and point Niro at them.

---

## First: how much VRAM do you have?

Your NVIDIA card's VRAM is the single number that decides how big you can go.

- **Windows:** Task Manager → *Performance* → *GPU* → **"Dedicated GPU memory"**.
- **Any OS with drivers:** run `nvidia-smi` — look at the total memory (e.g.
  `12288MiB` = 12 GB).

---

## Pick your model by VRAM

These use Ollama's default quantized builds (a good quality/size balance). Pull
the one for your tier, then set it in `config.yaml`.

| Your VRAM | Recommended model | Roughly needs | Why |
|-----------|-------------------|---------------|-----|
| **≤ 8 GB**  | `qwen2.5:7b` or `llama3.1:8b` | ~5–6 GB | Fast, genuinely capable. The safe sweet spot. |
| **10–12 GB** | `qwen2.5:14b` | ~9–10 GB | A clear step up in reasoning and knowledge. |
| **16 GB**   | `qwen2.5:14b` (comfortable) | ~10 GB | Runs 14B with headroom and long context. |
| **24 GB+**  | `qwen2.5:32b` | ~20 GB | Excellent — the smartest that fits a single big card. |

> **48 GB+ (or dual GPUs):** you can run `llama3.1:70b` (~40 GB) for near
> flagship-level quality.

Newer/stronger models come out constantly — browse **https://ollama.com/library**
and pull any chat/instruct model the same way. Bigger number of "b" (billions)
= smarter but heavier.

---

## How to switch models (30 seconds)

1. **Pull it** (downloads once):

   ```bash
   ollama pull qwen2.5:14b
   ```

2. **Point Niro at it** — edit `config.yaml`:

   ```yaml
   model: "qwen2.5:14b"
   ```

3. **Restart** Niro (`Ctrl+C`, then `python run.py` again).

The first message after a switch is a little slow while the model loads into
your GPU; after that it's fast.

---

## Tuning tips

- **Watch it use the GPU:** run `nvidia-smi` while Niro is replying — you should
  see GPU memory used and activity. If it barely touches the GPU, the model may
  be too big and is falling back to CPU (slow) — drop to a smaller one.
- **Higher-quality quant:** tags like `qwen2.5:14b-instruct-q5_K_M` are a bit
  sharper but use more VRAM. The default tag is fine to start.
- **Speed vs. smarts:** if replies feel slow, go one size down; if the machine
  has headroom, go one size up. You can change it any time.
- **Context length:** bigger models with spare VRAM can hold more of your
  conversation in mind. We'll expose this setting as Niro grows.
