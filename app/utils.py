"""Helper umum: decorator peran & filter template."""
from functools import wraps

from flask import abort
from flask_login import current_user


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
