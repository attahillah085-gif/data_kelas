"""Logika bisnis lintas modul: notifikasi, push, bagi hasil, pengingat."""
from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta

from flask import current_app

from .extensions import db
from .models import (
    ContentSchedule,
    Investment,
    Notification,
    Order,
    Period,
    PushSubscription,
    Setting,
    Transaction,
    User,
    CONTENT_PLANNED,
    INCOME,
    ORDER_COUNTED,
    ROLE_MANAGER,
    ROLE_OWNER,
)


# --------------------------------------------------------------------------
#  Notifikasi
# --------------------------------------------------------------------------
def create_notification(user_id, title, body="", category="info", link="", push=True):
    notif = Notification(
        user_id=user_id, title=title, body=body, category=category, link=link
    )
    db.session.add(notif)
    db.session.flush()
    if push:
        _push_to_user(user_id, title, body, link)
    return notif


def notify_managers(title, body="", category="info", link="", exclude_id=None):
    """Kirim notifikasi ke semua owner & pengelola."""
    q = User.query.filter(User.role.in_([ROLE_OWNER, ROLE_MANAGER]), User.active.is_(True))
    for u in q.all():
        if exclude_id and u.id == exclude_id:
            continue
        create_notification(u.id, title, body, category, link)


def notify_all(title, body="", category="info", link=""):
    for u in User.query.filter(User.active.is_(True)).all():
        create_notification(u.id, title, body, category, link)


# --------------------------------------------------------------------------
#  Web Push (opsional — aman bila pywebpush/VAPID tidak tersedia)
# --------------------------------------------------------------------------
def push_enabled() -> bool:
    return bool(
        current_app.config.get("VAPID_PUBLIC_KEY")
        and current_app.config.get("VAPID_PRIVATE_KEY")
    )


def _push_to_user(user_id, title, body, link=""):
    if not push_enabled():
        return
    try:
        from pywebpush import webpush, WebPushException  # noqa: WPS433
    except Exception:  # pragma: no cover - pywebpush belum terpasang
        return

    payload = json.dumps({"title": title, "body": body, "url": link or "/"})
    subs = PushSubscription.query.filter_by(user_id=user_id).all()
    for sub in subs:
        try:
            webpush(
                subscription_info=json.loads(sub.subscription_json),
                data=payload,
                vapid_private_key=current_app.config["VAPID_PRIVATE_KEY"],
                vapid_claims={"sub": current_app.config["VAPID_SUBJECT"]},
            )
        except WebPushException as exc:  # pragma: no cover
            # Langganan kadaluarsa/ditolak -> hapus
            if getattr(exc, "response", None) is not None and exc.response.status_code in (404, 410):
                db.session.delete(sub)
        except Exception:  # pragma: no cover
            pass


# --------------------------------------------------------------------------
#  Investor & bagi hasil
# --------------------------------------------------------------------------
def compute_investor_shares():
    """Kembalikan daftar dict {user, total, percent} berdasar total modal."""
    investors = (
        db.session.query(User)
        .join(Investment, Investment.user_id == User.id)
        .filter(User.active.is_(True))
        .distinct()
        .all()
    )
    rows = []
    total_capital = 0
    for u in investors:
        amt = sum(i.amount for i in u.investments)
        if amt <= 0:
            continue
        rows.append({"user": u, "total": amt, "percent": 0.0})
        total_capital += amt
    for r in rows:
        r["percent"] = round(r["total"] / total_capital * 100, 2) if total_capital else 0.0
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows, total_capital


def compute_profit_distribution(period: Period | None):
    """Hitung skema bagi hasil untuk sebuah periode.

    Laba bersih dibagi: porsi bisnis/owner ditahan (owner_share_percent),
    sisanya dibagi ke investor sesuai proporsi modal.
    """
    setting = Setting.get()
    net = period.net_profit if period else 0
    owner_percent = setting.owner_share_percent or 0
    owner_cut = round(net * owner_percent / 100) if net > 0 else 0
    investor_pool = max(net - owner_cut, 0)

    shares, total_capital = compute_investor_shares()
    for r in shares:
        r["payout"] = round(investor_pool * r["percent"] / 100)
    return {
        "net_profit": net,
        "owner_percent": owner_percent,
        "owner_cut": owner_cut,
        "investor_pool": investor_pool,
        "total_capital": total_capital,
        "shares": shares,
    }


# --------------------------------------------------------------------------
#  Pengingat konten
# --------------------------------------------------------------------------
def generate_content_reminders(window_hours: int = 24):
    """Buat notifikasi untuk konten yang akan tayang dalam `window_hours`.

    Dipanggil saat aplikasi diakses (best-effort) atau via endpoint cron.
    """
    now = datetime.utcnow()
    horizon = now + timedelta(hours=window_hours)
    due = (
        ContentSchedule.query.filter(
            ContentSchedule.status == CONTENT_PLANNED,
            ContentSchedule.reminder_sent.is_(False),
            ContentSchedule.scheduled_at <= horizon,
            ContentSchedule.scheduled_at >= now - timedelta(hours=1),
        ).all()
    )
    count = 0
    for item in due:
        when = item.scheduled_at.strftime("%d %b %H:%M")
        body = f"{item.kind_label} • {item.platform or 'tanpa platform'} • {when}"
        # Beri tahu penanggung jawab bila ada, kalau tidak beri tahu pengelola
        if item.assignee_id:
            create_notification(
                item.assignee_id,
                f"Pengingat: {item.title}",
                body,
                category="reminder",
                link="/konten",
            )
        else:
            notify_managers(
                f"Pengingat konten: {item.title}", body, category="reminder", link="/konten"
            )
        item.reminder_sent = True
        count += 1
    if count:
        db.session.commit()
    return count


# --------------------------------------------------------------------------
#  Marketplace / pesanan
# --------------------------------------------------------------------------
def generate_order_code() -> str:
    """Kode pesanan unik singkat, mis. TGH-7F3K9Q."""
    for _ in range(10):
        code = "TGH-" + secrets.token_hex(3).upper()
        if not Order.query.filter_by(code=code).first():
            return code
    return "TGH-" + secrets.token_hex(5).upper()


def _open_period() -> Period | None:
    return Period.query.filter_by(status="OPEN").order_by(Period.start_date.desc()).first()


def apply_order_effects(order: Order) -> str | None:
    """Sinkronkan efek pesanan ke stok & keuangan berdasarkan statusnya.

    - Status dihitung (PAID/SHIPPED/DONE) -> kurangi stok (sekali) & catat
      pemasukan di periode berjalan (sekali).
    - Status tidak dihitung (PENDING/CONFIRMED/CANCELED) -> kembalikan stok &
      hapus pemasukan terkait bila sebelumnya sudah diterapkan.

    Mengembalikan pesan peringatan (mis. tidak ada periode terbuka) atau None.
    """
    from .models import Product, ProductVariant, Setting  # lokal: hindari import melingkar

    warning = None
    counted = order.status in ORDER_COUNTED
    low_alerts = []  # (nama, sisa) untuk notifikasi stok menipis

    if counted and not order.stock_applied:
        # Kurangi stok (varian bila ada, jika tidak stok produk)
        for item in order.items:
            if item.variant_id:
                v = db.session.get(ProductVariant, item.variant_id)
                if v:
                    v.stock = max((v.stock or 0) - item.qty, 0)
                    low_alerts.append((item.display_name, v.stock))
            elif item.product_id:
                prod = db.session.get(Product, item.product_id)
                if prod:
                    prod.stock = max((prod.stock or 0) - item.qty, 0)
                    low_alerts.append((item.product_name, prod.stock))
        order.stock_applied = True
        if order.paid_at is None:
            order.paid_at = datetime.utcnow()
        # Notifikasi stok menipis
        try:
            threshold = Setting.get().low_stock_threshold or 0
            for name, left in low_alerts:
                if 0 <= left <= threshold:
                    notify_managers(
                        "Stok menipis" + (" — habis!" if left == 0 else ""),
                        f"{name}: sisa {left}", category="warning", link="/kelola/produk",
                    )
        except Exception:
            pass
        # Catat pemasukan sekali (bila belum ada transaksi terkait)
        if not order.transactions:
            period = _open_period()
            if period:
                db.session.add(Transaction(
                    period_id=period.id, kind=INCOME, category="Penjualan",
                    amount=order.total, description=f"Pesanan toko {order.code}",
                    date=datetime.utcnow().date(), order_id=order.id,
                ))
                order.period_id = period.id
            else:
                warning = ("Belum ada periode keuangan terbuka — stok sudah dikurangi, "
                           "tapi pemasukan belum tercatat. Buat periode lalu ubah status ulang.")

    elif not counted and order.stock_applied:
        # Kembalikan stok
        for item in order.items:
            if item.variant_id:
                v = db.session.get(ProductVariant, item.variant_id)
                if v:
                    v.stock = (v.stock or 0) + item.qty
            elif item.product_id:
                prod = db.session.get(Product, item.product_id)
                if prod:
                    prod.stock = (prod.stock or 0) + item.qty
        order.stock_applied = False
        order.paid_at = None
        # Hapus pemasukan terkait
        for tx in list(order.transactions):
            db.session.delete(tx)
        order.period_id = None

    return warning


def whatsapp_link(number: str, message: str) -> str:
    """Bangun URL wa.me dengan pesan ter-encode."""
    from urllib.parse import quote
    num = "".join(ch for ch in (number or "") if ch.isdigit())
    return f"https://wa.me/{num}?text={quote(message)}"
