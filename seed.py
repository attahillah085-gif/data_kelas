"""Isi database dengan akun owner + data demo.

Penggunaan:
    python seed.py            # buat owner (bila belum ada) + data demo
    python seed.py --vapid    # cetak sepasang kunci VAPID untuk Web Push
    python seed.py --reset     # hapus semua lalu buat ulang data demo
"""
import base64
import sys
from datetime import date, datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import (
    ContentSchedule,
    InventoryBatch,
    Investment,
    Order,
    OrderItem,
    Period,
    Product,
    Setting,
    Transaction,
    User,
    INCOME,
    EXPENSE,
    ROLE_INVESTOR,
    ROLE_MANAGER,
    ROLE_OWNER,
)
from app.utils import slugify


def generate_vapid():
    """Buat sepasang kunci VAPID (public untuk browser, private untuk server)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    def b64u(b):
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    priv = ec.generate_private_key(ec.SECP256R1())
    priv_bytes = priv.private_numbers().private_value.to_bytes(32, "big")
    pub_bytes = priv.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return b64u(pub_bytes), b64u(priv_bytes)


def seed_demo(app):
    with app.app_context():
        Setting.get()

        # Sudah ada data? jangan gandakan
        if Period.query.count() > 0:
            db.session.commit()
            print("  (data demo sudah ada, dilewati)")
            return

        # Tim — pengelola: Atahillah & Cendy, investor: Mifta
        manager = User(name="Atahillah", email="atahillah@thegirlhouse.id", role=ROLE_MANAGER, active=True)
        manager.set_password("atahillah123")
        cendy = User(name="Cendy", email="cendy@thegirlhouse.id", role=ROLE_MANAGER, active=True)
        cendy.set_password("cendy123")
        mifta = User(name="Mifta", email="mifta@thegirlhouse.id", role=ROLE_INVESTOR, active=True)
        mifta.set_password("mifta123")
        db.session.add_all([manager, cendy, mifta])
        db.session.flush()

        # Modal investor
        db.session.add_all([
            Investment(user_id=mifta.id, amount=8_000_000, date=date.today() - timedelta(days=40), note="Modal awal"),
        ])

        # Periode berjalan
        p = Period(name=datetime.now().strftime("%B %Y"),
                   start_date=date.today().replace(day=1), status="OPEN",
                   note="Periode demo")
        db.session.add(p)
        db.session.flush()

        # Stok
        b1 = InventoryBatch(name="Bal Kaos Bandung #1", supplier="Gudang Bandung", category="Kaos",
                            quantity=120, sold_quantity=64, cost_total=1_800_000, revenue_total=2_240_000,
                            selling_price=35_000, purchase_date=date.today() - timedelta(days=20),
                            created_by_id=manager.id)
        b2 = InventoryBatch(name="Bal Jaket Second #2", supplier="Supplier Jakarta", category="Jaket / Hoodie",
                            quantity=60, sold_quantity=18, cost_total=2_400_000, revenue_total=1_260_000,
                            selling_price=70_000, purchase_date=date.today() - timedelta(days=10),
                            created_by_id=manager.id)
        db.session.add_all([b1, b2])
        db.session.flush()

        # Transaksi
        txs = [
            Transaction(period_id=p.id, kind=INCOME, category="Setoran Modal", amount=3_000_000,
                        description="Modal tambahan Mifta", date=date.today() - timedelta(days=8)),
            Transaction(period_id=p.id, kind=EXPENSE, category="Kulakan / Beli Stok", amount=1_800_000,
                        description="Beli stok: Bal Kaos Bandung #1", date=date.today() - timedelta(days=20),
                        batch_id=b1.id),
            Transaction(period_id=p.id, kind=EXPENSE, category="Kulakan / Beli Stok", amount=2_400_000,
                        description="Beli stok: Bal Jaket Second #2", date=date.today() - timedelta(days=10),
                        batch_id=b2.id),
            Transaction(period_id=p.id, kind=INCOME, category="Penjualan", amount=2_240_000,
                        description="Penjualan kaos (live TikTok)", date=date.today() - timedelta(days=5),
                        batch_id=b1.id),
            Transaction(period_id=p.id, kind=INCOME, category="Penjualan", amount=1_260_000,
                        description="Penjualan jaket", date=date.today() - timedelta(days=3),
                        batch_id=b2.id),
            Transaction(period_id=p.id, kind=EXPENSE, category="Marketing / Iklan", amount=300_000,
                        description="Boost postingan Instagram", date=date.today() - timedelta(days=6)),
            Transaction(period_id=p.id, kind=EXPENSE, category="Operasional", amount=150_000,
                        description="Plastik & label", date=date.today() - timedelta(days=4)),
            Transaction(period_id=p.id, kind=EXPENSE, category="Ongkir / Logistik", amount=120_000,
                        description="Ongkir supplier", date=date.today() - timedelta(days=9)),
        ]
        db.session.add_all(txs)

        # Konten (beberapa akan datang)
        now = datetime.utcnow()
        contents = [
            ContentSchedule(title="Live Thrift Jumat Malam", kind="LIVE", platform="TikTok",
                            scheduled_at=now + timedelta(days=1, hours=3), assignee_id=manager.id,
                            created_by_id=manager.id, note="Fokus kaos & jaket"),
            ContentSchedule(title="Reels OOTD Thrift", kind="VIDEO", platform="Instagram",
                            scheduled_at=now + timedelta(days=2, hours=1), assignee_id=manager.id,
                            created_by_id=manager.id),
            ContentSchedule(title="Flyer Promo Weekend", kind="FLYER", platform="WhatsApp",
                            scheduled_at=now + timedelta(days=3), created_by_id=manager.id),
            ContentSchedule(title="Restock Post", kind="POST", platform="Instagram",
                            scheduled_at=now - timedelta(days=2), status="DONE", created_by_id=manager.id),
        ]
        db.session.add_all(contents)

        # --- Pengaturan toko online ---
        s = Setting.get()
        s.whatsapp_number = s.whatsapp_number or "6281234567890"
        s.shop_description = "Thrift & distro pilihan — kualitas oke, harga bersahabat. Update stok tiap minggu!"
        s.instagram = s.instagram or "thegirlhouse"

        # --- Produk demo ---
        demo = [
            ("Kaos Vintage Band Hitam", "Kaos", "M", 55000, 85000, 12, "kaos.png",
             "Kaos vintage motif band, bahan katun adem, jahitan rapi. Cocok buat harian."),
            ("Hoodie Oversized Abu", "Jaket / Hoodie", "L", 120000, 160000, 6, "hoodie.png",
             "Hoodie oversized bahan fleece tebal, hangat & nyaman. Unisex."),
            ("Jaket Denim Klasik", "Jaket / Hoodie", "M", 145000, 0, 4, "jaket.png",
             "Jaket denim second import, kondisi mulus, warna biru klasik."),
            ("Kemeja Flanel Kotak", "Flannel", "L", 75000, 95000, 9, "flannel.png",
             "Kemeja flanel motif kotak, bahan halus, cocok buat gaya kasual."),
            ("Celana Cargo Army", "Celana", "32", 98000, 0, 7, "celana.png",
             "Celana cargo warna army, banyak kantong, bahan kuat."),
            ("Sweater Rajut Cream", "Sweater", "All size", 89000, 110000, 5, "sweater.png",
             "Sweater rajut warna cream, lembut & anti gerah. Aesthetic banget."),
            ("Dress Floral Retro", "Dress", "M", 115000, 0, 3, "dress.png",
             "Dress motif floral retro, bahan adem, cocok buat hangout."),
            ("Kemeja Polos Putih", "Kemeja", "M", 65000, 0, 0, "kemeja.png",
             "Kemeja polos putih basic, wajib punya. (Contoh stok habis)"),
        ]
        for i, (name, cat, size, price, cmp, stock, img, desc) in enumerate(demo):
            db.session.add(Product(
                name=name, slug=slugify(name), category=cat, size=size, price=price,
                compare_price=cmp, stock=stock, image=f"/static/demo/{img}",
                description=desc, active=True, featured=(i < 3),
                condition="Second - Mulus" if "second" in desc.lower() else "Baru",
            ))

        db.session.commit()
        print("  ✓ Data demo dibuat (tim, periode, stok, transaksi, konten, produk toko).")
        print("     Pengelola : atahillah@thegirlhouse.id / atahillah123")
        print("     Pengelola : cendy@thegirlhouse.id / cendy123")
        print("     Investor  : mifta@thegirlhouse.id / mifta123")


def reset(app):
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("  ✓ Database direset.")


def main():
    if "--vapid" in sys.argv:
        pub, priv = generate_vapid()
        print("\nTempel ke file .env:\n")
        print(f"VAPID_PUBLIC_KEY={pub}")
        print(f"VAPID_PRIVATE_KEY={priv}")
        print("VAPID_SUBJECT=mailto:owner@thriftflow.id\n")
        return

    app = create_app()
    print("Menyiapkan data ThriftFlow…")
    if "--reset" in sys.argv:
        reset(app)
    seed_demo(app)
    print("Selesai. Jalankan:  python run.py")


if __name__ == "__main__":
    main()
