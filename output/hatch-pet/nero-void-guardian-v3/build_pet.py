from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[2]
WPF_SOURCE = Path("familiar/assets/nero/nero-voidcaster-v2.png")
WPF_ATLAS = REPO_ROOT / WPF_SOURCE
GENERATED = ROOT / "source" / "generated-variants-alpha.png"
OUT_PNG = ROOT / "spritesheet.png"
OUT_WEBP = ROOT / "spritesheet.webp"
QA = ROOT / "qa"

CELL_W, CELL_H = 192, 208
COLS, ROWS = 8, 11

Y_BANDS = [
    (26, 170), (196, 345), (368, 514), (529, 688), (704, 857),
    (874, 1019), (1036, 1191), (1212, 1381), (1401, 1552),
    (1574, 1739),
]
X_BANDS = [
    [(27, 126), (143, 250), (270, 376), (394, 493), (517, 611), (641, 735), (755, 850)],
    [(21, 139), (176, 311), (340, 480), (495, 615), (630, 745), (754, 867)],
    [(19, 138), (153, 265), (281, 388), (409, 510), (523, 637), (643, 743), (755, 857)],
    [(17, 142), (157, 269), (292, 396), (428, 531), (540, 648), (654, 754), (770, 870)],
    [(15, 105), (160, 258), (319, 418), (473, 602), (654, 780)],
    [(22, 128), (208, 315), (375, 483), (547, 644), (690, 786)],
    [(14, 157), (177, 322), (349, 504), (534, 672), (684, 838)],
    [(18, 159), (193, 339), (373, 514), (539, 681), (696, 836)],
    [(26, 145), (175, 296), (313, 437), (448, 567), (582, 702), (723, 838)],
    [(33, 147), (178, 293), (317, 431), (463, 564), (596, 696), (731, 831)],
]


def wpf_frame(atlas: Image.Image, index: int) -> Image.Image:
    x = (index % 8) * CELL_W
    y = (index // 8) * CELL_H
    return atlas.crop((x, y, x + CELL_W, y + CELL_H)).convert("RGBA")


def fitted_generated(source: Image.Image, row: int, frame: int) -> Image.Image:
    x0, x1 = X_BANDS[row][frame]
    y0, y1 = Y_BANDS[row]
    crop = source.crop((max(0, x0 - 4), max(0, y0 - 4), min(source.width, x1 + 5), min(source.height, y1 + 5)))
    alpha = crop.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        raise ValueError(f"Generated frame {row}:{frame} has no visible pixels")
    crop = crop.crop(bbox)
    scale = min(178 / crop.width, 198 / crop.height)
    size = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
    crop = crop.resize(size, Image.Resampling.LANCZOS)
    cell = Image.new("RGBA", (CELL_W, CELL_H), (0, 0, 0, 0))
    cell.alpha_composite(crop, ((CELL_W - crop.width) // 2, CELL_H - crop.height - 3))
    return cell


def failure_variant(base: Image.Image, phase: int) -> Image.Image:
    cell = base.copy()
    # A compact, readable failure marker derived from the WPF warning language.
    draw = ImageDraw.Draw(cell, "RGBA")
    pulse = 150 + phase * 12
    cx, cy = 157, 36
    draw.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=(62, 3, 36, 190), outline=(255, 62, 167, pulse), width=3)
    draw.line((cx - 8, cy - 8, cx + 8, cy + 8), fill=(255, 188, 225, 255), width=4)
    draw.line((cx + 8, cy - 8, cx - 8, cy + 8), fill=(255, 188, 225, 255), width=4)
    if phase % 2:
        cell = cell.transform(cell.size, Image.Transform.AFFINE, (1, 0, 1, 0, 1, 2), resample=Image.Resampling.BICUBIC)
    return cell


def waiting_variant(base: Image.Image, phase: int) -> Image.Image:
    cell = base.copy()
    draw = ImageDraw.Draw(cell, "RGBA")
    colors = [(255, 73, 213, 255), (153, 91, 255, 235), (69, 221, 255, 220)]
    for dot in range(3):
        angle = (phase / 6 * math.tau) + dot * math.tau / 3
        x = 96 + math.cos(angle) * 61
        y = 83 + math.sin(angle) * 25
        r = 4 if dot == phase % 3 else 6
        draw.ellipse((x - r, y - r, x + r, y + r), fill=colors[dot])
    return cell


def direction_variant(base: Image.Image, direction: int) -> Image.Image:
    cell = base.copy()
    draw = ImageDraw.Draw(cell, "RGBA")
    angle = math.radians(direction * 22.5 - 90)
    cx, cy = 96 + math.cos(angle) * 65, 73 + math.sin(angle) * 49
    color = (255, 77, 221, 255) if direction % 2 == 0 else (74, 226, 255, 255)
    r = 8
    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    draw.polygon(points, fill=color)
    draw.ellipse((cx - 13, cy - 13, cx + 13, cy + 13), outline=(*color[:3], 110), width=2)
    return cell


def frame_hash(frame: Image.Image) -> str:
    return hashlib.sha256(frame.tobytes()).hexdigest()[:16]


def main() -> None:
    QA.mkdir(parents=True, exist_ok=True)
    wpf = Image.open(WPF_ATLAS).convert("RGBA")
    generated = Image.open(GENERATED).convert("RGBA")
    if wpf.size != (1536, 416):
        raise ValueError(f"Unexpected WPF atlas size: {wpf.size}")

    exact = [wpf_frame(wpf, i) for i in range(16)]
    gen = [[fitted_generated(generated, r, i) for i in range(len(X_BANDS[r]))] for r in range(10)]

    rows: list[list[Image.Image]] = []
    rows.append(exact[0:6])
    run_right = [gen[1][i] for i in [0, 1, 2, 3, 4, 5, 4, 2]]
    rows.append(run_right)
    rows.append([f.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for f in run_right])
    rows.append([gen[3][i] for i in [0, 1, 2, 3]])
    rows.append([gen[4][i] for i in range(5)])
    failed_bases = [exact[i] for i in [8, 9, 10, 11, 10, 9, 8, 9]]
    rows.append([failure_variant(frame, i) for i, frame in enumerate(failed_bases)])
    waiting_bases = [exact[i] for i in [8, 9, 10, 11, 10, 9]]
    rows.append([waiting_variant(frame, i) for i, frame in enumerate(waiting_bases)])
    rows.append([gen[6][i] for i in [0, 1, 2, 3, 4, 2]])
    rows.append([gen[7][i] for i in [0, 1, 2, 3, 4, 2]])
    rows.append([direction_variant(exact[8 + (i % 4)], i) for i in range(8)])
    rows.append([direction_variant(exact[8 + (i % 4)], i + 8) for i in range(8)])

    expected_counts = [6, 8, 8, 4, 5, 8, 6, 6, 6, 8, 8]
    if [len(row) for row in rows] != expected_counts:
        raise AssertionError("Animation row counts do not match the Codex Pets contract")

    atlas = Image.new("RGBA", (COLS * CELL_W, ROWS * CELL_H), (0, 0, 0, 0))
    used = []
    for row_index, frames in enumerate(rows):
        for col_index, frame in enumerate(frames):
            atlas.alpha_composite(frame, (col_index * CELL_W, row_index * CELL_H))
            used.append({"row": row_index, "column": col_index, "hash": frame_hash(frame)})

    atlas.save(OUT_PNG, optimize=True)
    atlas.save(OUT_WEBP, format="WEBP", lossless=True, method=6)

    pet = {
        "id": "nero-void-guardian",
        "displayName": "Nero Void Guardian",
        "description": "The full WPF Void Guardian adapted for Codex Pets with movement, attention, waiting, work, success, failure, and directional states.",
        "spriteVersionNumber": 2,
        "spritesheetPath": "spritesheet.webp",
    }
    (ROOT / "pet.json").write_text(json.dumps(pet, indent=2) + "\n", encoding="utf-8")

    mapping = {
        "sourceWpfAtlas": WPF_SOURCE.as_posix(),
        "sourceGeneratedVariants": GENERATED.relative_to(REPO_ROOT).as_posix(),
        "cell": [CELL_W, CELL_H],
        "grid": [COLS, ROWS],
        "rows": [
            {"row": 0, "state": "idle", "frames": 6, "source": "exact WPF breathe frames"},
            {"row": 1, "state": "run-right", "frames": 8, "source": "generated WPF-identity movement"},
            {"row": 2, "state": "run-left", "frames": 8, "source": "mirrored run-right"},
            {"row": 3, "state": "wave", "frames": 4, "source": "WPF attention and greeting gestures"},
            {"row": 4, "state": "jump", "frames": 5, "source": "WPF-identity hover and action poses"},
            {"row": 5, "state": "failed", "frames": 8, "source": "WPF pensive frames with failure pulse"},
            {"row": 6, "state": "waiting", "frames": 6, "source": "WPF thinking frames with orbiting cognition dots"},
            {"row": 7, "state": "active-work", "frames": 6, "source": "cyan Codex hex and work effects"},
            {"row": 8, "state": "review-success", "frames": 6, "source": "violet review and success ring"},
            {"row": 9, "state": "look-000-to-157", "frames": 8, "source": "WPF attentive frames with directional focus spark"},
            {"row": 10, "state": "look-180-to-337", "frames": 8, "source": "WPF attentive frames with directional focus spark"},
        ],
    }
    (ROOT / "mapping.json").write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")

    contact = Image.new("RGBA", atlas.size, (22, 8, 31, 255))
    contact.alpha_composite(atlas)
    contact.thumbnail((1152, 1716), Image.Resampling.LANCZOS)
    contact.convert("RGB").save(QA / "final-contact-sheet.jpg", quality=92)

    durations = [180, 100, 100, 220, 130, 160, 190, 160, 180, 180, 180]
    for row_index, frames in enumerate(rows):
        preview = []
        for frame in frames:
            bg = Image.new("RGBA", frame.size, (22, 8, 31, 255))
            bg.alpha_composite(frame)
            preview.append(bg.convert("P", palette=Image.Palette.ADAPTIVE))
        preview[0].save(
            QA / f"row-{row_index:02d}.gif",
            save_all=True,
            append_images=preview[1:],
            duration=durations[row_index],
            loop=0,
            disposal=2,
        )

    alpha = atlas.getchannel("A")
    unused_opaque = 0
    for row_index, count in enumerate(expected_counts):
        for col_index in range(count, COLS):
            cell_alpha = alpha.crop((col_index * CELL_W, row_index * CELL_H, (col_index + 1) * CELL_W, (row_index + 1) * CELL_H))
            unused_opaque += sum(1 for value in cell_alpha.get_flattened_data() if value)
    green_pixels = sum(
        1 for r, g, b, a in atlas.get_flattened_data()
        if a > 24 and g > 180 and g > r * 1.7 and g > b * 1.7
    )
    validation = {
        "passed": atlas.size == (1536, 2288) and unused_opaque == 0 and green_pixels == 0,
        "size": list(atlas.size),
        "mode": atlas.mode,
        "alphaExtrema": list(alpha.getextrema()),
        "usedFrames": len(used),
        "uniqueFrameHashes": len({item["hash"] for item in used}),
        "unusedOpaquePixels": unused_opaque,
        "greenLeakPixels": green_pixels,
        "frames": used,
    }
    (ROOT / "validation.json").write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    if not validation["passed"]:
        raise AssertionError(f"Validation failed: {validation}")
    print(json.dumps({key: validation[key] for key in ["passed", "size", "usedFrames", "uniqueFrameHashes", "unusedOpaquePixels", "greenLeakPixels"]}))


if __name__ == "__main__":
    main()
