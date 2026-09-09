"""Autentikasi: login, logout, dan setup awal (first-run)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import ROLE_OWNER, User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    # Jika belum ada user sama sekali -> arahkan ke setup awal
    if User.query.count() == 0:
        return redirect(url_for("auth.setup"))

    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.active:
                flash("Akun kamu dinonaktifkan. Hubungi pemilik.", "danger")
                return render_template("auth/login.html")
            login_user(user, remember=remember)
            flash(f"Selamat datang kembali, {user.name}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("main.dashboard"))
        flash("Email atau kata sandi salah.", "danger")

    return render_template("auth/login.html")


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Pembuatan akun pemilik pertama kali (hanya saat belum ada user)."""
    if User.query.count() > 0:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not (name and email and len(password) >= 6):
            flash("Lengkapi nama, email, dan kata sandi minimal 6 karakter.", "danger")
            return render_template("auth/setup.html")
        owner = User(name=name, email=email, role=ROLE_OWNER, active=True)
        owner.set_password(password)
        db.session.add(owner)
        db.session.commit()
        login_user(owner)
        flash("Akun pemilik berhasil dibuat. Selamat datang di ThriftFlow!", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("auth/setup.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Kamu sudah keluar.", "info")
    return redirect(url_for("auth.login"))
