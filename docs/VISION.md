# Nero — Vision & Architecture

> From a chatbot to a **cognitive companion**. The model is just the brain;
> what makes Nero feel *alive* is the mind we build around it — memory,
> identity, reflection, a world model, and continuity.
>
> **North Star:** *continuity.* The best companions aren't the ones with the
> biggest models — they're the ones that wake up already knowing what you were
> working on and how to quietly help. We optimize for that.

Because Nero's brain is swappable (see [MODELS.md](MODELS.md)), this
architecture holds whether she's running a 14B model today or something far
larger later. We build the mind once; the brain keeps getting better.

---

## The cognitive loop (the centerpiece)

Instead of `Input → LLM → Output`, every meaningful interaction flows through a
loop. Not all steps run every turn — cheap turns short-circuit — but the shape
is always this:

```
   Perceive  →  Understand  →  Retrieve memories  →  Update world model
      ↑                                                      ↓
   Learn  ←  Reflect  ←  Act  ←  Choose tools  ←  Plan  ←────┘
```

- **Perceive / Understand** — parse the message (and later, context signals).
- **Retrieve** — pull relevant memories (semantic, episodic, preferences).
- **World model** — update the running picture of what's going on right now.
- **Plan / Tools / Act** — decide, optionally use tools, respond.
- **Reflect / Learn** — quietly ask *did I help? should I remember this?* and
  update memory. **Reflection is what makes her grow.**

---

## Memory has layers

Humans don't remember everything or nothing. Nero's memory is tiered:

| Layer | Lifetime | Example |
|-------|----------|---------|
| **Working** | current turn | what we're talking about right now |
| **Session** | since launch | the thread of this conversation |
| **Long-term** | persistent | things Nero decided are worth keeping |
| **Semantic** | persistent | facts about you ("you're building Nero") |
| **Episodic** | persistent | things you did together ("we set up voice on the 11th") |
| **Preference** | persistent | how you like things ("prefers dark UI, short answers") |

Each long-term memory carries metadata:

```
memory:  "Toni prefers concise answers"
type:    preference
confidence: 0.92
last_reinforced: 2026-07-11
```

- **Confidence** grows when reinforced, and memories **decay** if never touched
  again — so old, stale guesses fade instead of haunting her forever.
- **Automatic capture:** after important turns, Nero decides *herself* what's
  worth remembering (via reflection) — you shouldn't have to add facts by hand.
- **Retrieval:** start simple (inject the most relevant/confident memories),
  then semantic search via a local embedding model (**`nomic-embed`** through
  Ollama). If embeddings aren't available yet, fall back to confidence + recency
  so it always works.
- **Memories connect, not just accumulate.** Each memory carries the entities it
  mentions and a timestamp, so the flat store is already the seed of a
  **knowledge graph** (Toni → works on → ASC → written in → React) and a
  **timeline**. Some memories record *outcomes* ("animation lib X was too slow →
  avoid"), turning memory into experience. This shape is what later lets an
  **Insight Engine** find patterns across months.

---

## Identity is separate from knowledge

One file *is* Nero — her persona — kept apart from everything she learns:

```
name · pronouns · beliefs · speaking style · humor · languages
goals · principles · limitations · favorite phrases · things to avoid
```

Everything else (memories, world model) can evolve freely without changing
*who she is*. Today this lives in `config.yaml` (name, personality, humor,
languages); the next step promotes it to a first-class identity file.

### Goals (what she's for)

Every decision gets weighed against her goals, e.g.:

> Help Toni work faster · Protect Toni's data · Learn Toni's habits ·
> Reduce repetitive work · Never interrupt unnecessarily

### Principles (how she behaves) — not dozens of hard rules

> Don't waste Toni's time · Explain before acting · Never pretend ·
> Protect privacy · Ask when unsure · Be concise unless asked ·
> Remember what matters, forget what doesn't

---

## World model (continuity)

Nero maintains a small, continuously-updated picture instead of re-inferring it
every turn:

```
current project · current task · working directory · language/framework ·
git branch · deadline · what we did last · what's unfinished
```

This is the substrate of continuity — she resumes *knowing* where you left off.

---

## Presence: voice, confidence, and intelligent silence

People judge "smartness" mostly from conversational flow, not IQ.

- **Voice/flow:** fast responses, natural pacing, brevity. (Studio-quality local
  neural voice — Piper — is on the roadmap.)
- **Confidence-based answers:** speak certainty honestly — *"I know"* vs *"I
  think…"* vs *"I'd want to verify that."* Trust grows when uncertainty is named.
- **Intelligent silence:** when she's working for a few seconds, show a live
  status (*searching memory… checking calendar… done*) instead of freezing.

---

## Senses & proactivity (the desktop-companion leap)

Context is more than chat history. With permission, Nero can perceive: time,
active app, media playing, CPU/GPU load, battery, clipboard, recent files,
current project, calendar. An **attention system** scores each event's
importance and decides whether to act:

```
Discord ping      → 0.15 → ignore
New email         → 0.48 → mention later
GPU at 92°C       → 0.94 → interrupt now
```

This is powerful but heavy and privacy-sensitive — it needs a local OS agent and
careful, opt-in controls. It comes *after* the memory/identity core.

---

## Tools & planner

When Nero gains tools, a **planner** coordinates them instead of the model
trying to do everything in its head:

```
"Make me a presentation" → plan → search notes → generate images →
write slides → export PPTX → open PowerPoint → "it's ready"
```

The model becomes a **coordinator**, not a one-shot oracle.

---

## Skills: Nero as an OS, not a prompt

Long-term, capabilities are **plug-in skills** (email, coding, research, home
automation, Blender/Unreal/Photoshop companions, gaming buddy…). Each skill
declares the tools it uses, the context it needs, when it activates, and its
specialized prompts. The core stays clean; the surface grows.

---

## Observability (don't fly blind)

A developer dashboard most hobby projects skip: memory hits, current plan,
reasoning duration, model latency, active goals, attention scores, running
tools, queued tasks, current context, CPU/GPU/RAM, token usage. Debugging a
"mind" is impossible without a window into it.

---

## Roadmap — honest sequencing

Value/effort are my engineering estimates. We build in phases; each phase is its
own PR so we stay in control.

| Capability | Phase | Value | Effort |
|---|---|---|---|
| Identity file: persona + goals + principles | ✅ done | ★★★ | Low |
| Confidence-based answering | ✅ done | ★★☆ | Low |
| Layered memory (types · confidence · decay · entities) | ✅ done | ★★★ | Med |
| Automatic memory via reflection | ✅ done | ★★★ | Med |
| Semantic retrieval via `nomic-embed` (graceful fallback) | ✅ done | ★★★ | Med |
| **World model / continuity** (resume knowing where you left off) | **Building** | ★★★ | Med |
| Confidence *by source* (explicit / observed / inferred / guessed) | Next | ★★★ | Low |
| Intelligent silence / live "thinking…" status | Next | ★★☆ | Low |
| Tool system + planner (executive functions) | Soon | ★★★ | Med-High |
| Local voice pipeline (Piper/Kokoro) — interruptible, barge-in | Soon | ★★★ | Med-High |
| **Concept Engine + Identity Graph** ("understand", not just "remember") | Soon ★ | ★★★ | Med-High |
| Initiative Engine (scored proactivity: importance/novelty/urgency/cost) | Soon | ★★★ | Med |
| Insight Engine + **weekly self-improvement report** | Soon ★ | ★★★ | Med-High |
| Memory compression (100 convos → themes → lessons → personality model) | Soon | ★★★ | Med |
| Dream Cycle 🌙 (idle overnight consolidation) | Soon | ★★★ | Med |
| Relationship / knowledge graph | Soon | ★★★ | Med |
| Observability dashboard + World-Model Viewer (dev mode) + trust layer | Soon | ★★☆ | Med |
| Desktop-companion UI (Home dashboard · Memory Explorer · living background) | Soon | ★★★ | High |
| Internal monologue (hidden planning before answering) | Soon | ★★☆ | Low |
| Desktop senses + attention + background intelligence | Later | ★★★ | High |
| Multi-agent specialization · predictive assistance · digital twin | Later | ★★☆ | High |

★ = highest-leverage differentiators (per the second-opinion review).

**From the second-opinion review, adopted:** the *"understand > remember"* framing
(**Concept Engine** + **Identity Graph**), **confidence-by-source**, memory
compression, the **Dream Cycle**, **initiative scoring**, the weekly
**self-improvement report**, and a **desktop-companion UI** (Home dashboard,
Memory Explorer, World-Model Viewer). **Deliberately not adopted:** cloud voice
"during development" — it would break the local-first / privacy pillars. Voice is
prioritized sooner but stays **100% local** (Piper/Kokoro, not ElevenLabs/OpenAI).

---

## Nero 2.0 — the cognitive-OS horizon

The destination is bigger than an assistant: an **autonomous cognitive OS** you
trust more than your file explorer. That means background intelligence (she
works on your projects between conversations), predictive assistance (prepares
what you're about to need), desktop understanding (intent, not just process
names), a multi-agent inner team, and a **personal digital twin** of how you
work.

The **crown jewel** is an **Insight Engine** (the "Second Brain"): instead of
only storing memories, Nero periodically asks *what patterns am I seeing? what
recurring problems does Toni have? what can I automate? what should I recommend
before he asks?* — and surfaces the answer at the right moment. That's the leap
from **recorder → advisor**.

**Discipline (why this is "horizon," not "now"):** almost all of the 2.0 layer
depends on two things we don't have yet — a solid **memory/knowledge core** and a
**privacy-safe local sensing layer**. Built too early, it becomes a sprawling,
half-working system (the very "scope explosion" the advice itself warns about).
So we build the core so it can *grow into* this, and gate the autonomous/sensing
layer behind it — opt-in, local-only, observable.

**Deliberately deferred / treated with caution:**
- *Background daemons, predictive & desktop sensing* — the biggest payoff and the
  biggest privacy/complexity surface. Only after the core is solid; always
  opt-in and local.
- *Internal "emotion"/state variables* — cheap but easily gimmicky; add only if
  they visibly improve responses.

---

## What's already built

**v0.1 foundation:** identity basics (name, personality, humor dial, languages),
a first memory layer (conversations + a facts store injected into every reply),
voice in/out, local private inference, remote access, one-command setup.

**Phase 1 — identity increment:** goals, principles, and confidence-based
answering are live. The **memory half** (layered memory, `nomic-embed` retrieval,
reflection) is being built now.

The vision above is how that foundation grows into a companion — one phase at a
time.
