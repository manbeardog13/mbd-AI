# Nero Development Directive

**Local-First Cognitive Operating System**

This is the governing philosophy for Nero. Every architectural and engineering
decision in this repository defers to it. It supersedes convenience.

> Treat this project as a long-term **cognitive operating system**, not merely an
> AI chatbot or desktop assistant. The cloud environment is only a development
> workspace. The **real runtime is the local Windows workstation** — dedicated
> NVIDIA GPU, Ollama, local storage, full hardware access. Optimize every
> decision for the local environment, not the cloud.

---

## Priorities (in this exact order)

1. **Reliability**
2. **Privacy**
3. **Intelligence**
4. **Speed**
5. **Extensibility**
6. **Maintainability**
7. **User Experience**

Every subsystem must improve one or more of these pillars. When two pillars
conflict, the higher one wins.

---

## Local-First Development

For any subsystem that depends on Ollama, GPU inference, embeddings, vector DBs,
speech recognition, TTS, filesystem access, desktop/browser automation, OCR,
vision models, or local APIs — **do not make the cloud the primary execution
target.** Instead, always deliver:

- production-ready code
- unit tests
- integration tests
- local validation scripts
- graceful fallbacks
- setup scripts
- debugging commands
- performance benchmarks

**Every milestone concludes with a local verification procedure I can run on my
PC.** The local machine is always the source of truth.

---

## Definition of Done

Every completed subsystem must provide:

- ✓ Unit tests
- ✓ Integration tests
- ✓ Performance benchmarks
- ✓ Failure recovery
- ✓ Logging
- ✓ Metrics
- ✓ Documentation
- ✓ Local validation script (`verify_<subsystem>.py`)

**No feature is complete until it can verify itself automatically.**

---

## Verification Philosophy

Every subsystem gets a matching verification script under `verify/`:

```
verify_gpu.py          verify_ollama.py       verify_config.py
verify_embeddings.py   verify_memory.py       verify_reflection.py
verify_voice.py        verify_vector_db.py    verify_context.py
verify_tools.py        verify_scheduler.py    verify_performance.py
verify_everything.py   <- runs them all
```

Running

```bash
python verify/verify_everything.py
```

on the local PC validates Nero's major systems. Exit codes: `0` pass, `2` skip
(not applicable on this machine), anything else fail.

---

## Nero Is Not A Chatbot

Design Nero as a continuously running cognitive system. Conversation is only one
part of her cognition:

```
Perception → Context Collection → Memory Retrieval → World Model Update →
Planning → Tool Selection → Execution → Reflection → Learning →
Memory Update → Background Processing → (repeat)
```

### Continuous World Model
A persistent internal world state, updated continuously without being asked:
current project, goal, open apps, recent files, git branch/repo, system health,
tasks, deadlines, context, recently-learned information.

### Executive Functions
Cognitive modules that run *before* generating a response: planning,
prioritization, decision evaluation, scheduling, task decomposition, risk
assessment, progress tracking.

### Background Intelligence
Nero keeps working while I'm silent: refresh project summaries, compress
memories, update embeddings, find automation opportunities, review unfinished
work, check system health, index new files, update the knowledge graph, prepare
likely next actions. **Idle time is an opportunity for improvement.**

### Predictive Assistance
Favor anticipation over reaction. Open Unreal → prepare project context. Launch
VS Code → identify the active repo. Repeated manual work → suggest automation.
The objective is reducing friction.

---

## Memory Architecture

Multiple layers: working, conversation, session, semantic, procedural, episodic,
preference, long-term, and a knowledge graph. **Every memory includes:**
confidence, importance, timestamp, source, last-reinforced, decay rate, and
related memories. Memories strengthen or weaken over time.

### Insight Engine
Don't merely remember — continuously analyze. Periodically ask: what recurring
problems exist? what repetitive work? what patterns? what could be automated?
what should be recommended? **Generate insights, not isolated memories.**

### Experience Database
Store outcomes, not only facts ("Library X caused perf issues", "Framework Y cut
build time"). Experience influences future decisions.

### Self Reflection
After meaningful work: evaluate success, measure confidence, identify mistakes,
update strategy, store lessons. Reflection improves Nero over time.

### Personal Knowledge Graph
Connect information: projects ↔ files ↔ technologies ↔ conversations ↔ goals ↔
long-term objectives. Knowledge forms relationships, not isolated notes.

---

## Skills Architecture

Capabilities are modular skills. Each declares: capabilities, required context,
required permissions, dependencies, performance metrics, learning history, known
failure modes, and a self-test procedure. Skills evolve independently.

---

## Trust & Transparency

Every internal decision keeps metadata: confidence, reasoning depth, memory
sources, retrieved context, execution time, tool usage, freshness, assumptions.
Hidden by default; surfaced on request.

---

## Local AI Ecosystem

Use the best model for each task rather than forcing one model into every role:
conversation, reasoning, embedding, vision, speech recognition, TTS, OCR,
automation, reflection, planning.

---

## Engineering Standards

- Favor **modularity** over shortcuts.
- Favor **explicitness** over hidden behavior.
- Favor **observability** over assumptions.
- Favor **long-term maintainability** over temporary convenience.
- Every subsystem exposes logs, metrics, and health information.

### Continuous Self-Improvement
Regularly analyze latency, memory quality, retrieval accuracy, failure
frequency, automation opportunities, prompt effectiveness, and architecture
bottlenecks — and propose improvements proactively.

---

## The Development Principle

> Whenever multiple implementation options exist, choose the one that would still
> make sense if Nero grows into a **multi-year personal cognitive operating
> system used every day**. Never optimize only for today's milestone.

The objective is not an assistant that answers questions. The objective is a
**trusted cognitive partner** that continuously understands, learns, plans,
assists, and grows — while remaining **private, local-first, and
architecturally excellent**.
