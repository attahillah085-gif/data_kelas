"""Modul Laporan & Analitik + ekspor CSV (khusus pengelola & investor untuk lihat)."""
from __future__ import annotations

import csv
import io
from datetime import date

from flask import Blueprint, Response, render_template, request
from flask_login import login_required
from sqlalchemy import func

from .extensions import db
from .models import (
    CAPITAL_CATEGORIES,
    EXPENSE,
    INCOME,
    ORDER_COUNTED,
    Order,
    OrderItem,
    Period,
    Product,
    Transaction,
)
from .utils import manage_required

bp = Blueprint("reports", __name__, url_prefix="/laporan")


def _counted_orders_filter(q):
    return q.filter(Order.status.in_(list(ORDER_COUNTED)))


@bp.route("/")
@login_required
def index():
    from .models import Setting
    setting = Setting.get()
    periods = Period.query.order_by(Period.start_date.asc(), Period.id.asc()).all()

    # Tren per periode + saldo kas berjalan (kas = modal + laba)
    trend = []
    running = 0
    for p in periods:
        running += p.cash_flow
        trend.append({"name": p.name, "income": p.total_income,
                      "expense": p.total_expense, "profit": p.net_profit, "balance": running})
    trend_max = max([max(t["income"], t["expense"]) for t in trend], default=0) or 1
    cash_balance = running

    # Target omzet: bandingkan dengan periode terbuka terbaru (atau periode terakhir)
    target = setting.monthly_target or 0
    cur = next((p for p in reversed(periods) if p.is_open), None) or (periods[-1] if periods else None)
    target_income = cur.total_income if cur else 0
    target_pct = min(round(target_income / target * 100), 100) if target else 0

    # Ringkasan keseluruhan (pemasukan usaha TIDAK termasuk setoran modal)
    total_income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.kind == INCOME, Transaction.category.notin_(CAPITAL_CATEGORIES)).scalar() or 0
    total_capital = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.kind == INCOME, Transaction.category.in_(CAPITAL_CATEGORIES)).scalar() or 0
    total_expense = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.kind == EXPENSE).scalar() or 0
    net = total_income - total_expense

    order_count = _counted_orders_filter(Order.query).count()
    store_revenue = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.status.in_(list(ORDER_COUNTED))).scalar() or 0

    # Produk terlaris (dari pesanan yang sudah dibayar)
    top_products = (
        db.session.query(
            OrderItem.product_name,
            func.sum(OrderItem.qty).label("qty"),
            func.sum(OrderItem.price * OrderItem.qty).label("revenue"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.status.in_(list(ORDER_COUNTED)))
        .group_by(OrderItem.product_name)
        .order_by(func.sum(OrderItem.price * OrderItem.qty).desc())
        .limit(8)
        .all()
    )
    top_max = max([r.revenue for r in top_products], default=0) or 1

    # Pengeluaran per kategori (semua periode)
    cat_rows = (
        db.session.query(Transaction.category, func.sum(Transaction.amount))
        .filter(Transaction.kind == EXPENSE)
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(6)
        .all()
    )
    cat_max = max([r[1] for r in cat_rows], default=0) or 1

    return render_template(
        "reports/index.html",
        trend=trend, trend_max=trend_max,
        total_income=total_income, total_expense=total_expense, net=net,
        total_capital=total_capital,
        order_count=order_count, store_revenue=store_revenue,
        top_products=top_products, top_max=top_max,
        cat_rows=cat_rows, cat_max=cat_max,
        product_count=Product.query.count(),
        target=target, target_income=target_income, target_pct=target_pct,
        target_period=cur.name if cur else "", cash_balance=cash_balance,
    )


def _csv_response(filename, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for r in rows:
        writer.writerow(r)
    out = buf.getvalue()
    return Response(
        out, mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@bp.route("/ekspor/transaksi.csv")
@login_required
@manage_required
def export_transactions():
    q = Transaction.query.order_by(Transaction.date.desc())
    pid = request.args.get("period", type=int)
    if pid:
        q = q.filter_by(period_id=pid)
    rows = [
        [t.date.isoformat(), t.period.name if t.period else "",
         "Pemasukan" if t.kind == INCOME else "Pengeluaran",
         t.category, t.amount, t.description or ""]
        for t in q.all()
    ]
    return _csv_response("transaksi.csv",
                         ["Tanggal", "Periode", "Jenis", "Kategori", "Nominal", "Keterangan"], rows)


@bp.route("/ekspor/pesanan.csv")
@login_required
@manage_required
def export_orders():
    rows = [
        [o.code, o.created_at.strftime("%Y-%m-%d %H:%M"), o.customer_name, o.customer_phone,
         o.total_qty, o.total, o.status_label]
        for o in Order.query.order_by(Order.created_at.desc()).all()
    ]
    return _csv_response("pesanan.csv",
                         ["Kode", "Tanggal", "Pelanggan", "WhatsApp", "Jumlah Item", "Total", "Status"], rows)


@bp.route("/ekspor/produk.csv")
@login_required
@manage_required
def export_products():
    rows = [
        [p.name, p.category, p.size or "", p.price, p.stock,
         "Tampil" if p.active else "Sembunyi", p.avg_rating, p.review_count]
        for p in Product.query.order_by(Product.created_at.desc()).all()
    ]
    return _csv_response("produk.csv",
                         ["Nama", "Kategori", "Ukuran", "Harga", "Stok", "Status", "Rating", "Jml Ulasan"], rows)
