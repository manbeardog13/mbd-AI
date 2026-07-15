# Nero ↔ Live2D Viewer — WebSocket Protocol v1

**Version:** 1
**Transport:** WebSocket (default `ws://127.0.0.1:3939/nero`)
**Encoding:** JSON, UTF-8
**Direction:** bidirectional, but Nero → Viewer is the load-bearing direction
**Reference implementation:** `presence/runtime_bridge/live2d.py`

The Presence Director (via `Live2DRuntime`) speaks this protocol to whatever
process is hosting the Cubism viewer — typically a small standalone app the
user runs alongside Nero, containing the loaded `.model3.json` character.

Nero **never** blocks on viewer availability. If the viewer isn't running,
the runtime keeps trying to connect with exponential backoff, and voice +
chat continue working normally. When the viewer comes online, the runtime
reconnects and resumes sending parameter frames.

---

## Message envelope

Every message on the wire is a single JSON object:

```json
{
  "v": 1,
  "kind": "<one of the message types below>",
  ...kind-specific fields...
}
```

- `v` — protocol version. Currently `1`. Consumers **must** check this and
  gracefully reject unknown versions (rather than parse-crashing).
- `kind` — the message type. See below.
- Additional fields depend on the `kind`.

Unknown fields must be **ignored, not rejected**. This is the additive
evolution rule that keeps the protocol upgradeable without breaking
existing viewers.

---

## Nero → Viewer

### `hello` (once per connection, immediately after connect)

Nero identifies itself and declares what parameters it expects the viewer's
model to expose. The viewer can compare against its loaded model and warn
about mismatches.

```json
{
  "v": 1,
  "kind": "hello",
  "director": "nero.presence",
  "expected_params": [
    "ParamNeroVisibility",
    "ParamNeroWolfEyeGlow",
    "ParamNeroMist",
    "ParamNeroThroughGlow",
    "ParamNeroWarmthBloom"
  ],
  "blend_ms_default": 100
}
```

- `expected_params` — the Cubism parameter names Nero will drive. If the
  viewer's model doesn't expose all of them, that's not an error — the
  viewer should just ignore updates to unknown params. Missing coverage
  will simply not animate.
- `blend_ms_default` — the smooth-blend duration Nero suggests between
  parameter frames. Viewer may override.

### `params` (many per second while presence is active)

The core message. Every call to `PresenceDirector.set_intent()` produces
exactly one of these, translated from `PresenceIntent` through the two
mapping layers documented in `live2d_parameter_map.py`.

```json
{
  "v": 1,
  "kind": "params",
  "state": "speaking",
  "emotion": "warm",
  "params": {
    "ParamNeroVisibility": 1.0,
    "ParamNeroWolfEyeGlow": 0.65,
    "ParamNeroMist": 0.30,
    "ParamNeroThroughGlow": 0.42,
    "ParamNeroWarmthBloom": 0.35
  },
  "blend_ms": 100
}
```

- `state` — the semantic PresenceState value. Optional for viewers, but
  useful for state-machine animations (e.g. viewer picks between two
  breathing loops based on `state`).
- `emotion` — the EmotionState value. Same — informational.
- `params` — **the only field the viewer MUST respect.** A dict of Cubism
  parameter IDs to float values in `[0.0, 1.0]`. The viewer sets each
  parameter, blending toward the new value over `blend_ms` milliseconds.
- `blend_ms` — per-message override of the blend duration. Zero = snap.

### Message rates

- Idle / listening / thinking: bursty on state transition, then silent
  until the next transition. Not a continuous stream.
- Speaking: one message on voice.started, one on voice.speaking, one on
  voice.finished. Typically 2-3 messages per Kokoro sentence.
- Emergence / dissolution: five messages over the ~2 s ramp (four for the
  0.15 → 0.35 → 0.60 → 0.85 intensity steps + one for idle at 1.0).

Peak sustained rate is well below 30 msg/sec. Viewer should size buffers
accordingly (Nero's queue defaults to 256).

---

## Viewer → Nero

### `hello` (recommended, sent by the viewer immediately on receiving Nero's hello)

Viewer identifies its loaded model and lists which parameters are actually
available. Nero logs this and uses it for diagnostics — it does not gate
future messages on it.

```json
{
  "v": 1,
  "kind": "hello",
  "viewer": "cubism-web / cubism-native / custom",
  "viewer_version": "5.0.0",
  "model": "manbeardog__L1__v1",
  "params_available": [
    "ParamNeroVisibility",
    "ParamNeroWolfEyeGlow",
    "ParamNeroMist"
  ]
}
```

### `ack` (optional)

Viewer confirms a message was processed. Not required — Nero doesn't wait
for acks. Useful mostly for viewer-side unit testing.

```json
{"v": 1, "kind": "ack", "for": "params"}
```

### `error` (should be sent for viewer-side failures)

Viewer reports a problem it wants Nero to know about (unknown parameter,
model load failure, render issue). Nero logs this and includes the most
recent one in `health()`.

```json
{"v": 1, "kind": "error", "detail": "ParamNeroWolfEyeGlow not found in loaded model"}
```

### `status` (optional, periodic)

Viewer reports overall health. Useful for future observability. Not
required for v1.

```json
{"v": 1, "kind": "status", "fps": 60, "params_updated": 128, "uptime_s": 42.1}
```

---

## Connection lifecycle

```
Nero starts Live2DRuntime
     │
     ▼
Try WebSocket connect to configured URL
     │
     ├── Success → send hello → begin param stream → serve until disconnect
     │                                                       │
     │                                                       └── disconnect ──┐
     │                                                                        │
     └── Failure → wait backoff seconds → retry ◀────────────────────────────┘
```

- **Backoff schedule** (default): `1, 2, 5, 10, 30` seconds, last value
  repeats forever.
- **Max reconnect attempts** (default `0`): retry forever. Set >0 to give
  up after N failed connects.
- **No connection = drop messages.** Nero does NOT buffer unsent params
  while disconnected. When the connection returns, the runtime resumes
  with the CURRENT intent, not the accumulated backlog. Stale intents
  produce jarring animation on reconnect; dropping them is correct.
- **Ping/pong**: standard WebSocket keep-alive. Nero uses
  `ping_interval=20 s`, `ping_timeout=20 s`. Viewer should honor pings.

---

## Health reporting

The runtime exposes `health_snapshot()` returning:

```python
{
  "connected":        True | False,
  "websocket_url":    "ws://127.0.0.1:3939/nero",
  "reconnect_count":  0,             # cumulative
  "messages_sent":    128,           # cumulative
  "messages_dropped": 0,             # cumulative — from queue-full or send failure
  "last_sent_at":     1720879214.5,  # unix ts
  "last_error":       null | "text",
  "viewer_hello":     {..., "model": "..."}  # most recent viewer hello, if any
}
```

This is surfaced via `/api/runtime/health` under `services[].details` for
the presence service (see `app/main.py`).

---

## Non-goals

- **Not a streaming animation protocol.** This is discrete parameter
  frames. Interpolation is the viewer's job (via `blend_ms`).
- **Not an audio channel.** Voice is entirely separate (Nero's `/api/speak`
  → browser Web Audio). The presence viewer does not receive audio.
- **Not RPC.** Nero does not wait for viewer responses. Every message is
  one-way; acks are optional confirmations.
- **Not encrypted.** `ws://` local-only in v1. Add TLS + auth if the
  runtime ever needs to cross a network boundary.

---

## Future extensions (design-compatible)

- New parameter names — additive, viewer ignores unknown.
- New `kind` values — viewer must ignore unknown kinds, not error.
- New optional fields on `params` (e.g. `easing`, `priority`) — viewer
  may honor or ignore.
- Multi-model support (viewer hosts several rigs, message includes
  `target_model`) — additive field, unknown viewers drive their default
  model.
- Alternative transports (Unix domain socket, named pipe, MQTT) — reuse
  the same JSON envelope; just swap the transport layer inside
  `Live2DRuntime._async_main`.
