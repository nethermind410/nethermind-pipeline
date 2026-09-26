#!/usr/bin/env python3
"""Thumbnail for a finished video: one art still + 2-3 words of Anton, channel palette.

    python3 make_thumb.py packaging/<id>.json

Reads the "thumbnail" block from the packaging file:
    "thumbnail": {"src": "maggott_hero.jpg", "lines": ["WORST", "X-MAN?"], "accent": 1,
                  "cx": 0.5, "cy": 0.35, "zoom": 1.0}
  src     image in assets/ (defaults to the hook segment's image in cfg/<id>.json)
  lines   2-3 short lines — the curiosity gap, never the whole title
  accent  which line gets the accent colour (default: last)
  cx, cy  focal point of the image, 0-1 (default centre)
  zoom    extra zoom for the vertical cover, e.g. 1.12 to crop off text baked into the art

Writes out/<id>_thumb.jpg (1280x720, YouTube) and out/<id>_cover.jpg (1080x1920, TikTok/IG cover).
"""
import json, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
from channel import DATA  # the data folder (this folder unless NETHER_DATA is set)
A, OUT = os.path.join(DATA, "assets"), os.path.join(DATA, "out")
F_CAP = os.path.join(A, "Anton-Regular.ttf")
WHITE = (255, 255, 255)


def cover(im, w, h, cx, cy, z=1.0):
    s = max(w / im.width, h / im.height) * z
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    x = min(max(round(cx * im.width - w / 2), 0), im.width - w)
    y = min(max(round(cy * im.height - h / 2), 0), im.height - h)
    return im.crop((x, y, x + w, y + h))


def shade(w, h, horizontal):
    """Black gradient behind the text: left side for landscape, bottom for portrait."""
    g = Image.new("L", (w, h))
    px = g.load()
    for i in range(w if horizontal else h):
        t = 1 - i / ((w if horizontal else h) * 0.62) if horizontal else (i / h - 0.45) / 0.55
        a = int(235 * max(0.0, min(1.0, t)))
        if horizontal:
            for y in range(h): px[i, y] = a
        else:
            for x in range(w): px[x, i] = a
    return g


def fit_font(d, lines, max_w, max_h, start):
    s = start
    while s > 40:
        f = ImageFont.truetype(F_CAP, s)
        ws = [d.textbbox((0, 0), l, font=f)[2] for l in lines]
        if max(ws) <= max_w and s * 1.08 * len(lines) <= max_h:
            return f, s
        s -= 4
    return ImageFont.truetype(F_CAP, s), s


def render(img, lines, accent, col, w, h, cx, cy, landscape, z=1.0):
    bg = cover(img, w, h, cx, cy, 1.0 if landscape else z).convert("RGB")
    if landscape and img.width < img.height * 1.2:
        # portrait art in a landscape frame: blurred fill behind, the full-height subject on the right
        bg = bg.filter(ImageFilter.GaussianBlur(28))
        s = h / img.height * 1.12
        fg = img.convert("RGB").resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
        bg.paste(fg, (w - fg.width + round(fg.width * 0.04), round(-fg.height * 0.08 * cy / 0.5)))
    # punch up the art a little so it survives the small feed size
    bg = Image.blend(bg, bg.filter(ImageFilter.UnsharpMask(3, 120, 2)), 0.6)
    black = Image.new("RGB", (w, h))
    bg = Image.composite(black, bg, shade(w, h, landscape))
    d = ImageDraw.Draw(bg)
    if landscape:
        f, s = fit_font(d, lines, int(w * 0.52), int(h * 0.82), 210)
        x, y = int(w * 0.05), (h - s * 1.08 * len(lines)) / 2
    else:
        f, s = fit_font(d, lines, int(w * 0.88), int(h * 0.34), 260)
        x, y = None, h * 0.93 - s * 1.08 * len(lines)
    for i, l in enumerate(lines):
        fill = col if i == accent else WHITE
        bb = d.textbbox((0, 0), l, font=f)
        lx = x if x is not None else (w - bb[2]) / 2
        d.text((lx, y - bb[1]), l, font=f, fill=fill, stroke_width=max(6, s // 18), stroke_fill=(0, 0, 0))
        y += s * 1.08
    return bg


def main(pkg_path):
    vid = os.path.splitext(os.path.basename(pkg_path))[0]
    pkg = json.load(open(pkg_path))
    cfg = json.load(open(os.path.join(DATA, "cfg", vid + ".json")))
    t = pkg.get("thumbnail")
    if not t or not t.get("lines"):
        sys.exit(f'{pkg_path}: add a "thumbnail" block with "lines" (see make_thumb.py docstring)')
    src = t.get("src") or cfg["segments"][0]["vis"]["src"]
    img = Image.open(os.path.join(A, src))
    lines = [l.upper() for l in t["lines"]]
    accent = t.get("accent", len(lines) - 1)
    col = tuple(cfg.get("palette", {}).get("accent", (255, 214, 10)))
    cx, cy = t.get("cx", 0.5), t.get("cy", 0.4)
    specs = [("thumb", 1280, 720, True), ("cover", 1080, 1920, False)]
    for name, w, h, land in specs:
        out = os.path.join(OUT, f"{vid}_{name}.jpg")
        render(img, lines, accent, col, w, h, cx, cy, land, t.get("zoom", 1.0)).save(out, quality=92)
        print(out, f"({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
