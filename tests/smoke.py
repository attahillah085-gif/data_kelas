"""Smoke test The Girl House — dijalankan CI GitHub & lokal.

Memverifikasi: app boot, toko publik tampil, setup pengelola, login,
akses penuh pengelola, dan investor read-only. Keluar kode !=0 bila gagal.

    python tests/smoke.py
"""
import os
import sys

# Pastikan root proyek ada di path saat dijalankan sebagai skrip
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Product, User, ROLE_INVESTOR


def ok(cond, msg):
    status = "OK " if cond else "GAGAL "
    print(f"  [{status}] {msg}")
    if not cond:
        ok.failed = True


ok.failed = False


def main():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    # Data minimal untuk pengujian
    with app.app_context():
        db.create_all()
        if not Product.query.first():
            db.session.add(Product(name="Kaos Uji", slug="kaos-uji", price=50000,
                                   category="Kaos", stock=5, active=True))
            db.session.commit()

    c = app.test_client()

    print("== Publik ==")
    ok(c.get("/").status_code == 200, "GET / (toko)")
    ok(c.get("/keranjang").status_code == 200, "GET /keranjang")
    for path in ["/tentang", "/faq", "/cara-order", "/kebijakan", "/sitemap.xml",
                 "/robots.txt", "/wishlist", "/produk/kaos-uji"]:
        ok(c.get(path).status_code == 200, f"GET {path}")
    r = c.post("/produk/kaos-uji/ulasan", data={"name": "Uji", "rating": "5", "comment": "Barang bagus"})
    ok(r.status_code in (302, 303), "Kirim ulasan produk")

    print("== Setup pengelola pertama ==")
    # Saat belum ada user, /login mengarah ke /setup
    r = c.post("/setup", data={"name": "Admin Uji", "email": "admin@uji.id",
                               "password": "rahasia123"}, follow_redirects=False)
    ok(r.status_code in (302, 303), "POST /setup membuat pengelola & login")

    print("== Pengelola akses penuh ==")
    for path in ["/dashboard", "/keuangan/", "/inventori/", "/konten/", "/investor/",
                 "/laporan/", "/laporan/ekspor/transaksi.csv", "/laporan/ekspor/pesanan.csv",
                 "/kelola/produk", "/kelola/pesanan", "/kelola/ulasan", "/pengaturan", "/pengguna"]:
        ok(c.get(path).status_code == 200, f"GET {path}")

    # Varian produk
    r = c.post("/kelola/produk/1/varian/tambah", data={"label": "M", "sku": "M1", "stock": "5"})
    ok(r.status_code in (302, 303), "Tambah varian produk")
    ok(c.get("/produk/kaos-uji").status_code == 200, "Produk dengan varian tampil")

    # Buat akun investor
    r = c.post("/pengguna/tambah", data={"name": "Investor Uji", "email": "inv@uji.id",
                                         "role": ROLE_INVESTOR, "password": "rahasia123"})
    ok(r.status_code in (302, 303), "Buat akun investor")

    print("== Investor read-only ==")
    ci = app.test_client()
    ci.post("/login", data={"email": "inv@uji.id", "password": "rahasia123"})
    ok(ci.get("/dashboard").status_code == 200, "Investor lihat /dashboard")
    ok(ci.get("/keuangan/").status_code == 200, "Investor lihat /keuangan/")
    ok(ci.get("/investor/").status_code == 200, "Investor lihat /investor/")
    ok(ci.get("/laporan/").status_code == 200, "Investor lihat /laporan/")
    ok(ci.get("/laporan/ekspor/transaksi.csv").status_code == 403, "Investor DILARANG ekspor CSV (403)")
    ok(ci.get("/pengguna").status_code == 403, "Investor DILARANG /pengguna (403)")
    ok(ci.get("/pengaturan").status_code == 403, "Investor DILARANG /pengaturan (403)")
    ok(ci.get("/kelola/produk").status_code == 403, "Investor DILARANG /kelola/produk (403)")

    print("== PWA & endpoint ==")
    ok(c.get("/sw.js").status_code == 200, "GET /sw.js")
    ok(c.get("/manifest.webmanifest").status_code == 200, "GET /manifest.webmanifest")

    if ok.failed:
        print("\n❌ Ada pengujian yang GAGAL.")
        sys.exit(1)
    print("\n✅ Semua pengujian LULUS.")


if __name__ == "__main__":
    main()
