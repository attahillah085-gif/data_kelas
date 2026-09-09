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
ROLE_OWNER = "OWNER"
ROLE_MANAGER = "MANAGER"      # Pengelola
ROLE_INVESTOR = "INVESTOR"
ROLES = [ROLE_OWNER, ROLE_MANAGER, ROLE_INVESTOR]

ROLE_LABELS = {
    ROLE_OWNER: "Pemilik",
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
    business_name = db.Column(db.String(120), default="ThriftFlow")
    tagline = db.Column(db.String(200), default="Manajemen Bisnis Thrifting")
    currency_symbol = db.Column(db.String(8), default="Rp")
    # Porsi laba yang ditahan bisnis/owner sebelum sisanya dibagi ke investor (%)
    owner_share_percent = db.Column(db.Integer, default=30)
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
