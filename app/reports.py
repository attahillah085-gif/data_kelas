"""Modul Laporan & Analitik + ekspor CSV (khusus pengelola & investor untuk lihat)."""
from __future__ import annotations

import csv
import io
import math
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
    InventoryBatch,
    Order,
    OrderItem,
    Period,
    Product,
    Setting,
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


def _status(value, good, warn, higher_better=True):
    """Kembalikan 'g'/'w'/'b' berdasar ambang sehat/waspada."""
    if higher_better:
        if value >= good:
            return "g"
        if value >= warn:
            return "w"
        return "b"
    else:
        if value <= good:
            return "g"
        if value <= warn:
            return "w"
        return "b"


def _compute_ceo_metrics():
    """Hitung metrik ala CEO dari data nyata (bal inventori, pesanan, keuangan)."""
    setting = Setting.get()
    batches = InventoryBatch.query.all()

    total_qty = sum(b.quantity for b in batches)
    total_sold = sum(b.sold_quantity for b in batches)
    cogs_sold = sum(b.cost_per_item * b.sold_quantity for b in batches)
    gross_profit = sum(b.profit for b in batches)
    batch_revenue = sum(b.revenue_total for b in batches)
    active = [b for b in batches if b.status == "ACTIVE"]
    stock_value = sum(b.remaining * b.cost_per_item for b in active)
    stock_pieces = sum(b.remaining for b in active)

    gross_margin = round(gross_profit / batch_revenue * 100, 1) if batch_revenue else 0.0
    sell_through = round(total_sold / total_qty * 100, 1) if total_qty else 0.0
    turnover = round(cogs_sold / stock_value, 1) if stock_value else 0.0
    gmroi = round(gross_profit / stock_value, 2) if stock_value else 0.0
    avg_gp = round(gross_profit / total_sold) if total_sold else 0
    avg_price = round(batch_revenue / total_sold) if total_sold else 0
    days_inventory = round(365 / turnover) if turnover else 0

    # Pesanan toko → AOV
    order_count = Order.query.filter(Order.status.in_(list(ORDER_COUNTED))).count()
    store_revenue = db.session.query(func.coalesce(func.sum(Order.total), 0)).filter(
        Order.status.in_(list(ORDER_COUNTED))).scalar() or 0
    aov = round(store_revenue / order_count) if order_count else 0

    # Margin bersih dari keuangan (usaha, tanpa modal)
    total_income = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.kind == INCOME, Transaction.category.notin_(CAPITAL_CATEGORIES)).scalar() or 0
    total_expense = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.kind == EXPENSE).scalar() or 0
    net = total_income - total_expense
    net_margin = round(net / total_income * 100, 1) if total_income else 0.0

    # Periode berjalan (dasar alokasi laba)
    periods = Period.query.order_by(Period.start_date.asc(), Period.id.asc()).all()
    latest = next((p for p in reversed(periods) if p.is_open), None) or (periods[-1] if periods else None)
    latest_net = latest.net_profit if latest else 0
    latest_name = latest.name if latest else ""

    # BEP (titik impas)
    fixed = setting.fixed_costs_monthly or 0
    bep_pcs = math.ceil(fixed / avg_gp) if avg_gp > 0 else 0
    bep_omzet = bep_pcs * avg_price
    bep_daily = round(bep_pcs / 26, 1) if bep_pcs else 0

    # Cadangan kas ideal (2-3x biaya tetap)
    reserve_min = fixed * 2
    reserve_ideal = fixed * 3

    # Dead stock aging (dari bal aktif yang masih ada sisa)
    today = date.today()
    aging = [
        {"label": "0–30 hari", "value": 0, "pcs": 0, "key": "fresh"},
        {"label": "31–60 hari", "value": 0, "pcs": 0, "key": "ok"},
        {"label": "61–90 hari", "value": 0, "pcs": 0, "key": "watch"},
        {"label": "> 90 hari (dead)", "value": 0, "pcs": 0, "key": "dead"},
    ]
    for b in active:
        if b.remaining <= 0:
            continue
        age = (today - (b.purchase_date or today)).days
        val = b.remaining * b.cost_per_item
        idx = 0 if age <= 30 else 1 if age <= 60 else 2 if age <= 90 else 3
        aging[idx]["value"] += val
        aging[idx]["pcs"] += b.remaining
    dead_value = aging[3]["value"]
    dead_pct = round(dead_value / stock_value * 100, 1) if stock_value else 0.0

    # KPI cards
    kpis = [
        {"label": "Margin Kotor", "val": f"{gross_margin:.0f}%", "raw": gross_margin,
         "status": _status(gross_margin, 55, 40), "bench": "Sehat > 55%",
         "hint": "Bagian harga jual yang jadi milikmu sebelum biaya operasional."},
        {"label": "Margin Bersih", "val": f"{net_margin:.0f}%", "raw": net_margin,
         "status": _status(net_margin, 10, 0), "bench": "Sehat > 10%",
         "hint": "Untung sesungguhnya setelah semua biaya. Ini yang bisa direinvestasi."},
        {"label": "Sell-Through", "val": f"{sell_through:.0f}%", "raw": sell_through,
         "status": _status(sell_through, 65, 45), "bench": "Sehat > 65%",
         "hint": "Persen stok yang laku dari yang masuk. Ukur 'barangnya kejual gak'."},
        {"label": "GMROI", "val": f"{gmroi:.2f}", "raw": gmroi,
         "status": _status(gmroi, 1.5, 1.0), "bench": "Sehat > 1,5",
         "hint": "Laba kotor per Rp1 modal di stok. Metrik raja ritel."},
        {"label": "Perputaran Stok", "val": f"{turnover:.1f}×", "raw": turnover,
         "status": _status(turnover, 4, 3), "bench": "Sehat 4–8× / th",
         "hint": f"Stok berputar jadi uang {turnover:.1f}× setahun (± {days_inventory} hari/barang)."},
        {"label": "Dead Stock", "val": f"{dead_pct:.0f}%", "raw": dead_pct,
         "status": _status(dead_pct, 10, 25, higher_better=False), "bench": "Aman < 10%",
         "hint": "Nilai stok yang menganggur > 90 hari. Kas yang tidur."},
    ]

    return {
        "setting": setting,
        "kpis": kpis,
        "has_batch_data": bool(batches),
        "total_qty": total_qty, "total_sold": total_sold,
        "gross_profit": gross_profit, "cogs_sold": cogs_sold,
        "stock_value": stock_value, "stock_pieces": stock_pieces,
        "avg_gp": avg_gp, "avg_price": avg_price,
        "aov": aov, "order_count": order_count, "store_revenue": store_revenue,
        "net": net, "net_margin": net_margin,
        "latest_net": latest_net, "latest_name": latest_name,
        "fixed": fixed, "bep_pcs": bep_pcs, "bep_omzet": bep_omzet, "bep_daily": bep_daily,
        "reserve_min": reserve_min, "reserve_ideal": reserve_ideal,
        "aging": aging, "dead_value": dead_value, "dead_pct": dead_pct,
        "alloc": {
            "restock": setting.alloc_restock or 0,
            "reserve": setting.alloc_reserve or 0,
            "marketing": setting.alloc_marketing or 0,
            "ops": setting.alloc_ops or 0,
            "draw": setting.alloc_draw or 0,
        },
    }


@bp.route("/metrik")
@login_required
def metrics():
    data = _compute_ceo_metrics()
    return render_template("reports/metrics.html", **data)


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
