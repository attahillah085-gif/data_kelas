"""Konfigurasi aplikasi ThriftFlow."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Muat variabel dari file .env bila ada
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _database_uri() -> str:
    """Kembalikan URI database.

    Default memakai SQLite yang disimpan di folder ``instance/`` sehingga
    aplikasi langsung jalan tanpa setup. Set ``DATABASE_URL`` untuk memakai
    PostgreSQL/MySQL di produksi.
    """
    url = os.environ.get("DATABASE_URL")
    if url:
        # Kompatibilitas: paksa pakai driver psycopg (v3) untuk PostgreSQL.
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    instance = BASE_DIR / "instance"
    instance.mkdir(exist_ok=True)
    return f"sqlite:///{instance / 'thriftflow.db'}"


def _engine_options(uri: str) -> dict:
    """Opsi engine yang aman untuk masing-masing database."""
    if uri.startswith("sqlite"):
        # timeout menghindari error "database is locked" saat beberapa
        # request menulis bersamaan (dipasangkan dengan mode WAL di app factory).
        return {"connect_args": {"timeout": 30}}
    return {"pool_pre_ping": True}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-ubah-di-produksi")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(SQLALCHEMY_DATABASE_URI)

    # Keamanan cookie session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Set COOKIE_SECURE=1 di produksi (HTTPS) agar cookie hanya lewat HTTPS.
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes")

    # Batas ukuran upload (gambar produk) — 6 MB
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024

    # Identitas bisnis default (bisa diubah di halaman Pengaturan)
    APP_NAME = "The Girl House"

    # Web Push (VAPID)
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@thegirlhouse.id")

    # Akun owner awal (dipakai oleh seed.py)
    OWNER_NAME = os.environ.get("OWNER_NAME", "Pemilik")
    OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "owner@thegirlhouse.id")
    OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "owner123")
