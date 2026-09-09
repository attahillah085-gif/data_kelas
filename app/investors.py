"""Modul investor: modal masuk, kepemilikan, dan simulasi bagi hasil."""
from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from .extensions import db
from .models import (
    INCOME,
    Investment,
    Period,
    ROLE_INVESTOR,
    Transaction,
    User,
)
from .services import compute_profit_distribution
from .utils import owner_required

bp = Blueprint("investors", __name__, url_prefix="/investor")


def _parse_date(value, default=None):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default or date.today()


@bp.route("/")
@login_required
def index():
    periods = Period.query.order_by(Period.start_date.desc(), Period.id.desc()).all()
    selected = None
    pid = request.args.get("period", type=int)
    if pid:
        selected = db.session.get(Period, pid)
    if selected is None:
        selected = next((p for p in periods if p.is_open), None) or (periods[0] if periods else None)

    dist = compute_profit_distribution(selected)

    # Daftar akun ber-peran investor (untuk dropdown setor modal)
    investor_users = User.query.filter_by(role=ROLE_INVESTOR, active=True).order_by(User.name).all()

    # Riwayat setoran terbaru
    recent = (
        db.session.query(Investment, User)
        .join(User, Investment.user_id == User.id)
        .order_by(Investment.date.desc(), Investment.id.desc())
        .limit(15)
        .all()
    )

    return render_template(
        "investors/index.html",
        periods=periods, selected=selected, dist=dist,
        investor_users=investor_users, recent=recent,
        today=date.today().isoformat(),
    )


@bp.route("/setor", methods=["POST"])
@login_required
@owner_required
def add_investment():
    user_id = request.form.get("user_id", type=int)
    investor = db.session.get(User, user_id) if user_id else None
    if investor is None:
        flash("Pilih investor terlebih dahulu.", "danger")
        return redirect(url_for("investors.index"))
    try:
        amount = int(float(request.form.get("amount") or 0))
    except ValueError:
        amount = 0
    if amount <= 0:
        flash("Nominal modal harus lebih dari 0.", "danger")
        return redirect(url_for("investors.index"))

    inv = Investment(
        user_id=investor.id, amount=amount,
        date=_parse_date(request.form.get("date")),
        note=(request.form.get("note") or "").strip(),
    )
    db.session.add(inv)

    # Opsional: catat setoran sebagai pemasukan modal di periode berjalan
    if request.form.get("record_income"):
        open_period = Period.query.filter_by(status="OPEN").order_by(Period.start_date.desc()).first()
        if open_period:
            db.session.add(Transaction(
                period_id=open_period.id, kind=INCOME, category="Setoran Modal",
                amount=amount, description=f"Modal dari {investor.name}", date=inv.date,
            ))
    db.session.commit()
    flash(f"Modal Rp {amount:,}".replace(",", ".") + f" dari {investor.name} dicatat.", "success")
    return redirect(url_for("investors.index"))


@bp.route("/setor/<int:iid>/hapus", methods=["POST"])
@login_required
@owner_required
def delete_investment(iid):
    inv = db.session.get(Investment, iid)
    if inv is None:
        flash("Data setoran tidak ditemukan.", "danger")
        return redirect(url_for("investors.index"))
    db.session.delete(inv)
    db.session.commit()
    flash("Setoran modal dihapus.", "info")
    return redirect(url_for("investors.index"))
