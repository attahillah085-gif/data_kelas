"""Notifikasi in-app + endpoint Web Push (opsional)."""
from __future__ import annotations

import json

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    request,
    render_template,
    url_for,
)
from flask_login import current_user, login_required

from .extensions import db
from .models import Notification, PushSubscription
from .services import generate_content_reminders, push_enabled

bp = Blueprint("notifications", __name__)


@bp.route("/notifikasi")
@login_required
def index():
    items = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(100)
        .all()
    )
    return render_template("notifications.html", items=items)


@bp.route("/notifikasi/baca/<int:nid>", methods=["POST"])
@login_required
def mark_read(nid):
    n = db.session.get(Notification, nid)
    if n and n.user_id == current_user.id:
        n.is_read = True
        db.session.commit()
    link = n.link if (n and n.link) else url_for("notifications.index")
    return redirect(link)


@bp.route("/notifikasi/baca-semua", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {"is_read": True}
    )
    db.session.commit()
    flash("Semua notifikasi ditandai terbaca.", "info")
    return redirect(url_for("notifications.index"))


# -------------------- API untuk badge & polling --------------------
@bp.route("/api/notifications/unread")
@login_required
def unread_api():
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    items = (
        Notification.query.filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(6)
        .all()
    )
    return jsonify({
        "count": count,
        "items": [
            {"id": n.id, "title": n.title, "body": n.body,
             "category": n.category, "link": n.link,
             "read": n.is_read, "at": n.created_at.strftime("%d %b %H:%M")}
            for n in items
        ],
    })


# -------------------- Web Push --------------------
@bp.route("/api/push/public-key")
@login_required
def push_public_key():
    return jsonify({
        "enabled": push_enabled(),
        "publicKey": current_app.config.get("VAPID_PUBLIC_KEY", ""),
    })


@bp.route("/api/push/subscribe", methods=["POST"])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    if not endpoint:
        return jsonify({"ok": False, "error": "endpoint kosong"}), 400
    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.user_id = current_user.id
        existing.subscription_json = json.dumps(data)
    else:
        db.session.add(PushSubscription(
            user_id=current_user.id, endpoint=endpoint, subscription_json=json.dumps(data)
        ))
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/api/push/test", methods=["POST"])
@login_required
def push_test():
    """Kirim notifikasi percobaan ke perangkat pengguna saat ini."""
    from .services import _push_to_user
    if not push_enabled():
        return jsonify({"ok": False, "reason": "server"})
    devices = PushSubscription.query.filter_by(user_id=current_user.id).count()
    if devices == 0:
        return jsonify({"ok": False, "reason": "no_sub"})
    _push_to_user(
        current_user.id,
        "Tes Notifikasi 🎉",
        "Mantap! Notifikasi HP The Girl House sudah aktif.",
        link=url_for("notifications.index"),
    )
    db.session.commit()
    return jsonify({"ok": True, "devices": devices})


@bp.route("/api/push/unsubscribe", methods=["POST"])
@login_required
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    if endpoint:
        PushSubscription.query.filter_by(endpoint=endpoint).delete()
        db.session.commit()
    return jsonify({"ok": True})


# -------------------- Cron pengingat konten --------------------
@bp.route("/tasks/reminders", methods=["GET", "POST"])
def run_reminders():
    """Endpoint untuk dijalankan cron eksternal.

    Amankan dengan token: /tasks/reminders?token=SECRET_KEY
    Bila sudah login sebagai user, token tidak diperlukan.
    """
    token = request.args.get("token", "")
    if not current_user.is_authenticated:
        if not token or token != current_app.config.get("SECRET_KEY"):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
    created = generate_content_reminders()
    return jsonify({"ok": True, "reminders_created": created})
