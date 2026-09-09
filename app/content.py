"""Modul kalender konten: live, video, flyer, postingan."""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import (
    ContentSchedule,
    User,
    CONTENT_CANCELED,
    CONTENT_DONE,
    CONTENT_KIND_LABELS,
    CONTENT_KINDS,
    CONTENT_PLANNED,
    ROLE_MANAGER,
    ROLE_OWNER,
)
from .services import notify_managers
from .utils import manage_required

bp = Blueprint("content", __name__, url_prefix="/konten")

PLATFORMS = ["TikTok", "Instagram", "Shopee", "Facebook", "WhatsApp", "YouTube", "Offline", "Lainnya"]


def _parse_dt(value, default=None):
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except (TypeError, ValueError):
            continue
    return default or datetime.utcnow()


@bp.route("/")
@login_required
def index():
    kind = request.args.get("kind", "")
    status = request.args.get("status", "")
    q = ContentSchedule.query
    if kind in CONTENT_KINDS:
        q = q.filter_by(kind=kind)
    if status in (CONTENT_PLANNED, CONTENT_DONE, CONTENT_CANCELED):
        q = q.filter_by(status=status)

    now = datetime.utcnow()
    upcoming = (
        q.filter(ContentSchedule.scheduled_at >= now - timedelta(hours=3),
                 ContentSchedule.status == CONTENT_PLANNED)
        .order_by(ContentSchedule.scheduled_at.asc())
        .all()
        if not status else []
    )
    all_items = q.order_by(ContentSchedule.scheduled_at.desc()).all()

    assignees = User.query.filter(
        User.role.in_([ROLE_OWNER, ROLE_MANAGER]), User.active.is_(True)
    ).all()

    # Ringkasan 7 hari ke depan
    week_count = ContentSchedule.query.filter(
        ContentSchedule.status == CONTENT_PLANNED,
        ContentSchedule.scheduled_at >= now,
        ContentSchedule.scheduled_at <= now + timedelta(days=7),
    ).count()

    return render_template(
        "content/index.html",
        upcoming=upcoming, items=all_items, assignees=assignees,
        kinds=CONTENT_KINDS, kind_labels=CONTENT_KIND_LABELS, platforms=PLATFORMS,
        kind=kind, status=status, week_count=week_count,
        now_local=now.strftime("%Y-%m-%dT%H:%M"),
    )


@bp.route("/tambah", methods=["POST"])
@login_required
@manage_required
def add():
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Judul konten wajib diisi.", "danger")
        return redirect(url_for("content.index"))
    kind = request.form.get("kind")
    if kind not in CONTENT_KINDS:
        kind = "POST"
    assignee_id = request.form.get("assignee_id", type=int)
    item = ContentSchedule(
        title=title,
        kind=kind,
        platform=(request.form.get("platform") or "").strip(),
        scheduled_at=_parse_dt(request.form.get("scheduled_at")),
        note=(request.form.get("note") or "").strip(),
        assignee_id=assignee_id or None,
        created_by_id=current_user.id,
        status=CONTENT_PLANNED,
    )
    db.session.add(item)
    db.session.flush()
    # Beri tahu penanggung jawab
    if item.assignee_id and item.assignee_id != current_user.id:
        from .services import create_notification
        create_notification(
            item.assignee_id, f"Tugas konten baru: {title}",
            f"{item.kind_label} • {item.scheduled_at.strftime('%d %b %H:%M')}",
            category="info", link="/konten",
        )
    db.session.commit()
    flash(f"Konten '{title}' dijadwalkan.", "success")
    return redirect(url_for("content.index"))


@bp.route("/<int:cid>/status", methods=["POST"])
@login_required
@manage_required
def set_status(cid):
    item = db.session.get(ContentSchedule, cid)
    if item is None:
        flash("Konten tidak ditemukan.", "danger")
        return redirect(url_for("content.index"))
    new_status = request.form.get("status")
    if new_status in (CONTENT_PLANNED, CONTENT_DONE, CONTENT_CANCELED):
        item.status = new_status
        db.session.commit()
        flash("Status konten diperbarui.", "success")
    return redirect(url_for("content.index"))


@bp.route("/<int:cid>/ubah", methods=["POST"])
@login_required
@manage_required
def edit(cid):
    item = db.session.get(ContentSchedule, cid)
    if item is None:
        flash("Konten tidak ditemukan.", "danger")
        return redirect(url_for("content.index"))
    item.title = (request.form.get("title") or item.title).strip()
    kind = request.form.get("kind")
    if kind in CONTENT_KINDS:
        item.kind = kind
    item.platform = (request.form.get("platform") or "").strip()
    item.scheduled_at = _parse_dt(request.form.get("scheduled_at"), item.scheduled_at)
    item.note = (request.form.get("note") or "").strip()
    assignee_id = request.form.get("assignee_id", type=int)
    item.assignee_id = assignee_id or None
    item.reminder_sent = False  # jadwal berubah -> boleh diingatkan lagi
    db.session.commit()
    flash("Konten diperbarui.", "success")
    return redirect(url_for("content.index"))


@bp.route("/<int:cid>/hapus", methods=["POST"])
@login_required
@manage_required
def delete(cid):
    item = db.session.get(ContentSchedule, cid)
    if item is None:
        flash("Konten tidak ditemukan.", "danger")
        return redirect(url_for("content.index"))
    title = item.title
    db.session.delete(item)
    db.session.commit()
    flash(f"Konten '{title}' dihapus.", "info")
    return redirect(url_for("content.index"))
