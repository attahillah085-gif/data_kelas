"""Modul inventori: bal/karung stok thrift + pencatatan penjualan."""
from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import INCOME, InventoryBatch, Period, Transaction
from .utils import manage_required

bp = Blueprint("inventory", __name__, url_prefix="/inventori")

CATEGORIES = ["Campur", "Kaos", "Kemeja", "Jaket / Hoodie", "Celana", "Dress",
              "Sweater", "Jersey", "Sepatu", "Aksesoris", "Branded"]


def _parse_date(value, default=None):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default or date.today()


def _to_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


@bp.route("/")
@login_required
def index():
    status = request.args.get("status", "ACTIVE")
    q = InventoryBatch.query
    if status in ("ACTIVE", "ARCHIVED"):
        q = q.filter_by(status=status)
    batches = q.order_by(InventoryBatch.purchase_date.desc(), InventoryBatch.id.desc()).all()

    all_active = InventoryBatch.query.filter_by(status="ACTIVE").all()
    summary = {
        "modal": sum(b.cost_total for b in all_active),
        "pcs_total": sum(b.quantity for b in all_active),
        "pcs_sisa": sum(b.remaining for b in all_active),
        "pcs_terjual": sum(b.sold_quantity for b in all_active),
        "revenue": sum(b.revenue_total for b in all_active),
        "profit": sum(b.profit for b in all_active),
    }
    open_period = Period.query.filter_by(status="OPEN").order_by(Period.start_date.desc()).first()
    return render_template(
        "inventory/index.html",
        batches=batches, summary=summary, categories=CATEGORIES,
        status=status, today=date.today().isoformat(), open_period=open_period,
    )


@bp.route("/tambah", methods=["POST"])
@login_required
@manage_required
def add():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nama stok wajib diisi.", "danger")
        return redirect(url_for("inventory.index"))
    b = InventoryBatch(
        name=name,
        supplier=(request.form.get("supplier") or "").strip(),
        category=(request.form.get("category") or "Campur").strip(),
        quantity=_to_int(request.form.get("quantity")),
        cost_total=_to_int(request.form.get("cost_total")),
        selling_price=_to_int(request.form.get("selling_price")),
        purchase_date=_parse_date(request.form.get("purchase_date")),
        note=(request.form.get("note") or "").strip(),
        created_by_id=current_user.id,
    )
    db.session.add(b)

    # Opsional: catat modal beli sebagai pengeluaran di periode berjalan
    if request.form.get("record_expense") and b.cost_total > 0:
        open_period = Period.query.filter_by(status="OPEN").order_by(Period.start_date.desc()).first()
        if open_period:
            db.session.add(Transaction(
                period_id=open_period.id, kind="EXPENSE", category="Kulakan / Beli Stok",
                amount=b.cost_total, description=f"Beli stok: {name}",
                date=b.purchase_date, created_by_id=current_user.id,
            ))
    db.session.commit()
    flash(f"Stok '{name}' ditambahkan.", "success")
    return redirect(url_for("inventory.index"))


@bp.route("/<int:bid>/jual", methods=["POST"])
@login_required
@manage_required
def sell(bid):
    b = db.session.get(InventoryBatch, bid)
    if b is None:
        flash("Stok tidak ditemukan.", "danger")
        return redirect(url_for("inventory.index"))
    qty = _to_int(request.form.get("qty"))
    price = _to_int(request.form.get("price"), b.selling_price)
    if qty <= 0:
        flash("Jumlah jual harus lebih dari 0.", "danger")
        return redirect(url_for("inventory.index"))
    if qty > b.remaining:
        flash(f"Stok sisa hanya {b.remaining} pcs.", "warning")
        return redirect(url_for("inventory.index"))

    revenue = qty * price
    b.sold_quantity += qty
    b.revenue_total += revenue

    # Catat sebagai pemasukan di periode berjalan (bila ada)
    open_period = Period.query.filter_by(status="OPEN").order_by(Period.start_date.desc()).first()
    if open_period:
        db.session.add(Transaction(
            period_id=open_period.id, kind=INCOME, category="Penjualan",
            amount=revenue, description=f"Jual {qty} pcs • {b.name}",
            date=date.today(), batch_id=b.id, created_by_id=current_user.id,
        ))
        msg_extra = f" & tercatat di periode '{open_period.name}'"
    else:
        msg_extra = " (belum ada periode terbuka, pemasukan belum tercatat)"

    if b.is_sold_out:
        b.status = b.status  # tetap; ditandai sold out via properti
    db.session.commit()
    flash(f"Terjual {qty} pcs senilai Rp {revenue:,}".replace(",", ".") + msg_extra, "success")
    return redirect(url_for("inventory.index"))


@bp.route("/<int:bid>/ubah", methods=["POST"])
@login_required
@manage_required
def edit(bid):
    b = db.session.get(InventoryBatch, bid)
    if b is None:
        flash("Stok tidak ditemukan.", "danger")
        return redirect(url_for("inventory.index"))
    b.name = (request.form.get("name") or b.name).strip()
    b.supplier = (request.form.get("supplier") or "").strip()
    b.category = (request.form.get("category") or b.category).strip()
    b.selling_price = _to_int(request.form.get("selling_price"), b.selling_price)
    new_qty = _to_int(request.form.get("quantity"), b.quantity)
    if new_qty >= b.sold_quantity:
        b.quantity = new_qty
    b.note = (request.form.get("note") or "").strip()
    db.session.commit()
    flash("Stok diperbarui.", "success")
    return redirect(url_for("inventory.index"))


@bp.route("/<int:bid>/arsip", methods=["POST"])
@login_required
@manage_required
def archive(bid):
    b = db.session.get(InventoryBatch, bid)
    if b is None:
        flash("Stok tidak ditemukan.", "danger")
        return redirect(url_for("inventory.index"))
    b.status = "ARCHIVED" if b.status == "ACTIVE" else "ACTIVE"
    db.session.commit()
    flash(("Diarsipkan" if b.status == "ARCHIVED" else "Diaktifkan") + f": {b.name}", "info")
    return redirect(url_for("inventory.index", status=b.status))


@bp.route("/<int:bid>/hapus", methods=["POST"])
@login_required
@manage_required
def delete(bid):
    b = db.session.get(InventoryBatch, bid)
    if b is None:
        flash("Stok tidak ditemukan.", "danger")
        return redirect(url_for("inventory.index"))
    # Lepaskan tautan transaksi agar tidak terhapus
    for t in b.sales:
        t.batch_id = None
    name = b.name
    db.session.delete(b)
    db.session.commit()
    flash(f"Stok '{name}' dihapus.", "info")
    return redirect(url_for("inventory.index"))
