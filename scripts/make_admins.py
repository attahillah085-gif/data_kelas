"""Buat akun tim standar The Girl House (tanpa data demo).

Aman dijalankan kapan saja: akun yang sudah ada dilewati (idempotent),
data lain tidak disentuh. Cocok untuk menyiapkan akun login di server.

    python scripts/make_admins.py

Di dalam Docker (server):
    docker compose exec thegirlhouse python scripts/make_admins.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import User, ROLE_MANAGER, ROLE_INVESTOR

# Daftar akun standar: (nama, email, peran, kata sandi)
ACCOUNTS = [
    ("Atahillah", "atahillah@thegirlhouse.id", ROLE_MANAGER, "atahillah123"),
    ("Cendy", "cendy@thegirlhouse.id", ROLE_MANAGER, "cendy123"),
    ("Mifta", "mifta@thegirlhouse.id", ROLE_INVESTOR, "mifta123"),
]


def main():
    app = create_app()
    with app.app_context():
        for name, email, role, password in ACCOUNTS:
            existing = User.query.filter_by(email=email).first()
            if existing:
                print(f"  = sudah ada, dilewati : {email}")
                continue
            u = User(name=name, email=email, role=role, active=True)
            u.set_password(password)
            db.session.add(u)
            print(f"  + dibuat              : {email} ({role})")
        db.session.commit()

    print("\nSelesai. Kredensial login:")
    for name, email, role, password in ACCOUNTS:
        label = "Pengelola" if role == ROLE_MANAGER else "Investor"
        print(f"  {label:10} {email} / {password}")
    print("\n> Ganti kata sandi setelah login pertama (menu Tim & Pengguna / profil).")


if __name__ == "__main__":
    main()
