"""Modul kalender konten: live, video, flyer, postingan."""
from __future__ import annotations

import calendar as _cal
from datetime import date, datetime, timedelta

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
INDO_MONTHS = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
               "Agustus", "September", "Oktober", "November", "Desember"]
INDO_DOW = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


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
    today = date.today()
    # Bulan yang ditampilkan (?bulan=YYYY-MM), default bulan ini
    try:
        y, m = [int(x) for x in (request.args.get("bulan") or "").split("-")]
        month_first = date(y, m, 1)
    except (ValueError, TypeError):
        month_first = today.replace(day=1)
    y, m = month_first.year, month_first.month

    cal = _cal.Calendar(firstweekday=0)  # Senin
    weeks_dates = cal.monthdatescalendar(y, m)
    start, end = weeks_dates[0][0], weeks_dates[-1][-1]
    start_dt = datetime(start.year, start.month, start.day)
    end_dt = datetime(end.year, end.month, end.day) + timedelta(days=1)

    in_range = (ContentSchedule.query
                .filter(ContentSchedule.scheduled_at >= start_dt,
                        ContentSchedule.scheduled_at < end_dt)
                .order_by(ContentSchedule.scheduled_at.asc()).all())
    one_time = [it for it in in_range if (it.repeat or "NONE") != "DAILY"]
    by_date = {}
    for it in one_time:
        by_date.setdefault(it.scheduled_at.date().isoformat(), []).append(it)

    routines = (ContentSchedule.query.filter_by(repeat="DAILY")
                .order_by(ContentSchedule.scheduled_at.asc()).all())

    weeks = []
    for wk in weeks_dates:
        weeks.append([{
            "iso": d.isoformat(), "day": d.day,
            "in_month": d.month == m, "is_today": d == today,
            "entries": by_date.get(d.isoformat(), []),
        } for d in wk])

    prev_m = (month_first - timedelta(days=1)).replace(day=1)
    next_m = (month_first + timedelta(days=32)).replace(day=1)
    now = datetime.utcnow()
    week_count = ContentSchedule.query.filter(
        ContentSchedule.status == CONTENT_PLANNED,
        ContentSchedule.repeat != "DAILY",
        ContentSchedule.scheduled_at >= now,
        ContentSchedule.scheduled_at <= now + timedelta(days=7),
    ).count()
    assignees = User.query.filter(
        User.role.in_([ROLE_OWNER, ROLE_MANAGER]), User.active.is_(True)
    ).all()

    return render_template(
        "content/index.html",
        weeks=weeks, routines=routines, edit_items=one_time + routines,
        month_label=f"{INDO_MONTHS[m]} {y}", dow=INDO_DOW,
        prev_bulan=f"{prev_m.year}-{prev_m.month:02d}",
        next_bulan=f"{next_m.year}-{next_m.month:02d}",
        this_bulan=f"{today.year}-{today.month:02d}",
        today_iso=today.isoformat(),
        assignees=assignees, kinds=CONTENT_KINDS, kind_labels=CONTENT_KIND_LABELS,
        platforms=PLATFORMS, week_count=week_count,
    )


@bp.route("/tambah", methods=["POST"])
@login_required
@manage_required
def add():
    title = (request.form.get("title") or "").strip()
    if not title:
        flash("Judul konten wajib diisi.", "danger")
        return redirect(request.referrer or url_for("content.index"))
    kind = request.form.get("kind")
    if kind not in CONTENT_KINDS:
        kind = "POST"
    repeat = "DAILY" if request.form.get("repeat") == "DAILY" else "NONE"
    time_str = (request.form.get("time") or "09:00").strip()
    if repeat == "DAILY":
        date_str = date.today().isoformat()
    else:
        date_str = (request.form.get("date") or date.today().isoformat()).strip()
    # Dukung juga field lama datetime-local bila dikirim
    scheduled_at = _parse_dt(request.form.get("scheduled_at")) if request.form.get("scheduled_at") \
        else _parse_dt(f"{date_str}T{time_str}")
    assignee_id = request.form.get("assignee_id", type=int)
    item = ContentSchedule(
        title=title,
        kind=kind,
        platform=(request.form.get("platform") or "").strip(),
        scheduled_at=scheduled_at,
        repeat=repeat,
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
    label = "Rutin harian" if repeat == "DAILY" else "Konten"
    flash(f"{label} '{title}' disimpan.", "success")
    return redirect(request.referrer or url_for("content.index"))


@bp.route("/<int:cid>/status", methods=["POST"])
@login_required
@manage_required
def set_status(cid):
    item = db.session.get(ContentSchedule, cid)
    if item is None:
        flash("Konten tidak ditemukan.", "danger")
        return redirect(request.referrer or url_for("content.index"))
    new_status = request.form.get("status")
    if new_status in (CONTENT_PLANNED, CONTENT_DONE, CONTENT_CANCELED):
        item.status = new_status
        db.session.commit()
        flash("Status konten diperbarui.", "success")
    return redirect(request.referrer or url_for("content.index"))


@bp.route("/<int:cid>/ubah", methods=["POST"])
@login_required
@manage_required
def edit(cid):
    item = db.session.get(ContentSchedule, cid)
    if item is None:
        flash("Konten tidak ditemukan.", "danger")
        return redirect(request.referrer or url_for("content.index"))
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
    return redirect(request.referrer or url_for("content.index"))


@bp.route("/<int:cid>/hapus", methods=["POST"])
@login_required
@manage_required
def delete(cid):
    item = db.session.get(ContentSchedule, cid)
    if item is None:
        flash("Konten tidak ditemukan.", "danger")
        return redirect(request.referrer or url_for("content.index"))
    title = item.title
    db.session.delete(item)
    db.session.commit()
    flash(f"Konten '{title}' dihapus.", "info")
    return redirect(request.referrer or url_for("content.index"))
