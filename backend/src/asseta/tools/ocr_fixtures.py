"""Deterministic synthetic hour-meter image corpus for on-device OCR tests (Android ML Kit, iOS Vision).

Synthetic images are a test baseline, not field validation: real dashboard samples are required for acceptance
(track.md EXT-05). Run: uv run python -m asseta.tools.ocr_fixtures  ->  contracts/fixtures/ocr/images + manifest.json
Categories: `must_read` (OCR expected to succeed) and `fallback_ok` (hard conditions: a failed/low-confidence read
must route to manual entry — a *wrong confident* read is never acceptable).
"""

import json
import random
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[4] / "contracts" / "fixtures" / "ocr"
W, H = 480, 200
SEGMENTS = {
    "0": "abcdef",
    "1": "bc",
    "2": "abged",
    "3": "abgcd",
    "4": "fgbc",
    "5": "afgcd",
    "6": "afgedc",
    "7": "abc",
    "8": "abcdefg",
    "9": "abcdfg",
}


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size=size)  # bundled with Pillow: identical everywhere


def _seven_segment(draw: ImageDraw.ImageDraw, x: int, y: int, digit: str, color: tuple[int, int, int]) -> None:
    w, h, t = 34, 70, 7
    seg = {
        "a": (x + t, y, x + w - t, y + t),
        "b": (x + w - t, y + t, x + w, y + h // 2),
        "c": (x + w - t, y + h // 2, x + w, y + h - t),
        "d": (x + t, y + h - t, x + w - t, y + h),
        "e": (x, y + h // 2, x + t, y + h - t),
        "f": (x, y + t, x + t, y + h // 2),
        "g": (x + t, y + h // 2 - t // 2, x + w - t, y + h // 2 + t // 2),
    }
    for s in SEGMENTS[digit]:
        draw.rectangle(seg[s], fill=color)


def lcd_7seg(value: str) -> Image.Image:
    img = Image.new("RGB", (W, H), (168, 186, 150))
    d = ImageDraw.Draw(img)
    x = 60
    for ch in value:
        if ch == ".":
            d.rectangle((x - 4, 128, x + 4, 136), fill=(30, 40, 30))
            x += 12
            continue
        _seven_segment(d, x, 66, ch, (30, 40, 30))
        x += 46
    d.text((W - 70, 150), "h", font=_font(28), fill=(30, 40, 30))
    return img


def mechanical_drum(value: str) -> Image.Image:
    img = Image.new("RGB", (W, H), (40, 40, 40))
    d = ImageDraw.Draw(img)
    whole, tenths = value.split(".")
    x = 60
    for i, ch in enumerate(whole + tenths):
        is_tenth = i == len(whole)
        d.rectangle((x, 50, x + 52, 140), fill=(170, 20, 20) if is_tenth else (10, 10, 10))
        d.text((x + 10, 60), ch, font=_font(64), fill=(245, 245, 245))
        x += 60
    d.text((60, 155), "HOURS", font=_font(22), fill=(200, 200, 200))
    return img


def backlit_amber(value: str) -> Image.Image:
    img = Image.new("RGB", (W, H), (8, 8, 8))
    d = ImageDraw.Draw(img)
    d.text((30, 20), "12:45", font=_font(30), fill=(255, 176, 0))  # clock distractor
    d.text((70, 70), value, font=_font(72), fill=(255, 176, 0))
    d.text((380, 100), "HRS", font=_font(26), fill=(255, 176, 0))
    return img


def plain_digital(value: str) -> Image.Image:
    img = Image.new("RGB", (W, H), (225, 228, 232))
    d = ImageDraw.Draw(img)
    d.text((30, 30), "Engine Hours", font=_font(34), fill=(20, 20, 20))
    d.text((60, 90), f"{value} h", font=_font(70), fill=(20, 20, 20))
    return img


STYLES = {
    "lcd_7seg": lcd_7seg,
    "mechanical_drum": mechanical_drum,
    "backlit_amber": backlit_amber,
    "plain_digital": plain_digital,
}


def condition(img: Image.Image, name: str, rnd: random.Random) -> Image.Image:
    if name == "dim":
        return img.point(lambda p: int(p * 0.45))
    if name == "glare":
        glare = Image.new("L", img.size, 0)
        ImageDraw.Draw(glare).ellipse((140, 20, 360, 180), fill=200)
        glare = glare.filter(ImageFilter.GaussianBlur(40))
        return Image.composite(Image.new("RGB", img.size, (255, 255, 255)), img, glare)
    if name == "blur":
        return img.filter(ImageFilter.GaussianBlur(2.2))
    if name == "rotated":
        return img.rotate(7, expand=False, fillcolor=(60, 60, 60))
    if name == "noise":
        px = img.load()
        assert px is not None
        for _ in range(9000):
            x, y = rnd.randrange(W), rnd.randrange(H)
            v = rnd.randrange(256)
            px[x, y] = (v, v, v)
        return img
    return img


HARD = {
    ("lcd_7seg", "glare"),
    ("lcd_7seg", "blur"),
    ("lcd_7seg", "noise"),
    ("mechanical_drum", "glare"),
    ("mechanical_drum", "blur"),
    ("backlit_amber", "glare"),
    ("plain_digital", "glare"),
}


def generate() -> list[dict[str, object]]:
    rnd = random.Random(20261021)  # noqa: S311 — deterministic fixtures
    (OUT / "images").mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    for style, render in STYLES.items():
        for cond in ("normal", "dim", "glare", "blur", "rotated", "noise"):
            value = f"{rnd.randrange(100, 99999):05d}.{rnd.randrange(10)}"
            expected = format(Decimal(value).normalize() if "." not in value else Decimal(value), "f")
            name = f"{style}__{cond}.png"
            condition(render(value), cond, rnd).save(OUT / "images" / name, optimize=True)
            manifest.append(
                {
                    "file": f"images/{name}",
                    "style": style,
                    "condition": cond,
                    "displayed": value,
                    "expected_reading": str(Decimal(expected)),
                    "decimal_places": 1,
                    "category": "fallback_ok" if (style, cond) in HARD else "must_read",
                }
            )
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "spec_version": "1",
                "generator": "asseta.tools.ocr_fixtures",
                "seed": 20261021,
                "acceptance": {
                    "must_read_min_accuracy": 0.9,
                    "wrong_confident_reads_allowed": 0,
                    "note": "Measured per platform in Gate 4; real samples required (EXT-05).",
                },
                "known_risks": [
                    "mechanical_drum: the red tenths wheel is spatial; text OCR may merge it into the integer "
                    "(e.g. 20264.1 read as 202641). Apps must use drum geometry or fall back; the server's "
                    "IMPOSSIBLE_INCREMENT/METER_DECREASE sequence rules catch merged reads."
                ],
                "images": manifest,
            },
            indent=2,
        )
        + "\n"
    )
    return manifest


if __name__ == "__main__":
    print(f"wrote {len(generate())} fixtures to {OUT}")
