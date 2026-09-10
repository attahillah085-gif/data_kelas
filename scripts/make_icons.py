"""Generate ikon PWA (dijalankan sekali saat setup).

    python scripts/make_icons.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"
OUT.mkdir(parents=True, exist_ok=True)


def gradient(size, c1, c2):
    """Diagonal gradient background."""
    base = Image.new("RGB", (size, size), c1)
    top = Image.new("RGB", (size, size), c2)
    mask = Image.new("L", (size, size))
    md = mask.load()
    for y in range(size):
        for x in range(size):
            md[x, y] = int(255 * ((x + y) / (2 * size)))
    base.paste(top, (0, 0), mask)
    return base


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size, size], radius=radius, fill=255)
    return m


def draw_bag(draw, size, pad, stroke_col, w):
    """Gambar tas belanja sederhana (sesuai favicon)."""
    x0, y0, x1, y1 = pad, pad * 1.15, size - pad, size - pad * 0.85
    bw = x1 - x0
    bh = y1 - y0
    # badan tas
    body = [x0, y0 + bh * 0.22, x1, y1]
    draw.rounded_rectangle(body, radius=int(bw * 0.12), outline=stroke_col, width=w)
    # pegangan (busur)
    hx0 = x0 + bw * 0.30
    hy0 = y0
    hx1 = x1 - bw * 0.30
    hy1 = y0 + bh * 0.44
    draw.arc([hx0, hy0, hx1, hy1], start=180, end=360, fill=stroke_col, width=w)
    # tag lingkaran di tengah
    r = bw * 0.16
    cx = (x0 + x1) / 2
    cy = y0 + bh * 0.60
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=stroke_col, width=w)


def make(size, radius_ratio=0.22, pad_ratio=0.26, maskable=False):
    bg = gradient(size, (219, 106, 157), (243, 169, 198)).convert("RGBA")
    if maskable:
        # latar penuh (tanpa sudut membulat) + area aman di tengah
        img = bg
        pad = int(size * (pad_ratio + 0.06))
    else:
        radius = int(size * radius_ratio)
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        img.paste(bg, (0, 0), rounded_mask(size, radius))
        pad = int(size * pad_ratio)
    d = ImageDraw.Draw(img)
    draw_bag(d, size, pad, (255, 255, 255, 255), max(2, int(size * 0.028)))
    return img


make(192).save(OUT / "icon-192.png")
make(512).save(OUT / "icon-512.png")
make(512, maskable=True).save(OUT / "icon-maskable-512.png")
make(72, pad_ratio=0.24).save(OUT / "badge-72.png")
print("Ikon dibuat di", OUT)
