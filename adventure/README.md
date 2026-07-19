# Nero: Voidbound Codex

Voidbound Codex is a self-contained, local-first browser action RPG inspired by
the product scope of OpenAI's Phantasy Codex Adventure showcase. Its world,
classes, names, visual language, implementation, and progression are original
to Nero.

## Launch

Double-click `Start-VoidboundCodex.ps1`, or run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\adventure\Start-VoidboundCodex.ps1
```

The launcher binds a static server to `127.0.0.1:8788` and opens
`http://127.0.0.1:8788/adventure/`. It does not start the Nero runtime, load a
model, read `data/memory.db`, or expose a network listener beyond loopback.

To create a desktop icon, run `Install-VoidboundCodexShortcut.ps1` once.

## Controls

| Input | Action |
|---|---|
| WASD / arrow keys / left stick | Move |
| Space / J / controller south | Attack |
| Shift / controller east | Evade |
| F / controller west | Oath art |
| Q | Field tonic |
| C | Character Codex |
| L | Local rankings |
| M | Audio toggle |

Touch controls appear automatically at narrow viewport sizes.

## Companions

Choose one companion before a run. Each uses the published pet animation grid,
follows independently, earns persistent-in-run Bond levels, and contributes a
distinct ability:

- **Iskra — Copper Pounce:** marks a target and amplifies focused player damage.
- **Nero — Guardian Rupture:** reduces incoming harm and staggers nearby foes.
- **Mia — Nineteenth Light:** heals a wounded player or burns the nearest threat
  with a warm beacon.

Mia's v2 atlas is still being built elsewhere. Voidbound consumes a hashed,
versioned provisional copy and never edits the active build directory. Replacing
that one asset after Mia's final validation requires no game-logic or save change.
Asset hashes and source status live in `app/static/adventure/assets/provenance.json`.

## Modes

- **Journey:** eight domains, escalating enemy sets, a named keeper boss in
  each domain, recovery gates, and a final ending.
- **Survival:** endless threat escalation, rotating biomes, periodic bosses,
  and local high scores.

Progress, settings, and the Hall of Echoes use one versioned `localStorage`
record. Malformed or incompatible data fails closed to clean defaults. Nothing
is uploaded and there is no shared identity surface.

The title scene was created with OpenAI's built-in image generation using Nero,
Iskra, and Mia as identity references. The production prompt summary and hash
are recorded in the provenance manifest.

## Verify

```powershell
python verify\verify_voidbound_codex.py
python -m unittest tests.test_voidbound_server
```
