"""Helper umum: decorator peran, filter template, upload & slug."""
import os
import re
import secrets
import unicodedata
from functools import wraps
from pathlib import Path

from flask import abort, current_app
from flask_login import current_user
from werkzeug.utils import secure_filename


def role_required(*roles):
    """Batasi akses hanya untuk peran tertentu."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


def manage_required(view):
    """Hanya owner & pengelola yang boleh mengubah data."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.can_manage:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def owner_required(view):
    """Dulu khusus owner; kini Pengelola (akses penuh) juga lolos."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.can_manage:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


# --------------------------------------------------------------------------
#  Filter template
# --------------------------------------------------------------------------
def format_rupiah(value) -> str:
    """1500000 -> 'Rp 1.500.000'."""
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        value = 0
    sign = "-" if value < 0 else ""
    s = f"{abs(value):,}".replace(",", ".")
    return f"{sign}Rp {s}"


def format_number(value) -> str:
    try:
        value = int(round(float(value)))
    except (TypeError, ValueError):
        value = 0
    return f"{value:,}".replace(",", ".")


def format_compact(value) -> str:
    """Ringkas untuk kartu KPI: 1500000 -> 'Rp 1,5 jt'."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = 0
    neg = value < 0
    value = abs(value)
    if value >= 1_000_000_000:
        out = f"Rp {value / 1_000_000_000:.1f} M".replace(".", ",")
    elif value >= 1_000_000:
        out = f"Rp {value / 1_000_000:.1f} jt".replace(".", ",")
    elif value >= 1_000:
        out = f"Rp {value / 1_000:.0f} rb"
    else:
        out = f"Rp {value:.0f}"
    return ("-" if neg else "") + out


def register_filters(app):
    app.jinja_env.filters["rupiah"] = format_rupiah
    app.jinja_env.filters["angka"] = format_number
    app.jinja_env.filters["ringkas"] = format_compact


# --------------------------------------------------------------------------
#  Slug & upload gambar
# --------------------------------------------------------------------------
def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text or "produk"


def unique_slug(model, text: str) -> str:
    """Slug unik untuk sebuah model (menambah -2, -3, ... bila bentrok)."""
    base = slugify(text)
    slug = base
    i = 2
    while model.query.filter_by(slug=slug).first() is not None:
        slug = f"{base}-{i}"
        i += 1
    return slug


ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def upload_dir() -> Path:
    d = Path(current_app.static_folder) / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


# Sisi terpanjang maksimum (px) & kualitas kompres JPEG untuk foto unggahan.
MAX_IMAGE_DIM = 1600
JPEG_QUALITY = 82


def save_upload(file_storage) -> str | None:
    """Simpan gambar unggahan — otomatis diperkecil & dikompres agar ringan.

    Foto besar dari HP (mis. 5 MB) diperkecil ke maksimal 1600px & dikompres,
    sehingga toko cepat dibuka dan hemat bandwidth. Bila optimasi gagal
    (mis. Pillow tak ada / file animasi), file disimpan apa adanya.
    """
    if not file_storage or not file_storage.filename:
        return None
    ext = os.path.splitext(secure_filename(file_storage.filename))[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        return None
    name = secrets.token_hex(8)
    dest = upload_dir()

    # GIF (mungkin animasi) disimpan utuh agar animasinya tidak hilang.
    if ext != ".gif":
        try:
            from PIL import Image, ImageOps
            file_storage.stream.seek(0)
            img = Image.open(file_storage.stream)
            img = ImageOps.exif_transpose(img)          # koreksi rotasi kamera HP
            img.thumbnail((MAX_IMAGE_DIM, MAX_IMAGE_DIM), Image.LANCZOS)
            has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
            if has_alpha:
                out = f"{name}.png"
                img.convert("RGBA").save(dest / out, format="PNG", optimize=True)
            else:
                out = f"{name}.jpg"
                img.convert("RGB").save(dest / out, format="JPEG",
                                        quality=JPEG_QUALITY, optimize=True, progressive=True)
            return f"/static/uploads/{out}"
        except Exception:
            pass  # jatuh ke penyimpanan mentah di bawah

    out = f"{name}{ext}"
    try:
        file_storage.stream.seek(0)
    except Exception:
        pass
    file_storage.save(str(dest / out))
    return f"/static/uploads/{out}"


# Nama file ikon aplikasi yang dihasilkan dari logo (disimpan di volume uploads).
APP_ICON_FILES = ["appicon-192.png", "appicon-512.png", "appicon-maskable-512.png"]


def generate_app_icons(logo_rel_url: str) -> bool:
    """Buat ikon aplikasi (PWA) dari logo unggahan agar ikon HP = logo web.

    Logo ditaruh di kanvas persegi putih (rapi untuk home screen & install).
    Mengembalikan True bila berhasil.
    """
    if not logo_rel_url:
        return False
    try:
        from PIL import Image
        static = Path(current_app.static_folder)
        src = static / logo_rel_url.replace("/static/", "", 1)
        if not src.exists():
            return False
        logo = Image.open(src)
        from PIL import ImageOps
        logo = ImageOps.exif_transpose(logo).convert("RGBA")
        dest = upload_dir()
        specs = [
            (192, "appicon-192.png", 0.12),
            (512, "appicon-512.png", 0.12),
            (512, "appicon-maskable-512.png", 0.20),  # padding lebih besar (safe zone)
        ]
        for size, name, pad_ratio in specs:
            canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
            pad = int(size * pad_ratio)
            box = size - 2 * pad
            lg = logo.copy()
            lg.thumbnail((box, box), Image.LANCZOS)
            x = (size - lg.width) // 2
            y = (size - lg.height) // 2
            canvas.alpha_composite(lg, (x, y))
            canvas.convert("RGB").save(dest / name, format="PNG", optimize=True)
        return True
    except Exception:
        return False


def remove_app_icons() -> None:
    """Hapus ikon aplikasi hasil generate (mis. saat logo dihapus)."""
    try:
        dest = upload_dir()
        for name in APP_ICON_FILES:
            p = dest / name
            if p.exists():
                p.unlink()
    except Exception:
        pass


def app_icons_exist() -> bool:
    try:
        dest = upload_dir()
        return all((dest / n).exists() for n in APP_ICON_FILES)
    except Exception:
        return False
