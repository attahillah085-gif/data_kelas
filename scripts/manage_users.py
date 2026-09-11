"""Lihat & kelola akun The Girl House dari server (alat darurat).

Berguna saat lupa sandi / terkunci. Data lain tidak disentuh.

Lihat semua akun yang ADA di server:
    python scripts/manage_users.py

Buat akun baru ATAU reset sandi akun yang sudah ada:
    python scripts/manage_users.py <email> <sandi_baru> [pengelola|investor]

Contoh (di server, dalam Docker):
    docker compose exec thegirlhouse python scripts/manage_users.py
    docker compose exec thegirlhouse python scripts/manage_users.py atahillah@thegirlhouse.id sandiBaru123 pengelola
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import User, ROLE_MANAGER, ROLE_INVESTOR, ROLE_LABELS


def list_users():
    users = User.query.order_by(User.created_at.asc()).all()
    if not users:
        print("  (belum ada akun sama sekali — buka /setup di situs untuk membuat akun pertama)")
        return
    print(f"  {'EMAIL':38} {'PERAN':10} AKTIF")
    print("  " + "-" * 60)
    for u in users:
        print(f"  {u.email:38} {ROLE_LABELS.get(u.role, u.role):10} {'ya' if u.active else 'TIDAK'}")


def upsert(email, password, role_word):
    email = email.strip().lower()
    role = ROLE_INVESTOR if str(role_word).lower().startswith(("inv",)) else ROLE_MANAGER
    if len(password) < 6:
        print("  Kata sandi minimal 6 karakter."); return
    u = User.query.filter_by(email=email).first()
    if u:
        u.set_password(password)
        u.active = True
        db.session.commit()
        print(f"  ✓ Sandi di-reset untuk akun yang sudah ada: {email} ({ROLE_LABELS.get(u.role, u.role)})")
    else:
        u = User(name=email.split("@")[0].title(), email=email, role=role, active=True)
        u.set_password(password)
        db.session.add(u); db.session.commit()
        print(f"  ✓ Akun baru dibuat: {email} ({ROLE_LABELS.get(role, role)})")
    print(f"    Login: {email} / {password}")


def main():
    app = create_app()
    with app.app_context():
        args = sys.argv[1:]
        if not args:
            print("\nDaftar akun di server:")
            list_users()
            print("\nUntuk buat/reset: python scripts/manage_users.py <email> <sandi> [pengelola|investor]")
            return
        if len(args) < 2:
            print("  Format: python scripts/manage_users.py <email> <sandi> [pengelola|investor]"); return
        email, password = args[0], args[1]
        role_word = args[2] if len(args) > 2 else "pengelola"
        upsert(email, password, role_word)
        print("\nDaftar akun sekarang:")
        list_users()


if __name__ == "__main__":
    main()
