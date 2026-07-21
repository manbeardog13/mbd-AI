# DESIGN — Mission Control (Quantum OLED)

*The Companion's command surface: one screen where the operator sees Nero's
state, the Council's live orchestration, honest host telemetry, the approval
queue, and a command bar that stages real files for Claude · Architect.*

Route: **`GET /mission-control`** · assets: `app/static/mission-control.{html,css,js}`
· backend: `GET /api/host`, `POST /api/council/dispatch` in `app/main.py`.

---

## 1. Why it exists / provenance

Delivered from a Claude Design handoff (`MissionControl.dc.html` + a full
spec pack: design tokens, interaction spec, host-telemetry schema, dispatch
contract, nine reference state renders). The source is a proprietary Claude
Design *Component* (React-based `DCLogic`, `<x-dc>` templating, an external
runtime `support.js` / `vendor/resources.js`). Nero is **local-first and
offline** (ADR-0006), so shipping a CDN/React runtime is disallowed.

**Decision:** re-implement the screen as **offline vanilla HTML/CSS/JS** in
`app/static/`, matching the repo's existing frontend house style, and preserve
every interaction, the deterministic 3-D field, and — above all — the honesty
guarantees. No framework, no network fetch for chrome.

## 2. Colour law (operator's directive)

The operator supplied a six-tone grayscale ramp and three rules:

- **Structure is grayscale.** Shell, nav, status bar, panels, cards, Council
  nodes, telemetry, command bar, borders, dividers, text — all neutral:
  `#070707 · #0e0f0f · #141414 · #1c1c1c · #252525 · #343534` (shell → stage →
  panels → cards → elevated/hover → borders).
- **Nero keeps her colours.** The celestial being at the centre — her field,
  core, brand orb, the filaments reaching out from her, the cursor light — is
  the only vivid hue in the room (electric cyan / spectral blue / violet /
  ice-white; all nine state hues).
- **Signal colour only where it means something:** amber = operator authority,
  red = a genuine block, green = safe / live / approve. Nothing else is
  coloured.

Primary actions that target Claude (the Send button) are pearl-white, not
cyan — colour is reserved for Nero and for signals.

## 3. Honesty contracts (non-negotiable)

These come straight from the handoff's Master Directive and match Nero's own
"measure, don't assume / no invented data" laws.

### Host telemetry — `GET /api/host`
- The UI draws a gauge **only** when the response attests `"simulated": false`.
  Any response missing that is treated as *unavailable* (badge: `DISCONNECTED`,
  placeholder: "No real input").
- The backend returns `simulated: false` **exclusively** for values it has
  actually measured (`psutil` CPU/RAM/disk). There is no vendor-neutral GPU
  source, so `gpu` is `null` with a stated `gpu_reason` → the UI draws **no**
  GPU gauge and shows the reason.
- When no measured source exists (`psutil` absent), the endpoint returns **503**
  — it never fabricates a fallback (`contracts/sample-host-disconnected.json`:
  *"Do not return fabricated fallback values."*). `psutil` is an **optional**
  dependency; without it the panel is honestly Disconnected.
- Poll interval: 5 s. Schema: `host-telemetry.schema.json` in the handoff.

### Command dispatch — `POST /api/council/dispatch`
- `multipart/form-data`: `prompt`, `target=claude`, `role=architect`, `files[]`.
- Staged files stay **local** and are shown as removable chips. They are cleared
  **only** after an HTTP-2xx adapter success.
- No Claude adapter is wired in this repo yet, so the endpoint returns **503**;
  the UI shows `Not sent: … Files remain local.` and **retains every file**.
  Nothing is uploaded anywhere. When a real adapter lands, forward here and
  return 2xx only on genuine success.

### Preview vs measured
Repository stats, orchestration, Council states, approvals, and memory are
labelled **preview/fixture** scenario data (badges: `Preview`, `Retrieved`,
`… pending`). The central field is a **deterministic** visual animation (seed
`0x4E45524F`, 84 particles) and is never presented as a measurement.

## 4. The Nero field — nine states

Canvas-2D projected-3-D wireframe (parametric shells + Lissajous contours +
particle depth + inter-particle links + a bright core), driven by
`CFG[state]` = `{hue, speed, intensity, wire, …}` plus per-state modifiers
(`ripple` / `dense` / `branch` / `scan` / `beam` / `gray`). States: idle,
listening, thinking, planning, reviewing, executing, speaking, waiting, offline
(see `app/animation/nero-core-states.json` in the handoff for the canonical
table). Pointer parallax stays under ~2°. Reduced-motion freezes ambient
advancement while preserving state colour/geometry semantics.

## 5. Polish bar

The screen was refined against a premium-product checklist (Apple/Linear/Arc
sensibility), translated to this OLED-grayscale + celestial-Nero identity (not
the borrowed brief's orange/white/summer literals): stronger hierarchy (the
field is the anchor; command is primary; context cards recede), floating cards
with layered ambient shadow + hairline borders + inner highlights, engineered
spring motion (250–500 ms, hover-lift, button-compress, liquid bars, count-up
numerals, staggered entrances), extremely-low-opacity ambient light, optical
spacing, monumental numerals / receding metadata, and "visual silence" copy —
trimmed everywhere **except** the load-bearing honesty disclosures, which keep
their meaning.

## 6. Integration

- New screen added **beside** the existing chat Companion (strangler-fig); the
  chat UI is untouched apart from a Mission Control link in its top bar. The
  Mission Control brand mark links back to the chat (`/`).
- The nav rail is a Companion nav *shell*; only Mission Control is live. Other
  items are inert placeholders (as in the source) — they do not pretend to
  navigate.

## 7. Verification

- `tests/test_mission_control.py` — offline invariants (assets linked, three
  disclosures distinct, nine states, telemetry gate, GPU-null reason, dispatch
  contract, files-retained-on-failure, backend never fabricates telemetry,
  grayscale-structure/Nero-colour tokens). No server/psutil/network needed.
- `verify/verify_mission_control.py` — the above **plus** live route checks via
  TestClient when FastAPI is present (page 200; `/api/host` honest live-or-503;
  dispatch honest 503; chat still serves). Exit contract 0/2/other.
- Rendered in headless Chromium across idle/thinking/executing/waiting and both
  telemetry paths (Live + Disconnected) with zero JS errors.

## 8. Launcher & device access

**Desktop icon (Windows).** `scripts/install-desktop-icon.ps1` (double-click
`scripts/Create Desktop Icon.cmd`) drops a **NERO Mission Control** shortcut on
the desktop, icon `scripts/nero-mission-control.ico` (Nero's orb, regenerable
via `scripts/make_icon.py`). It runs `scripts/mission-control.ps1`, which starts
the Companion if it isn't already up (`.venv\Scripts\python.exe run.py`, or
`start.bat` on first run), waits for the port, then opens `/mission-control`.

**Phone & tablet (same Wi-Fi).** The server already binds `0.0.0.0` (config
default), so any device on the LAN reaches `http://<pc-ip>:<port>/mission-control`.
Discovery is built in:
- **`GET /connect`** (+ `GET /api/connect`) shows this machine's LAN URL(s) with
  tap-to-open links, a **scan-to-open QR** (optional `segno`; degrades to the
  URL when absent), and Add-to-Home-Screen guidance. Reachable from the
  **Devices** link in the Mission Control status bar.
- Mission Control is a **PWA** (`mission-control.webmanifest` + Apple touch
  meta, orb PNG icons): "Add to Home Screen" gives phone/tablet a real launch
  icon. It is a fixed 21:9 environment scaled to fit — best in landscape /
  on a tablet; a portrait phone letterboxes.
- Off-network access stays private over Tailscale (`docs/REMOTE_ACCESS.md`).

Both `psutil` (telemetry) and `segno` (QR) are **optional** — guarded imports;
the features degrade honestly when absent.

## 9. Known deviations (kept honest)

- The state selector and approval buttons are a compact segmented control
  (~27–28 px), matching the design source rather than the 44 px touch target;
  they remain keyboard-operable. Revisit if Mission Control gains a touch
  surface.
- `/api/council/dispatch` is an honest 503 stub — the real Claude · Architect
  adapter is future work (it is *the* thing that makes the command bar live).
- Nav items beyond Mission Control are visual placeholders.
