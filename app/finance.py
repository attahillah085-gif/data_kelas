"""Modul keuangan: periode & transaksi pemasukan/pengeluaran."""
from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import (
    EXPENSE,
    EXPENSE_CATEGORIES,
    INCOME,
    INCOME_CATEGORIES,
    Period,
    Transaction,
)
from .services import notify_managers
from .utils import manage_required

bp = Blueprint("finance", __name__, url_prefix="/keuangan")


def _parse_date(value: str, default: date | None = None) -> date:
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

    kind_filter = request.args.get("kind", "")
    transactions = []
    if selected:
        transactions = list(selected.transactions)
        if kind_filter in (INCOME, EXPENSE):
            transactions = [t for t in transactions if t.kind == kind_filter]

    return render_template(
        "finance/index.html",
        periods=periods,
        selected=selected,
        transactions=transactions,
        kind_filter=kind_filter,
        income_categories=INCOME_CATEGORIES,
        expense_categories=EXPENSE_CATEGORIES,
        today=date.today().isoformat(),
    )


# ---------------- Periode ----------------
@bp.route("/periode/tambah", methods=["POST"])
@login_required
@manage_required
def period_add():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nama periode wajib diisi.", "danger")
        return redirect(url_for("finance.index"))
    start = _parse_date(request.form.get("start_date"), date.today())
    end_raw = request.form.get("end_date")
    end = _parse_date(end_raw) if end_raw else None
    p = Period(name=name, start_date=start, end_date=end, status="OPEN",
               note=(request.form.get("note") or "").strip())
    db.session.add(p)
    db.session.commit()
    flash(f"Periode '{name}' dibuat.", "success")
    return redirect(url_for("finance.index", period=p.id))


@bp.route("/periode/<int:pid>/tutup", methods=["POST"])
@login_required
@manage_required
def period_toggle(pid):
    p = db.session.get(Period, pid)
    if p is None:
        flash("Periode tidak ditemukan.", "danger")
        return redirect(url_for("finance.index"))
    p.status = "CLOSED" if p.is_open else "OPEN"
    if p.status == "CLOSED" and not p.end_date:
        p.end_date = date.today()
    db.session.commit()
    if p.status == "CLOSED":
        notify_managers(
            f"Periode '{p.name}' ditutup",
            f"Laba bersih: Rp {p.net_profit:,}".replace(",", "."),
            category="info", link="/keuangan",
        )
        db.session.commit()
    flash(f"Periode '{p.name}' {'ditutup' if p.status == 'CLOSED' else 'dibuka kembali'}.", "info")
    return redirect(url_for("finance.index", period=p.id))


@bp.route("/periode/<int:pid>/hapus", methods=["POST"])
@login_required
@manage_required
def period_delete(pid):
    p = db.session.get(Period, pid)
    if p is None:
        flash("Periode tidak ditemukan.", "danger")
        return redirect(url_for("finance.index"))
    name = p.name
    db.session.delete(p)
    db.session.commit()
    flash(f"Periode '{name}' beserta transaksinya dihapus.", "info")
    return redirect(url_for("finance.index"))


# ---------------- Transaksi ----------------
@bp.route("/transaksi/tambah", methods=["POST"])
@login_required
@manage_required
def tx_add():
    period_id = request.form.get("period_id", type=int)
    p = db.session.get(Period, period_id) if period_id else None
    if p is None:
        flash("Pilih periode terlebih dahulu.", "danger")
        return redirect(url_for("finance.index"))
    if not p.is_open:
        flash("Periode sudah ditutup. Buka kembali untuk menambah transaksi.", "warning")
        return redirect(url_for("finance.index", period=p.id))

    kind = request.form.get("kind")
    if kind not in (INCOME, EXPENSE):
        flash("Jenis transaksi tidak valid.", "danger")
        return redirect(url_for("finance.index", period=p.id))
    try:
        amount = int(float(request.form.get("amount") or 0))
    except ValueError:
        amount = 0
    if amount <= 0:
        flash("Nominal harus lebih dari 0.", "danger")
        return redirect(url_for("finance.index", period=p.id))

    tx = Transaction(
        period_id=p.id,
        kind=kind,
        category=(request.form.get("category") or "Lainnya").strip(),
        amount=amount,
        description=(request.form.get("description") or "").strip(),
        date=_parse_date(request.form.get("date"), date.today()),
        created_by_id=current_user.id,
    )
    db.session.add(tx)
    db.session.commit()
    label = "Pemasukan" if kind == INCOME else "Pengeluaran"
    flash(f"{label} Rp {amount:,} dicatat.".replace(",", "."), "success")
    return redirect(url_for("finance.index", period=p.id))


@bp.route("/transaksi/<int:tid>/hapus", methods=["POST"])
@login_required
@manage_required
def tx_delete(tid):
    tx = db.session.get(Transaction, tid)
    if tx is None:
        flash("Transaksi tidak ditemukan.", "danger")
        return redirect(url_for("finance.index"))
    pid = tx.period_id
    db.session.delete(tx)
    db.session.commit()
    flash("Transaksi dihapus.", "info")
    return redirect(url_for("finance.index", period=pid))
