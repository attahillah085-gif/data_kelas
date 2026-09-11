"""Dashboard, pengaturan, dan manajemen pengguna."""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import (
    ContentSchedule,
    InventoryBatch,
    Investment,
    Order,
    Period,
    Product,
    Setting,
    Transaction,
    User,
    CONTENT_PLANNED,
    EXPENSE,
    INCOME,
    ORDER_COUNTED,
    ORDER_PENDING,
    ROLES,
    ROLE_LABELS,
    ROLE_INVESTOR,
    ROLE_MANAGER,
)
from .services import compute_investor_shares, compute_profit_distribution, generate_content_reminders
from .utils import owner_required, save_upload, generate_app_icons, remove_app_icons

bp = Blueprint("main", __name__)


@bp.route("/dashboard")
@login_required
def dashboard():
    # Pengingat konten (best-effort, tidak menggagalkan halaman)
    try:
        generate_content_reminders()
    except Exception:
        db.session.rollback()

    periods = Period.query.order_by(Period.start_date.desc(), Period.id.desc()).all()

    # Periode terpilih: dari query ?period=, atau periode OPEN pertama, atau terbaru
    selected = None
    pid = request.args.get("period", type=int)
    if pid:
        selected = db.session.get(Period, pid)
    if selected is None:
        selected = next((p for p in periods if p.is_open), None) or (periods[0] if periods else None)

    income = expense = net = 0
    expense_by_cat = []
    recent_tx = []
    if selected:
        income = selected.total_income
        expense = selected.total_expense
        net = selected.net_profit
        # rincian pengeluaran per kategori
        cat_map: dict[str, int] = {}
        for t in selected.transactions:
            if t.kind == EXPENSE:
                cat_map[t.category] = cat_map.get(t.category, 0) + t.amount
        expense_by_cat = sorted(cat_map.items(), key=lambda kv: kv[1], reverse=True)[:6]
        recent_tx = selected.transactions[:6]

    # Tren 6 periode terakhir (untuk grafik batang)
    trend = list(reversed(periods[:6]))
    trend_data = [
        {"name": p.name, "income": p.total_income, "expense": p.total_expense}
        for p in trend
    ]
    trend_max = max([max(d["income"], d["expense"]) for d in trend_data], default=0) or 1

    # Nilai stok tersisa (modal yang masih menempel di stok aktif)
    active_batches = InventoryBatch.query.filter_by(status="ACTIVE").all()
    stock_value = sum(b.remaining * b.cost_per_item for b in active_batches)
    stock_pieces = sum(b.remaining for b in active_batches)

    # Investor & modal
    shares, total_capital = compute_investor_shares()
    investor_count = len(shares)

    # Konten mendatang (7 hari)
    now = datetime.utcnow()
    upcoming = (
        ContentSchedule.query.filter(
            ContentSchedule.status == CONTENT_PLANNED,
            ContentSchedule.scheduled_at >= now - timedelta(hours=2),
        )
        .order_by(ContentSchedule.scheduled_at.asc())
        .limit(6)
        .all()
    )
    upcoming_week = ContentSchedule.query.filter(
        ContentSchedule.status == CONTENT_PLANNED,
        ContentSchedule.scheduled_at >= now,
        ContentSchedule.scheduled_at <= now + timedelta(days=7),
    ).count()

    # Statistik toko online
    store_pending = Order.query.filter_by(status=ORDER_PENDING).count()
    store_orders = Order.query.count()
    store_revenue = db.session.query(db.func.coalesce(db.func.sum(Order.total), 0)).filter(
        Order.status.in_(list(ORDER_COUNTED))
    ).scalar() or 0
    active_products = Product.query.filter_by(active=True).count()
    low_stock = (
        Product.query.filter(Product.active.is_(True), Product.stock > 0, Product.stock <= 3)
        .order_by(Product.stock.asc()).limit(5).all()
    )
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()

    # Bagian khusus investor
    my_investment = my_percent = my_payout = 0
    if current_user.is_investor:
        my_investment = sum(i.amount for i in current_user.investments)
        me = next((r for r in shares if r["user"].id == current_user.id), None)
        my_percent = me["percent"] if me else 0
        dist = compute_profit_distribution(selected)
        mine = next((r for r in dist["shares"] if r["user"].id == current_user.id), None)
        my_payout = mine["payout"] if mine else 0

    return render_template(
        "dashboard.html",
        periods=periods,
        selected=selected,
        income=income,
        expense=expense,
        net=net,
        expense_by_cat=expense_by_cat,
        recent_tx=recent_tx,
        trend_data=trend_data,
        trend_max=trend_max,
        stock_value=stock_value,
        stock_pieces=stock_pieces,
        total_capital=total_capital,
        investor_count=investor_count,
        upcoming=upcoming,
        upcoming_week=upcoming_week,
        my_investment=my_investment,
        my_percent=my_percent,
        my_payout=my_payout,
        store_pending=store_pending,
        store_orders=store_orders,
        store_revenue=store_revenue,
        active_products=active_products,
        low_stock=low_stock,
        recent_orders=recent_orders,
    )


# --------------------------------------------------------------------------
#  Pengaturan (owner)
# --------------------------------------------------------------------------
@bp.route("/pengaturan", methods=["GET", "POST"])
@login_required
@owner_required
def settings():
    s = Setting.get()
    if request.method == "POST":
        s.business_name = (request.form.get("business_name") or s.business_name).strip()
        s.tagline = (request.form.get("tagline") or "").strip()
        s.currency_symbol = (request.form.get("currency_symbol") or "Rp").strip()
        try:
            pct = int(request.form.get("owner_share_percent") or 0)
            s.owner_share_percent = min(max(pct, 0), 100)
        except ValueError:
            pass
        # --- Toko online ---
        s.store_active = bool(request.form.get("store_active"))
        s.whatsapp_number = "".join(ch for ch in (request.form.get("whatsapp_number") or "") if ch.isdigit())
        s.shop_description = (request.form.get("shop_description") or "").strip()
        s.hero_headline = (request.form.get("hero_headline") or "").strip()
        s.hero_subtext = (request.form.get("hero_subtext") or "").strip()
        s.hero_image = (request.form.get("hero_image") or "").strip()
        s.instagram = (request.form.get("instagram") or "").strip()
        s.tiktok = (request.form.get("tiktok") or "").strip()
        try:
            s.shipping_fee = max(int(float(request.form.get("shipping_fee") or 0)), 0)
        except ValueError:
            pass
        s.promo_active = bool(request.form.get("promo_active"))
        s.promo_text = (request.form.get("promo_text") or "").strip()
        s.promo_link = (request.form.get("promo_link") or "").strip()
        try:
            s.low_stock_threshold = max(int(request.form.get("low_stock_threshold") or 0), 0)
        except ValueError:
            pass
        try:
            s.monthly_target = max(int(float(request.form.get("monthly_target") or 0)), 0)
        except ValueError:
            pass
        # --- Logo toko (unggah / hapus) ---
        if request.form.get("logo_remove"):
            s.logo_path = ""
            remove_app_icons()
        logo_url = save_upload(request.files.get("logo"))
        if logo_url:
            s.logo_path = logo_url
            generate_app_icons(logo_url)   # ikon aplikasi (PWA) = logo
        db.session.commit()
        flash("Pengaturan disimpan.", "success")
        return redirect(url_for("main.settings"))
    return render_template("settings.html", s=s)


# --------------------------------------------------------------------------
#  Manajemen pengguna (owner)
# --------------------------------------------------------------------------
@bp.route("/pengguna")
@login_required
@owner_required
def users():
    all_users = User.query.order_by(User.created_at.asc()).all()
    return render_template("users.html", users=all_users, roles=ROLES, role_labels=ROLE_LABELS)


@bp.route("/pengguna/tambah", methods=["POST"])
@login_required
@owner_required
def user_add():
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    role = request.form.get("role") or "INVESTOR"
    password = request.form.get("password") or ""
    if not (name and email and len(password) >= 6 and role in ROLES):
        flash("Lengkapi data & kata sandi minimal 6 karakter.", "danger")
        return redirect(url_for("main.users"))
    if User.query.filter_by(email=email).first():
        flash("Email sudah dipakai.", "danger")
        return redirect(url_for("main.users"))
    u = User(name=name, email=email, role=role, active=True)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    flash(f"Akun {name} ({ROLE_LABELS.get(role, role)}) dibuat.", "success")
    return redirect(url_for("main.users"))


@bp.route("/pengguna/<int:uid>/ubah", methods=["POST"])
@login_required
@owner_required
def user_edit(uid):
    u = db.session.get(User, uid)
    if u is None:
        flash("Data tidak ditemukan.", "danger")
        return redirect(url_for("main.users"))
    u.name = (request.form.get("name") or u.name).strip()
    new_role = request.form.get("role")
    if new_role in ROLES:
        # Cegah menurunkan pengelola aktif terakhir jadi investor (agar tak terkunci)
        if (u.can_manage and new_role == ROLE_INVESTOR
                and User.query.filter(User.role == ROLE_MANAGER, User.active.is_(True)).count() <= 1):
            flash("Tidak bisa menurunkan pengelola aktif terakhir.", "danger")
            return redirect(url_for("main.users"))
        u.role = new_role
    pw = request.form.get("password")
    if pw:
        if len(pw) < 6:
            flash("Kata sandi minimal 6 karakter.", "danger")
            return redirect(url_for("main.users"))
        u.set_password(pw)
    db.session.commit()
    flash("Perubahan disimpan.", "success")
    return redirect(url_for("main.users"))


@bp.route("/pengguna/<int:uid>/status", methods=["POST"])
@login_required
@owner_required
def user_toggle(uid):
    u = db.session.get(User, uid)
    if u is None:
        flash("Data tidak ditemukan.", "danger")
        return redirect(url_for("main.users"))
    if u.id == current_user.id:
        flash("Tidak bisa menonaktifkan akun sendiri.", "danger")
        return redirect(url_for("main.users"))
    if (u.can_manage and u.active
            and User.query.filter(User.role == ROLE_MANAGER, User.active.is_(True)).count() <= 1):
        flash("Tidak bisa menonaktifkan pengelola aktif terakhir.", "danger")
        return redirect(url_for("main.users"))
    u.active = not u.active
    db.session.commit()
    flash(("Diaktifkan" if u.active else "Dinonaktifkan") + f": {u.name}", "info")
    return redirect(url_for("main.users"))
