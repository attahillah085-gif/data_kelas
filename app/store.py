"""Storefront publik: katalog, keranjang, checkout, pesanan."""
from __future__ import annotations

import json

from flask import (
    Blueprint,
    Response,
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
    ProductVariant,
    PRODUCT_CATEGORIES,
    Review,
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

    size = (request.args.get("ukuran") or "").strip()
    pmin = request.args.get("harga_min", type=int)
    pmax = request.args.get("harga_max", type=int)

    query = Product.query.filter_by(active=True)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Product.name.ilike(like), Product.description.ilike(like)))
    if category:
        query = query.filter_by(category=category)
    if size:
        query = query.filter(Product.size.ilike(f"%{size}%"))
    if pmin is not None:
        query = query.filter(Product.price >= pmin)
    if pmax is not None:
        query = query.filter(Product.price <= pmax)

    if sort == "murah":
        query = query.order_by(Product.price.asc())
    elif sort == "mahal":
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.featured.desc(), Product.created_at.desc())

    products = query.all()
    has_filter = bool(q or category or size or pmin is not None or pmax is not None)
    featured = (
        Product.query.filter_by(active=True, featured=True)
        .order_by(Product.created_at.desc())
        .limit(4)
        .all()
        if not has_filter else []
    )
    # Kategori & ukuran yang benar-benar terpakai (untuk filter)
    active_products = Product.query.filter_by(active=True).all()
    used_cats = [c for c in PRODUCT_CATEGORIES
                 if any(pr.category == c for pr in active_products)]
    sizes = sorted({s.strip() for pr in active_products for s in (pr.size or "").replace("/", ",").split(",") if s.strip()})

    return render_template(
        "store/index.html", setting=setting, products=products, featured=featured,
        categories=used_cats, sizes=sizes, q=q, category=category, sort=sort,
        size=size, pmin=pmin, pmax=pmax, has_filter=has_filter,
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


@bp.route("/produk/<slug>/ulasan", methods=["POST"])
def add_review(slug):
    p = Product.query.filter_by(slug=slug).first()
    if p is None or not p.active:
        abort(404)
    name = (request.form.get("name") or "").strip()
    comment = (request.form.get("comment") or "").strip()
    try:
        rating = int(request.form.get("rating") or 5)
    except (TypeError, ValueError):
        rating = 5
    rating = min(max(rating, 1), 5)
    if not name or not comment:
        flash("Nama & ulasan wajib diisi.", "danger")
        return redirect(url_for("store.product", slug=slug))
    db.session.add(Review(product_id=p.id, name=name, rating=rating,
                          comment=comment, approved=False))
    db.session.commit()
    flash("Terima kasih! Ulasan kamu akan tampil setelah disetujui admin.", "success")
    return redirect(url_for("store.product", slug=slug))


@bp.route("/wishlist")
def wishlist():
    return render_template("store/wishlist.html", setting=Setting.get())


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
            variant = None
            vid = row.get("variantId")
            if vid:
                try:
                    variant = db.session.get(ProductVariant, int(vid))
                except (ValueError, TypeError):
                    variant = None
                if variant and variant.product_id != prod.id:
                    variant = None
            # Produk dgn varian wajib pilih varian
            if prod.has_variants and variant is None:
                continue
            item = OrderItem(
                product_id=prod.id,
                variant_id=variant.id if variant else None,
                product_name=prod.name,
                variant_label=variant.label if variant else "",
                price=prod.price, qty=qty,
            )
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


# ---------------- Halaman info ----------------
@bp.route("/tentang")
def about():
    return render_template("store/about.html", setting=Setting.get())


@bp.route("/faq")
def faq():
    return render_template("store/faq.html", setting=Setting.get())


@bp.route("/cara-order")
def how_to_order():
    return render_template("store/how_to_order.html", setting=Setting.get())


@bp.route("/kebijakan")
def policy():
    return render_template("store/policy.html", setting=Setting.get())


# ---------------- SEO: robots & sitemap ----------------
@bp.route("/robots.txt")
def robots():
    body = "\n".join([
        "User-agent: *",
        "Allow: /",
        "Disallow: /kelola/",
        "Disallow: /dashboard",
        f"Sitemap: {request.url_root}sitemap.xml",
    ])
    return Response(body, mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap():
    root = request.url_root[:-1]
    urls = [
        (root + url_for("store.index"), "1.0"),
        (root + url_for("store.about"), "0.5"),
        (root + url_for("store.faq"), "0.5"),
        (root + url_for("store.how_to_order"), "0.5"),
        (root + url_for("store.policy"), "0.4"),
    ]
    for p in Product.query.filter_by(active=True).all():
        urls.append((root + url_for("store.product", slug=p.slug), "0.8"))

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, pr in urls:
        parts.append(f"<url><loc>{loc}</loc><priority>{pr}</priority></url>")
    parts.append("</urlset>")
    return Response("\n".join(parts), mimetype="application/xml")
