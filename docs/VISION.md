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
  then add semantic (embedding) search as the store grows.

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

| # (from the brief) | Capability | Phase | Value | Effort |
|---|---|---|---|---|
| 4, 7, 16 | **Identity file: persona + goals + principles** | **Next** | ★★★ | Low |
| 1, 11 | **Layered memory: types, confidence, decay** | **Next** | ★★★ | Med |
| 3 (reflect) | **Automatic memory via reflection** (she decides what to keep) | **Next** | ★★★ | Med |
| 12 | Confidence-based answering | Next | ★★☆ | Low |
| 10 | Intelligent silence / live status | Next | ★★☆ | Low |
| 15 | **World model** (continuity) | Soon | ★★★ | Med |
| 3 (full loop) | The full cognitive loop wiring | Soon | ★★★ | Med |
| 8 | Tool planner (once tools exist) | Soon | ★★★ | Med-High |
| 18 | Skills plugin system | Soon | ★★★ | Med |
| 17 | Observability dashboard | Soon | ★★☆ | Med |
| 6, 5, 14 | Desktop senses + proactivity + attention | Later | ★★★ | High |
| 2 | Internal state variables (curiosity/urgency…) | Later | ★☆☆ | Low |
| 13 | Slow personality drift | Later | ★★☆ | Med |

**Deliberately deferred / treated with caution:**
- *Internal "emotion" variables (#2)* — cheap to add but easily gimmicky; only
  worth it if they visibly improve responses.
- *Full desktop sensing & proactivity (#5, #6, #14)* — the biggest "alive"
  payoff, but also the biggest privacy surface. Opt-in, local-only, and only
  after the memory/identity core is solid.

---

## What's already built (v0.1 foundation)

Identity basics (name, personality, humor dial, languages), a first memory layer
(conversations + a facts store injected into every reply), voice in/out, local
private inference, and remote access. The vision above is how that foundation
grows into a companion — one phase at a time.
