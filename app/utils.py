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
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_owner:
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


def save_upload(file_storage) -> str | None:
    """Simpan file gambar yang diunggah, kembalikan URL relatif (/static/uploads/..)."""
    if not file_storage or not file_storage.filename:
        return None
    ext = os.path.splitext(secure_filename(file_storage.filename))[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        return None
    name = secrets.token_hex(8) + ext
    file_storage.save(str(upload_dir() / name))
    return f"/static/uploads/{name}"
