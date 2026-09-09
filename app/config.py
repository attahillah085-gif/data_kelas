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


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-ubah-di-produksi")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Identitas bisnis default (bisa diubah di halaman Pengaturan)
    APP_NAME = "The Girl House"

    # Web Push (VAPID)
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@thriftflow.id")

    # Akun owner awal (dipakai oleh seed.py)
    OWNER_NAME = os.environ.get("OWNER_NAME", "Pemilik")
    OWNER_EMAIL = os.environ.get("OWNER_EMAIL", "owner@thriftflow.id")
    OWNER_PASSWORD = os.environ.get("OWNER_PASSWORD", "owner123")
