"""Catatan & Target harian/bulanan (khusus pengelola)."""
from __future__ import annotations

from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .models import Note, Target, TARGET_CATEGORIES, TARGET_DAILY, TARGET_MONTHLY
from .utils import manage_required

bp = Blueprint("planner", __name__, url_prefix="/rencana")


def _back():
    return redirect(request.referrer or url_for("planner.index"))


def _month_start(d: date | None = None) -> date:
    return (d or date.today()).replace(day=1)


@bp.route("/")
@login_required
@manage_required
def index():
    today = date.today()
    mstart = _month_start(today)
    daily = (Target.query.filter_by(period=TARGET_DAILY, target_date=today)
             .order_by(Target.done.asc(), Target.created_at.asc()).all())
    monthly = (Target.query.filter_by(period=TARGET_MONTHLY, target_date=mstart)
               .order_by(Target.done.asc(), Target.created_at.asc()).all())
    notes = Note.query.order_by(Note.pinned.desc(), Note.created_at.desc()).all()
    return render_template(
        "planner/index.html", daily=daily, monthly=monthly, notes=notes,
        categories=TARGET_CATEGORIES, today=today, mstart=mstart,
    )


@bp.route("/target/tambah", methods=["POST"])
@login_required
@manage_required
def target_add():
    title = (request.form.get("title") or "").strip()
    period = request.form.get("period")
    period = period if period in (TARGET_DAILY, TARGET_MONTHLY) else TARGET_DAILY
    category = (request.form.get("category") or "Umum").strip()
    if not title:
        flash("Isi dulu targetnya ya.", "danger")
        return _back()
    td = date.today() if period == TARGET_DAILY else _month_start()
    db.session.add(Target(
        title=title, period=period, category=category, target_date=td,
        created_by_id=current_user.id,
    ))
    db.session.commit()
    flash("Target ditambahkan.", "success")
    return _back()


@bp.route("/target/<int:tid>/toggle", methods=["POST"])
@login_required
@manage_required
def target_toggle(tid):
    t = db.session.get(Target, tid)
    if t:
        t.done = not t.done
        t.done_at = datetime.utcnow() if t.done else None
        db.session.commit()
    return _back()


@bp.route("/target/<int:tid>/hapus", methods=["POST"])
@login_required
@manage_required
def target_delete(tid):
    t = db.session.get(Target, tid)
    if t:
        db.session.delete(t)
        db.session.commit()
        flash("Target dihapus.", "info")
    return _back()


@bp.route("/catatan/tambah", methods=["POST"])
@login_required
@manage_required
def note_add():
    body = (request.form.get("body") or "").strip()
    category = (request.form.get("category") or "Umum").strip()
    pinned = bool(request.form.get("pinned"))
    if not body:
        flash("Catatannya masih kosong.", "danger")
        return _back()
    db.session.add(Note(body=body, category=category, pinned=pinned,
                        created_by_id=current_user.id))
    db.session.commit()
    flash("Catatan disimpan.", "success")
    return _back()


@bp.route("/catatan/<int:nid>/pin", methods=["POST"])
@login_required
@manage_required
def note_pin(nid):
    n = db.session.get(Note, nid)
    if n:
        n.pinned = not n.pinned
        db.session.commit()
    return _back()


@bp.route("/catatan/<int:nid>/hapus", methods=["POST"])
@login_required
@manage_required
def note_delete(nid):
    n = db.session.get(Note, nid)
    if n:
        db.session.delete(n)
        db.session.commit()
        flash("Catatan dihapus.", "info")
    return _back()
