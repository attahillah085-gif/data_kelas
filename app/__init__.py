"""ThriftFlow — application factory."""
from __future__ import annotations

from datetime import datetime

from flask import Flask, Response, render_template, send_from_directory
from flask_login import current_user

from .config import Config
from .extensions import db, login_manager
from .utils import register_filters


def _auto_migrate_sqlite() -> None:
    """Tambah kolom baru pada tabel yang sudah ada (SQLite) tanpa hapus data.

    Dipanggil saat startup. Aman: hanya menambah kolom yang belum ada, sesuai
    definisi model — sehingga penambahan fitur tidak butuh reset database.
    """
    try:
        from sqlalchemy import inspect, text
        if db.engine.url.get_backend_name() != "sqlite":
            return
        insp = inspect(db.engine)
        tables = set(insp.get_table_names())
        with db.engine.begin() as conn:
            for table in db.metadata.sorted_tables:
                if table.name not in tables:
                    continue
                have = {c["name"] for c in insp.get_columns(table.name)}
                for col in table.columns:
                    if col.name in have:
                        continue
                    try:
                        col_type = col.type.compile(dialect=db.engine.dialect)
                    except Exception:
                        col_type = "TEXT"
                    ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'
                    default = getattr(getattr(col, "default", None), "arg", None)
                    if isinstance(default, bool):
                        ddl += f" DEFAULT {1 if default else 0}"
                    elif isinstance(default, (int, float)):
                        ddl += f" DEFAULT {default}"
                    elif isinstance(default, str):
                        ddl += " DEFAULT '" + default.replace("'", "''") + "'"
                    conn.execute(text(ddl))
    except Exception:
        # Auto-migrasi tidak boleh menggagalkan startup
        pass


def _ensure_vapid_keys(app: Flask) -> None:
    """Pastikan kunci VAPID ada agar notifikasi push jalan tanpa setup manual.

    Jika belum di-set lewat environment, buat sekali & simpan permanen di
    instance/vapid.json (folder volume) sehingga tetap sama setelah restart.
    """
    if app.config.get("VAPID_PUBLIC_KEY") and app.config.get("VAPID_PRIVATE_KEY"):
        return
    import base64
    import json
    from pathlib import Path
    try:
        from .config import BASE_DIR
        store = Path(BASE_DIR) / "instance"
        store.mkdir(exist_ok=True)
        f = store / "vapid.json"
        keys = None
        if f.exists():
            try:
                keys = json.loads(f.read_text())
            except Exception:
                keys = None
        if not keys:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.primitives.asymmetric import ec

            def b64u(b: bytes) -> str:
                return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

            priv = ec.generate_private_key(ec.SECP256R1())
            priv_val = priv.private_numbers().private_value.to_bytes(32, "big")
            pub = priv.public_key().public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint,
            )
            keys = {"public": b64u(pub), "private": b64u(priv_val)}
            f.write_text(json.dumps(keys))
        app.config["VAPID_PUBLIC_KEY"] = keys["public"]
        app.config["VAPID_PRIVATE_KEY"] = keys["private"]
    except Exception:
        # Tanpa VAPID, notifikasi in-app tetap jalan; push saja yang nonaktif.
        pass


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)
    _ensure_vapid_keys(app)

    # Di belakang reverse-proxy (Caddy/Nginx): hormati header X-Forwarded-*
    # agar url_for(_external), redirect, sitemap & Open Graph memakai https + host benar.
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    except Exception:
        pass

    db.init_app(app)
    login_manager.init_app(app)
    register_filters(app)

    # Import model agar terdaftar sebelum create_all
    from . import models  # noqa: F401

    # Blueprint
    from .auth import bp as auth_bp
    from .main import bp as main_bp
    from .finance import bp as finance_bp
    from .inventory import bp as inventory_bp
    from .content import bp as content_bp
    from .investors import bp as investors_bp
    from .notifications import bp as notifications_bp
    from .store import bp as store_bp
    from .catalog import bp as catalog_bp
    from .reports import bp as reports_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(content_bp)
    app.register_blueprint(investors_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(store_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(reports_bp)

    with app.app_context():
        db.create_all()
        # SQLite: aktifkan WAL agar lebih tahan akses baca/tulis bersamaan
        if db.engine.url.get_backend_name() == "sqlite":
            try:
                from sqlalchemy import text
                db.session.execute(text("PRAGMA journal_mode=WAL"))
                db.session.commit()
            except Exception:
                db.session.rollback()
        # Auto-migrasi ringan: tambah kolom baru tanpa menghapus data
        _auto_migrate_sqlite()

    _register_context(app)
    _register_pwa(app)
    _register_errors(app)
    return app


def _register_context(app: Flask) -> None:
    import os
    from flask import url_for
    from .models import Notification, Order, Review, Setting, ORDER_PENDING

    def _detect_logo():
        for name in ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp", "logo.svg"):
            if os.path.exists(os.path.join(app.static_folder, "brand", name)):
                return url_for("static", filename=f"brand/{name}")
        return None

    @app.context_processor
    def inject_globals():
        unread = 0
        pending_orders = 0
        pending_reviews = 0
        recent_notifs = []
        setting = None
        brand_logo = _detect_logo()
        try:
            setting = Setting.get()
            # Logo unggahan (dari Pengaturan) diprioritaskan; jika kosong pakai file bawaan.
            if setting and getattr(setting, "logo_path", ""):
                brand_logo = setting.logo_path
            if current_user.is_authenticated:
                unread = Notification.query.filter_by(
                    user_id=current_user.id, is_read=False
                ).count()
                recent_notifs = (
                    Notification.query.filter_by(user_id=current_user.id)
                    .order_by(Notification.created_at.desc())
                    .limit(8)
                    .all()
                )
                if current_user.can_manage:
                    pending_orders = Order.query.filter_by(status=ORDER_PENDING).count()
                    pending_reviews = Review.query.filter_by(approved=False).count()
        except Exception:
            pass
        # Ikon aplikasi (apple-touch) = ikon hasil logo bila ada, else bawaan.
        from flask import url_for
        from .utils import app_icons_exist
        try:
            app_icon = (url_for("static", filename="uploads/appicon-192.png")
                        if app_icons_exist()
                        else url_for("static", filename="icons/icon-192.png"))
        except Exception:
            app_icon = "/static/icons/icon-192.png"
        return {
            "setting": setting,
            "unread_count": unread,
            "pending_orders": pending_orders,
            "pending_reviews": pending_reviews,
            "recent_notifs": recent_notifs,
            "brand_logo": brand_logo,
            "app_icon": app_icon,
            "now": datetime.utcnow(),
            "vapid_public_key": app.config.get("VAPID_PUBLIC_KEY", ""),
        }


def _register_pwa(app: Flask) -> None:
    @app.route("/sw.js")
    def service_worker():
        resp = send_from_directory(app.static_folder, "sw.js")
        resp.headers["Content-Type"] = "application/javascript"
        resp.headers["Service-Worker-Allowed"] = "/"
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    @app.route("/manifest.webmanifest")
    def manifest():
        import json as _json
        from flask import Response, url_for
        from .utils import app_icons_exist
        name = "The Girl House"
        try:
            from .models import Setting
            s = Setting.get()
            if s and s.business_name:
                name = s.business_name
        except Exception:
            pass
        # Ikon: pakai hasil generate dari logo bila ada; kalau tidak, ikon bawaan.
        if app_icons_exist():
            icons = [
                {"src": url_for("static", filename="uploads/appicon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": url_for("static", filename="uploads/appicon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
                {"src": url_for("static", filename="uploads/appicon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            ]
        else:
            icons = [
                {"src": url_for("static", filename="icons/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": url_for("static", filename="icons/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
                {"src": url_for("static", filename="icons/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
            ]
        data = {
            "name": f"{name} — Manajemen", "short_name": name[:20], "id": "/",
            "start_url": "/dashboard", "scope": "/", "display": "standalone",
            "orientation": "portrait-primary",
            "background_color": "#fff8fb", "theme_color": "#db6a9d", "lang": "id",
            "categories": ["business", "finance", "productivity"],
            "icons": icons,
            "shortcuts": [
                {"name": "Keuangan", "url": "/keuangan"},
                {"name": "Inventori", "url": "/inventori"},
                {"name": "Kalender Konten", "url": "/konten"},
            ],
        }
        return Response(_json.dumps(data), content_type="application/manifest+json")

    @app.route("/offline")
    def offline():
        return render_template("offline.html")


def _register_errors(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(e):  # noqa: ANN001
        return render_template("error.html", code=403,
                               message="Kamu tidak punya akses ke halaman ini."), 403

    @app.errorhandler(404)
    def not_found(e):  # noqa: ANN001
        return render_template("error.html", code=404,
                               message="Halaman tidak ditemukan."), 404

    @app.errorhandler(401)
    def unauthorized(e):  # noqa: ANN001
        return render_template("error.html", code=401,
                               message="Silakan masuk terlebih dahulu."), 401
