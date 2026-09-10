"""Buat akun tim standar The Girl House (tanpa data demo).

Aman & idempotent: akun yang sudah ada dilewati, data lain tak disentuh.
Kata sandi dibuat ACAK (aman) lalu dicetak SEKALI di layar — repo publik jadi
tidak menyimpan kata sandi apa pun. Ganti ke yang mudah diingat lewat menu
Tim & Pengguna setelah login.

    python scripts/make_admins.py

Di dalam Docker (server):
    docker compose exec thegirlhouse python scripts/make_admins.py

Ingin menentukan kata sandi sendiri? Set variabel lingkungan (opsional):
    ATAHILLAH_PW=... CENDY_PW=... MIFTA_PW=... python scripts/make_admins.py
"""
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import User, ROLE_MANAGER, ROLE_INVESTOR

# (nama, email, peran, nama env untuk password opsional)
ACCOUNTS = [
    ("Atahillah", "atahillah@thegirlhouse.id", ROLE_MANAGER, "ATAHILLAH_PW"),
    ("Cendy", "cendy@thegirlhouse.id", ROLE_MANAGER, "CENDY_PW"),
    ("Mifta", "mifta@thegirlhouse.id", ROLE_INVESTOR, "MIFTA_PW"),
]


def main():
    app = create_app()
    created = []  # (email, peran, password) untuk dicetak
    with app.app_context():
        for name, email, role, env_key in ACCOUNTS:
            if User.query.filter_by(email=email).first():
                print(f"  = sudah ada, dilewati : {email}")
                continue
            password = os.environ.get(env_key) or secrets.token_urlsafe(9)
            u = User(name=name, email=email, role=role, active=True)
            u.set_password(password)
            db.session.add(u)
            created.append((email, role, password))
            print(f"  + dibuat              : {email} ({role})")
        db.session.commit()

    if created:
        print("\n=== SIMPAN KREDENSIAL INI (hanya tampil sekali) ===")
        for email, role, password in created:
            label = "Pengelola" if role == ROLE_MANAGER else "Investor"
            print(f"  {label:10} {email}   sandi: {password}")
        print("=====================================================")
        print("> Segera login & ganti kata sandi lewat menu Tim & Pengguna.")
    else:
        print("\nTidak ada akun baru dibuat (semua sudah ada).")


if __name__ == "__main__":
    main()
