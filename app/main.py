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
    Period,
    Setting,
    Transaction,
    User,
    CONTENT_PLANNED,
    EXPENSE,
    INCOME,
    ROLES,
    ROLE_LABELS,
    ROLE_OWNER,
)
from .services import compute_investor_shares, compute_profit_distribution, generate_content_reminders
from .utils import owner_required

bp = Blueprint("main", __name__)


@bp.route("/")
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
        # Cegah menghapus owner terakhir
        if u.is_owner and new_role != ROLE_OWNER and User.query.filter_by(role=ROLE_OWNER).count() <= 1:
            flash("Tidak bisa menurunkan peran owner terakhir.", "danger")
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
    if u.is_owner and User.query.filter_by(role=ROLE_OWNER, active=True).count() <= 1 and u.active:
        flash("Tidak bisa menonaktifkan owner aktif terakhir.", "danger")
        return redirect(url_for("main.users"))
    u.active = not u.active
    db.session.commit()
    flash(("Diaktifkan" if u.active else "Dinonaktifkan") + f": {u.name}", "info")
    return redirect(url_for("main.users"))
