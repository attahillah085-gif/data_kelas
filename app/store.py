"""Storefront publik: katalog, keranjang, checkout, pesanan."""
from __future__ import annotations

import json

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from .extensions import db
from .models import (
    Order,
    OrderItem,
    Product,
    PRODUCT_CATEGORIES,
    Setting,
)
from .services import generate_order_code, notify_managers, whatsapp_link

bp = Blueprint("store", __name__)


@bp.route("/")
def index():
    setting = Setting.get()
    q = (request.args.get("q") or "").strip()
    category = request.args.get("kategori", "")
    sort = request.args.get("urut", "")

    query = Product.query.filter_by(active=True)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Product.name.ilike(like), Product.description.ilike(like)))
    if category:
        query = query.filter_by(category=category)

    if sort == "murah":
        query = query.order_by(Product.price.asc())
    elif sort == "mahal":
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.featured.desc(), Product.created_at.desc())

    products = query.all()
    featured = (
        Product.query.filter_by(active=True, featured=True)
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
        if not (q or category) else []
    )
    # Kategori yang benar-benar terpakai
    used_cats = [c for c in PRODUCT_CATEGORIES
                 if Product.query.filter_by(active=True, category=c).count() > 0]

    return render_template(
        "store/index.html", setting=setting, products=products, featured=featured,
        categories=used_cats, q=q, category=category, sort=sort,
    )


@bp.route("/produk/<slug>")
def product(slug):
    p = Product.query.filter_by(slug=slug).first()
    if p is None or not p.active:
        abort(404)
    related = (
        Product.query.filter(Product.active.is_(True), Product.category == p.category,
                             Product.id != p.id)
        .order_by(Product.created_at.desc()).limit(4).all()
    )
    return render_template("store/product.html", p=p, related=related)


@bp.route("/keranjang")
def cart():
    return render_template("store/cart.html", setting=Setting.get())


@bp.route("/checkout", methods=["GET", "POST"])
def checkout():
    setting = Setting.get()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        address = (request.form.get("address") or "").strip()
        note = (request.form.get("note") or "").strip()
        raw = request.form.get("items") or "[]"
        try:
            wanted = json.loads(raw)
        except (ValueError, TypeError):
            wanted = []

        if not (name and phone):
            flash("Nama dan nomor WhatsApp wajib diisi.", "danger")
            return render_template("store/checkout.html", setting=setting)

        # Bangun item pesanan dari DB (harga & nama diambil dari server)
        order = Order(
            code=generate_order_code(), customer_name=name, customer_phone=phone,
            customer_address=address, note=note,
        )
        subtotal = 0
        for row in wanted:
            try:
                pid = int(row.get("id"))
                qty = max(int(row.get("qty", 1)), 1)
            except (ValueError, TypeError, AttributeError):
                continue
            prod = db.session.get(Product, pid)
            if prod is None or not prod.active:
                continue
            item = OrderItem(product_id=prod.id, product_name=prod.name,
                             price=prod.price, qty=qty)
            order.items.append(item)
            subtotal += prod.price * qty

        if not order.items:
            flash("Keranjang kosong atau produk tidak tersedia.", "warning")
            return redirect(url_for("store.cart"))

        order.subtotal = subtotal
        order.shipping = setting.shipping_fee or 0
        order.total = subtotal + order.shipping
        db.session.add(order)
        db.session.flush()

        notify_managers(
            f"Pesanan baru {order.code}",
            f"{name} • {order.total_qty} item • Rp {order.total:,}".replace(",", "."),
            category="success", link=url_for("catalog.order_detail", oid=order.id),
        )
        db.session.commit()
        return redirect(url_for("store.order", code=order.code))

    return render_template("store/checkout.html", setting=setting)


@bp.route("/pesanan/<code>")
def order(code):
    o = Order.query.filter_by(code=code).first()
    if o is None:
        abort(404)
    setting = Setting.get()

    # Pesan WhatsApp
    lines = [f"Halo {setting.business_name}, saya mau konfirmasi pesanan *{o.code}*:", ""]
    for it in o.items:
        lines.append(f"• {it.product_name} x{it.qty} = Rp {it.line_total:,}".replace(",", "."))
    lines.append("")
    lines.append(f"Subtotal: Rp {o.subtotal:,}".replace(",", "."))
    if o.shipping:
        lines.append(f"Ongkir: Rp {o.shipping:,}".replace(",", "."))
    lines.append(f"*Total: Rp {o.total:,}*".replace(",", "."))
    lines.append("")
    lines.append(f"Nama: {o.customer_name}")
    lines.append(f"Alamat: {o.customer_address or '-'}")
    wa = whatsapp_link(setting.whatsapp_number, "\n".join(lines)) if setting.whatsapp_number else ""

    return render_template("store/order.html", o=o, setting=setting, wa=wa)
