"""Model database ThriftFlow.

Semua nilai uang disimpan sebagai bilangan bulat Rupiah (tanpa desimal).
"""
from __future__ import annotations

from datetime import datetime, date

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

# --------------------------------------------------------------------------
#  Konstanta peran & kategori
# --------------------------------------------------------------------------
# Peran: Pengelola = akses penuh (admin), Investor = lihat laporan (read-only).
# ROLE_OWNER dipertahankan sebagai konstanta legacy (tidak dipakai untuk akun baru).
ROLE_OWNER = "OWNER"
ROLE_MANAGER = "MANAGER"      # Pengelola (akses penuh)
ROLE_INVESTOR = "INVESTOR"
ROLES = [ROLE_MANAGER, ROLE_INVESTOR]

ROLE_LABELS = {
    ROLE_OWNER: "Pengelola",   # legacy -> diperlakukan sebagai pengelola
    ROLE_MANAGER: "Pengelola",
    ROLE_INVESTOR: "Investor",
}

INCOME = "INCOME"
EXPENSE = "EXPENSE"

# Kategori bawaan (dipakai untuk dropdown; kategori bebas tetap boleh)
INCOME_CATEGORIES = ["Penjualan", "Setoran Modal", "Pendapatan Lain"]
EXPENSE_CATEGORIES = [
    "Kulakan / Beli Stok",
    "Operasional",
    "Gaji / Fee",
    "Marketing / Iklan",
    "Sewa Tempat",
    "Ongkir / Logistik",
    "Bagi Hasil Investor",
    "Pengeluaran Lain",
]

CONTENT_LIVE = "LIVE"
CONTENT_VIDEO = "VIDEO"
CONTENT_FLYER = "FLYER"
CONTENT_POST = "POST"
CONTENT_OTHER = "OTHER"
CONTENT_KINDS = [CONTENT_LIVE, CONTENT_VIDEO, CONTENT_FLYER, CONTENT_POST, CONTENT_OTHER]
CONTENT_KIND_LABELS = {
    CONTENT_LIVE: "Live Jualan",
    CONTENT_VIDEO: "Video / Reels",
    CONTENT_FLYER: "Flyer / Poster",
    CONTENT_POST: "Postingan Feed",
    CONTENT_OTHER: "Lainnya",
}

CONTENT_PLANNED = "PLANNED"
CONTENT_DONE = "DONE"
CONTENT_CANCELED = "CANCELED"


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_INVESTOR)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    investments = db.relationship(
        "Investment", backref="investor", cascade="all, delete-orphan",
        order_by="Investment.date.desc()",
    )
    notifications = db.relationship(
        "Notification", backref="user", cascade="all, delete-orphan",
        order_by="Notification.created_at.desc()",
    )
    push_subscriptions = db.relationship(
        "PushSubscription", backref="user", cascade="all, delete-orphan",
    )

    # -- password helpers --
    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    # -- role helpers --
    @property
    def is_owner(self) -> bool:
        return self.role == ROLE_OWNER

    @property
    def is_manager(self) -> bool:
        return self.role == ROLE_MANAGER

    @property
    def is_investor(self) -> bool:
        return self.role == ROLE_INVESTOR

    @property
    def can_manage(self) -> bool:
        """Owner & pengelola boleh menambah/ubah data operasional."""
        return self.role in (ROLE_OWNER, ROLE_MANAGER)

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def initials(self) -> str:
        parts = [p for p in self.name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    # Flask-Login memakai properti is_active; kita override ke kolom "active"
    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.active

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} ({self.role})>"


class Setting(db.Model):
    """Pengaturan tingkat aplikasi (satu baris, id=1)."""

    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    business_name = db.Column(db.String(120), default="The Girl House")
    tagline = db.Column(db.String(200), default="Manajemen Bisnis Thrifting")
    currency_symbol = db.Column(db.String(8), default="Rp")
    # Porsi laba yang ditahan bisnis/owner sebelum sisanya dibagi ke investor (%)
    owner_share_percent = db.Column(db.Integer, default=30)

    # --- Storefront / marketplace ---
    store_active = db.Column(db.Boolean, default=True)
    whatsapp_number = db.Column(db.String(30), default="")  # format 62812xxxx
    shop_description = db.Column(db.Text, default="Thrift & distro pilihan — kualitas oke, harga bersahabat.")
    hero_headline = db.Column(db.String(160), default="Gaya Keren, Harga Bersahabat")
    hero_subtext = db.Column(db.String(240), default="Koleksi thrift & distro pilihan yang di-kurasi khusus buat kamu.")
    hero_image = db.Column(db.String(400), default="")
    instagram = db.Column(db.String(120), default="")
    tiktok = db.Column(db.String(120), default="")
    shipping_fee = db.Column(db.Integer, default=0)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get() -> "Setting":
        s = db.session.get(Setting, 1)
        if s is None:
            s = Setting(id=1)
            db.session.add(s)
            db.session.commit()
        return s


class Period(db.Model):
    """Periode keuangan/operasional (mis. bulanan atau per-batch)."""

    __tablename__ = "periods"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(12), default="OPEN")  # OPEN / CLOSED
    note = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship(
        "Transaction", backref="period", cascade="all, delete-orphan",
        order_by="Transaction.date.desc(), Transaction.id.desc()",
    )

    @property
    def is_open(self) -> bool:
        return self.status == "OPEN"

    @property
    def total_income(self) -> int:
        return sum(t.amount for t in self.transactions if t.kind == INCOME)

    @property
    def total_expense(self) -> int:
        return sum(t.amount for t in self.transactions if t.kind == EXPENSE)

    @property
    def net_profit(self) -> int:
        return self.total_income - self.total_expense

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Period {self.name}>"


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey("periods.id"), nullable=False, index=True)
    kind = db.Column(db.String(10), nullable=False)  # INCOME / EXPENSE
    category = db.Column(db.String(80), nullable=False, default="Lainnya")
    amount = db.Column(db.Integer, nullable=False, default=0)
    description = db.Column(db.String(255), default="")
    date = db.Column(db.Date, nullable=False, default=date.today)
    batch_id = db.Column(db.Integer, db.ForeignKey("inventory_batches.id"), nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    created_by = db.relationship("User", foreign_keys=[created_by_id])

    @property
    def is_income(self) -> bool:
        return self.kind == INCOME


class InventoryBatch(db.Model):
    """Satu bal/karung/lot stok thrift."""

    __tablename__ = "inventory_batches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    supplier = db.Column(db.String(140), default="")
    category = db.Column(db.String(80), default="Campur")
    quantity = db.Column(db.Integer, default=0)        # jumlah potong awal
    sold_quantity = db.Column(db.Integer, default=0)   # sudah terjual
    cost_total = db.Column(db.Integer, default=0)      # total modal beli
    revenue_total = db.Column(db.Integer, default=0)   # total penjualan tercatat
    selling_price = db.Column(db.Integer, default=0)   # harga jual per potong (acuan)
    purchase_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(12), default="ACTIVE")  # ACTIVE / ARCHIVED
    note = db.Column(db.Text, default="")
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sales = db.relationship("Transaction", backref="batch")

    @property
    def remaining(self) -> int:
        return max(self.quantity - self.sold_quantity, 0)

    @property
    def cost_per_item(self) -> int:
        if not self.quantity:
            return 0
        return round(self.cost_total / self.quantity)

    @property
    def profit(self) -> int:
        """Laba kotor = pendapatan tercatat - modal potong yang terjual."""
        return self.revenue_total - (self.cost_per_item * self.sold_quantity)

    @property
    def sell_through(self) -> float:
        if not self.quantity:
            return 0.0
        return round(self.sold_quantity / self.quantity * 100, 1)

    @property
    def is_sold_out(self) -> bool:
        return self.remaining <= 0 and self.quantity > 0


class ContentSchedule(db.Model):
    """Jadwal konten: live, video, flyer, dsb."""

    __tablename__ = "content_schedules"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(12), default=CONTENT_POST)
    platform = db.Column(db.String(60), default="")
    scheduled_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    status = db.Column(db.String(12), default=CONTENT_PLANNED)
    note = db.Column(db.Text, default="")
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reminder_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assignee = db.relationship("User", foreign_keys=[assignee_id])

    @property
    def kind_label(self) -> str:
        return CONTENT_KIND_LABELS.get(self.kind, self.kind)


class Investment(db.Model):
    __tablename__ = "investments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False, default=0)
    date = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(400), default="")
    category = db.Column(db.String(40), default="info")  # info/success/warning/reminder
    link = db.Column(db.String(255), default="")
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PushSubscription(db.Model):
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    endpoint = db.Column(db.String(500), unique=True, nullable=False)
    subscription_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==========================================================================
#  Marketplace / Storefront
# ==========================================================================
PRODUCT_CATEGORIES = [
    "Kaos", "Kemeja", "Jaket / Hoodie", "Celana", "Dress", "Sweater",
    "Jersey", "Flannel", "Crewneck", "Sepatu", "Tas", "Aksesoris", "Lainnya",
]

# Status pesanan
ORDER_PENDING = "PENDING"       # baru masuk, belum dikonfirmasi
ORDER_CONFIRMED = "CONFIRMED"   # dikonfirmasi admin, menunggu bayar
ORDER_PAID = "PAID"             # sudah dibayar (dihitung sebagai penjualan)
ORDER_SHIPPED = "SHIPPED"       # dikirim
ORDER_DONE = "DONE"             # selesai
ORDER_CANCELED = "CANCELED"     # dibatalkan
ORDER_STATUSES = [ORDER_PENDING, ORDER_CONFIRMED, ORDER_PAID, ORDER_SHIPPED, ORDER_DONE, ORDER_CANCELED]
ORDER_STATUS_LABELS = {
    ORDER_PENDING: "Menunggu Konfirmasi",
    ORDER_CONFIRMED: "Dikonfirmasi",
    ORDER_PAID: "Sudah Dibayar",
    ORDER_SHIPPED: "Dikirim",
    ORDER_DONE: "Selesai",
    ORDER_CANCELED: "Dibatalkan",
}
# Status yang dihitung sebagai penjualan (kurangi stok + catat pemasukan)
ORDER_COUNTED = {ORDER_PAID, ORDER_SHIPPED, ORDER_DONE}


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, index=True)
    description = db.Column(db.Text, default="")
    price = db.Column(db.Integer, default=0)
    compare_price = db.Column(db.Integer, default=0)   # harga coret (opsional)
    category = db.Column(db.String(80), default="Lainnya")
    size = db.Column(db.String(60), default="")         # mis. "M" atau "S,M,L"
    condition = db.Column(db.String(40), default="")    # mis. "Baru", "Second - Mulus"
    stock = db.Column(db.Integer, default=0)
    image = db.Column(db.String(500), default="")       # URL penuh atau /static/uploads/..
    image2 = db.Column(db.String(500), default="")
    active = db.Column(db.Boolean, default=True, index=True)
    featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def in_stock(self) -> bool:
        return self.stock > 0

    @property
    def discount_percent(self) -> int:
        if self.compare_price and self.compare_price > self.price and self.price > 0:
            return round((self.compare_price - self.price) / self.compare_price * 100)
        return 0

    @property
    def image_or_placeholder(self) -> str:
        return self.image or ""


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, index=True)
    customer_name = db.Column(db.String(120), nullable=False)
    customer_phone = db.Column(db.String(30), nullable=False)
    customer_address = db.Column(db.Text, default="")
    note = db.Column(db.Text, default="")
    status = db.Column(db.String(12), default=ORDER_PENDING, index=True)
    subtotal = db.Column(db.Integer, default=0)
    shipping = db.Column(db.Integer, default=0)
    total = db.Column(db.Integer, default=0)
    stock_applied = db.Column(db.Boolean, default=False)
    period_id = db.Column(db.Integer, db.ForeignKey("periods.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    paid_at = db.Column(db.DateTime, nullable=True)

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", backref="order")

    @property
    def status_label(self) -> str:
        return ORDER_STATUS_LABELS.get(self.status, self.status)

    @property
    def total_qty(self) -> int:
        return sum(i.qty for i in self.items)

    @property
    def is_counted(self) -> bool:
        return self.status in ORDER_COUNTED


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    product_name = db.Column(db.String(160), nullable=False)
    price = db.Column(db.Integer, default=0)
    qty = db.Column(db.Integer, default=1)

    product = db.relationship("Product")

    @property
    def line_total(self) -> int:
        return self.price * self.qty
