<!--
  Provenance: authored by Toni; adopted verbatim below as Nero's governing voice
  spec. The content under "# NERO VOICE SYSTEM V1.0" is unmodified — do not edit
  it in place; changes to the plan go through Toni.
-->
> **Status — adopted, not yet built.** Voice is a **Phase 4** capability
> ([ROADMAP.md](ROADMAP.md)); this is its canonical, governing plan ("the
> Bible"). When Phase 4 begins, the detailed design (an ADR + a Phase-4 design
> doc) is *derived from* this and must not deviate from it.
>
> **Build-order guidance (Toni, non-negotiable):** do **not** chase perfect TTS
> before the voice pipeline exists. Get the architecture working first with a
> decent local voice (Kokoro is already shipped), then iterate. The magic is the
> **Voice Director + personality system** — that's what turns a voice engine into
> Nero.
>
> **Fits the Constitution:** "the TTS engine is replaceable, the personality is
> not" mirrors ADR-0002 (the model is a replaceable component) and the Capability
> Registry seam (ADR-0007); local-first / privacy / offline are already pillars.
> No governance conflict — adopted as written.

---

# NERO VOICE SYSTEM V1.0

## Local-First Cinematic Voice Architecture

## Mission

Create the voice identity system for NERO.

The objective is not simply adding text-to-speech.

The objective is creating a **cinematic AI personality system**.

NERO should feel like a premium companion from a AAA game, sci-fi universe, or futuristic command center.

The voice is a core part of NERO's identity.

However, the architecture must remain:

* 100% local
* zero recurring costs
* privacy-first
* offline capable
* GPU optimized for RTX 4070 12GB
* modular and future-proof

Do not design the system around paid cloud APIs.

Cloud voices such as ElevenLabs may be used only as external references during development, never as a dependency.

---

# PRIMARY RULE

## NERO must own the voice layer.

The voice engine is replaceable.

NERO's personality is not.

The architecture should allow:

```text
NERO Brain

        ↓

Voice Director

        ↓

Voice Personality

        ↓

TTS Engine

        ↓

Audio Output
```

The TTS model should be a replaceable component.

Future engines should be interchangeable without modifying Nero's core.

---

# VOICE ARCHITECTURE

Create a dedicated Voice System module.

Suggested structure:

```text
voice/

├── manager/
│
├── personalities/
│
├── profiles/
│
├── emotion/
│
├── effects/
│
├── local_tts/
│
├── cache/
│
└── audio/
```

---

# VOICE DIRECTOR

Implement a Voice Director responsible for choosing:

* voice personality
* emotional state
* speaking speed
* intensity
* pauses
* effects
* delivery style

The LLM should not directly control TTS.

Instead:

Example:

Input:

"The build has failed."

Voice Director converts it into:

```json
{
"voice":"nero_sentinel",
"emotion":"serious",
"pace":"slow",
"authority":0.9,
"warmth":0.2,
"effect":"subtle_system_alert"
}
```

The TTS engine receives structured instructions.

---

# LOCAL TTS ENGINE

Prioritize free local models.

Evaluate and implement the best option available for RTX 4070.

Candidate technologies:

## Kokoro TTS

Primary candidate.

Requirements:

* fast inference
* natural speech
* low VRAM usage
* suitable for daily conversation

## XTTS v2

Evaluate for:

* voice cloning
* character voices
* multilingual support

## Piper

Use where extreme speed is needed.

## Croatian Support

Evaluate:

* Meta MMS-TTS
* Croatian-compatible neural models
* multilingual XTTS capabilities

The Croatian voice quality must be treated as a first-class feature.

---

# VOICE PERSONALITY FRAMEWORK

Do not create one voice.

Create a cast.

Every personality requires:

* name
* purpose
* emotional profile
* speaking style
* preferred situations
* example phrases
* audio effects profile

---

# INITIAL NERO VOICE CAST

## 1. NERO PRIME

Default voice.

Purpose:

Daily interaction.

Personality:

Trusted AI companion.

Characteristics:

* intelligent
* warm
* calm
* precise
* futuristic
* human

Reference:

High-budget sci-fi companion.

Example:

"Good evening, Toni. Nero is online."

"Your workspace is ready."

"I have analyzed the available options."

---

## 2. NERO COMMANDER

Purpose:

Productivity mode.

Personality:

Strategic commander.

Characteristics:

* authority
* confidence
* discipline
* calm leadership

Never aggressive.

A true commander does not need to shout.

Example:

"Analysis complete. The optimal path has been identified."

---

## 3. NERO SHADOW

Purpose:

Late-night coding.

Personality:

Quiet genius.

Characteristics:

* lower energy
* focused
* mysterious
* analytical

Example:

"I found the issue. The problem was not the code. It was the assumption."

---

## 4. NERO SENTINEL

Purpose:

Security and warnings.

Personality:

Guardian.

Characteristics:

* serious
* precise
* protective

Example:

"Confirmation required. This action modifies system files."

---

## 5. NERO ORACLE

Purpose:

Research and creative thinking.

Personality:

Ancient intelligence.

Characteristics:

* elegant
* thoughtful
* philosophical

Example:

"The answer was hidden beneath the obvious."

---

## 6. NERO DEMON

Purpose:

Entertainment mode only.

Personality:

Ancient powerful entity.

Important:

Do not create a childish monster voice.

Create:

* intelligent
* charismatic
* intimidating
* humorous

Imagine:

An ancient warlord who decided to help manage your computer.

Example:

"The task is complete.

The machine resisted.

The machine failed."

Optional effects:

* subtle distortion
* deep resonance
* ancient chamber reverb
* cinematic darkness

---

# FEMALE VOICES

Create equally detailed female personalities.

---

# NERO LUNA

Purpose:

Companion mode.

Characteristics:

* warm
* natural
* supportive
* human

Example:

"Everything is ready. We can continue whenever you are."

---

# NERO AURELIA

Purpose:

Female commander.

Characteristics:

* elegant
* strategic
* powerful
* calm authority

Example:

"The situation has been analyzed. I recommend the following approach."

---

# NERO VALKYRIE

Purpose:

Warrior personality.

Characteristics:

* fearless
* determined
* heroic

Example:

"The path ahead is difficult.

Good.

Difficult paths create stronger outcomes."

---

# NERO ECLIPSE

Purpose:

Mystery mode.

Characteristics:

* futuristic
* intelligent
* almost supernatural

Example:

"The pattern has revealed itself."

---

# EMOTION SYSTEM

NERO must not read every sentence identically.

Create emotional parameters:

```json
{
"warmth":0.5,
"authority":0.7,
"energy":0.4,
"mystery":0.2,
"humor":0.1,
"urgency":0.3
}
```

Different situations change delivery.

Examples:

Normal:

"The download is complete."

Commander:

"Download complete. All systems are operational."

Demon:

"The transfer is complete. Another victory."

---

# AUDIO EFFECT SYSTEM

Create optional effects.

Effects must enhance personality, never damage clarity.

Examples:

## Activation

Prime:

soft futuristic startup

Commander:

deep system initialization

Demon:

ancient awakening

## Success

Achievement-style audio cue.

Premium.

Subtle.

Not childish.

## Warning

Security pulse.

## Discovery

Small "new knowledge acquired" sound.

Inspired by games, but original.

---

# VOICE CACHE

Implement audio caching.

If Nero repeatedly says:

"Good morning, Toni."

Do not regenerate.

Store:

* common greetings
* confirmations
* status messages
* errors
* system notifications

This improves speed and reduces GPU usage.

---

# STREAMING VOICE

NERO should not wait for the entire answer.

Pipeline:

```text
Generate text

↓

Split into sentences

↓

Generate audio immediately

↓

Play while next sentence generates
```

Goal:

First sound within milliseconds.

---

# INTERRUPT SYSTEM

Voice must be interruptible.

If user speaks:

"Actually..."

NERO immediately stops speaking.

The conversation should feel natural.

---

# VOICE SELECTION UI

Create a game-inspired selector.

Each voice card displays:

Name

Role

Authority

Warmth

Energy

Humor

Mystery

Preview button

Example:

```text
NERO COMMANDER

Strategic AI

Authority ████████░░

Warmth █████░░░░░

Energy ███████░░░

[Preview]
[Select]
```

---

# PERFORMANCE REQUIREMENTS

RTX 4070 optimization:

Monitor:

* VRAM
* GPU load
* CPU load
* inference time

Priorities:

Conversation responsiveness first.

Background generation second.

Never allow voice generation to freeze Nero.

---

# FUTURE COMPATIBILITY

The architecture should allow future additions:

* better local TTS models
* voice cloning
* emotion models
* real-time conversation
* multilingual voices
* singing/creative voices
* custom user voices

---

# FINAL OBJECTIVE

The final result should not feel like:

"Text-to-speech added to an AI."

It should feel like:

"I built a character."

NERO's voice should become recognizable.

A user should hear one sentence and immediately know:

That is Nero.

Build the foundation correctly.

Prioritize personality, speed, immersion, and local independence above everything else.
