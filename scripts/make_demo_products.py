"""Buat gambar produk demo (placeholder gradien) untuk storefront.

    python scripts/make_demo_products.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "demo"
OUT.mkdir(parents=True, exist_ok=True)

# (nama file, warna1, warna2, label) — palet hangat sesuai brand The Girl House
ITEMS = [
    ("kaos.png", (124, 80, 56), (201, 139, 133), "KAOS"),
    ("hoodie.png", (155, 106, 79), (216, 170, 150), "HOODIE"),
    ("jaket.png", (110, 70, 52), (176, 125, 143), "JAKET"),
    ("kemeja.png", (201, 139, 133), (176, 125, 143), "KEMEJA"),
    ("celana.png", (139, 100, 70), (191, 138, 106), "CELANA"),
    ("sweater.png", (191, 138, 106), (217, 166, 160), "SWEATER"),
    ("dress.png", (176, 125, 143), (201, 139, 133), "DRESS"),
    ("flannel.png", (150, 90, 70), (191, 138, 58), "FLANNEL"),
]

SIZE = 800


def gradient(c1, c2):
    base = Image.new("RGB", (SIZE, SIZE), c1)
    top = Image.new("RGB", (SIZE, SIZE), c2)
    mask = Image.new("L", (SIZE, SIZE))
    md = mask.load()
    for y in range(SIZE):
        for x in range(SIZE):
            md[x, y] = int(255 * ((x + y) / (2 * SIZE)))
    base.paste(top, (0, 0), mask)
    return base


def font(size):
    for path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_bag(d):
    cx, cy = SIZE / 2, SIZE / 2 - 40
    w = 300
    x0, y0, x1, y1 = cx - w / 2, cy - w / 2, cx + w / 2, cy + w / 2
    col = (255, 255, 255, 235)
    d.rounded_rectangle([x0, y0 + w * 0.2, x1, y1], radius=36, outline=col, width=10)
    d.arc([x0 + w * 0.3, y0, x1 - w * 0.3, y0 + w * 0.44], 180, 360, fill=col, width=10)
    r = w * 0.14
    d.ellipse([cx - r, cy + w * 0.02, cx + r, cy + w * 0.02 + 2 * r], outline=col, width=10)


for name, c1, c2, label in ITEMS:
    img = gradient(c1, c2).convert("RGBA")
    d = ImageDraw.Draw(img)
    draw_bag(d)
    f = font(64)
    tb = d.textbbox((0, 0), label, font=f)
    tw = tb[2] - tb[0]
    d.text(((SIZE - tw) / 2, SIZE - 180), label, font=f, fill=(255, 255, 255, 240))
    img.convert("RGB").save(OUT / name, quality=88)

print("Gambar demo dibuat di", OUT)
