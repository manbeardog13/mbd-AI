#!/usr/bin/env python3
"""Generate the NERO Mission Control desktop icon (her orb, her colours).

Renders a rounded OLED-dark tile with Nero's radial core glow (white → ice →
cyan → spectral blue) and writes a multi-resolution Windows ``.ico`` next to
this script. Reproducible — re-run to regenerate:

    python scripts/make_icon.py

Requires Pillow (``pip install Pillow``). The committed ``.ico`` means end
users never need to run this.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "nero-mission-control.ico"
SS = 1024  # supersample canvas, downsampled into each icon size

# Radial stops: (radius fraction of tile, (r, g, b, a)) — Nero's celestial ramp.
STOPS = [
    (0.00, (255, 255, 255, 255)),   # white core
    (0.09, (201, 246, 255, 255)),   # ice
    (0.22, (88, 243, 255, 236)),    # electric cyan
    (0.40, (75, 124, 255, 120)),    # spectral blue
    (0.60, (75, 124, 255, 34)),     # falloff
    (0.82, (10, 30, 60, 0)),        # bloom → transparent
]


def _lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(4))


def _color_at(frac):
    frac = max(0.0, min(1.0, frac))
    for i in range(len(STOPS) - 1):
        r0, c0 = STOPS[i]
        r1, c1 = STOPS[i + 1]
        if frac <= r1:
            t = 0 if r1 == r0 else (frac - r0) / (r1 - r0)
            return _lerp(c0, c1, t)
    return STOPS[-1][1]


def build() -> Image.Image:
    tile = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))

    # Rounded OLED tile background (subtle vertical grade #0e0f0f -> #070707).
    bg = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bg)
    for y in range(SS):
        t = y / SS
        v = _lerp((14, 15, 15, 255), (7, 7, 7, 255), t)
        bd.line([(0, y), (SS, y)], fill=v)
    mask = Image.new("L", (SS, SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SS - 1, SS - 1], radius=int(SS * 0.18), fill=255)
    tile.paste(bg, (0, 0), mask)

    # Nero's radial glow, drawn outer→inner so the bright core lands on top.
    glow = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx = cy = SS / 2
    R = SS * 0.82 / 2
    steps = 900
    for s in range(steps, 0, -1):
        frac = s / steps
        r = frac * R
        col = _color_at(frac)
        if col[3] <= 0:
            continue
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    tile = Image.alpha_composite(tile, glow)

    # A whisper of a ring around the core (echoes the brand mark).
    ring = Image.new("RGBA", (SS, SS), (0, 0, 0, 0))
    rr = SS * 0.145
    ImageDraw.Draw(ring).ellipse(
        [cx - rr, cy - rr, cx + rr, cy + rr],
        outline=(255, 255, 255, 90), width=max(2, int(SS * 0.006)),
    )
    tile = Image.alpha_composite(tile, ring)
    return tile


def main() -> None:
    tile = build()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [tile.resize((n, n), Image.LANCZOS) for n in sizes]
    frames[-1].save(OUT, format="ICO", sizes=[(n, n) for n in sizes], append_images=frames[:-1])

    # PNGs for the PWA manifest + Apple touch icon (phone/tablet home-screen
    # icon) and a docs preview. Written into app/static/ where the app serves.
    static = Path(__file__).resolve().parent.parent / "app" / "static"
    tile.resize((512, 512), Image.LANCZOS).save(static / "mission-control-512.png")
    tile.resize((192, 192), Image.LANCZOS).save(static / "mission-control-192.png")
    tile.resize((180, 180), Image.LANCZOS).save(static / "mission-control-180.png")
    tile.resize((256, 256), Image.LANCZOS).save(OUT.with_suffix(".png"))
    print(f"wrote {OUT}  ({', '.join(str(n) for n in sizes)} px) + PWA PNGs in app/static/")


if __name__ == "__main__":
    main()
