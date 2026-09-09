"""Panel admin: kelola produk & pesanan (owner/pengelola)."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from .extensions import db
from .models import (
    Order,
    Product,
    PRODUCT_CATEGORIES,
    Review,
    ORDER_STATUSES,
    ORDER_STATUS_LABELS,
    ORDER_PENDING,
)
from .services import apply_order_effects
from .utils import manage_required, save_upload, unique_slug

bp = Blueprint("catalog", __name__, url_prefix="/kelola")


def _to_int(v, default=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _image_from_form(prefix="image"):
    """Ambil gambar dari file upload atau URL."""
    f = request.files.get(f"{prefix}_file")
    saved = save_upload(f) if f else None
    if saved:
        return saved
    return (request.form.get(f"{prefix}_url") or "").strip()


# ------------------------------------------------------------------ Produk
@bp.route("/produk")
@login_required
@manage_required
def products():
    status = request.args.get("status", "")
    q = Product.query
    if status == "active":
        q = q.filter_by(active=True)
    elif status == "inactive":
        q = q.filter_by(active=False)
    items = q.order_by(Product.created_at.desc()).all()
    return render_template(
        "catalog/products.html", items=items, categories=PRODUCT_CATEGORIES, status=status,
    )


@bp.route("/produk/tambah", methods=["POST"])
@login_required
@manage_required
def product_add():
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Nama produk wajib diisi.", "danger")
        return redirect(url_for("catalog.products"))
    p = Product(
        name=name,
        slug=unique_slug(Product, name),
        description=(request.form.get("description") or "").strip(),
        price=_to_int(request.form.get("price")),
        compare_price=_to_int(request.form.get("compare_price")),
        category=(request.form.get("category") or "Lainnya").strip(),
        size=(request.form.get("size") or "").strip(),
        condition=(request.form.get("condition") or "").strip(),
        stock=_to_int(request.form.get("stock")),
        image=_image_from_form("image"),
        image2=_image_from_form("image2"),
        active=bool(request.form.get("active")),
        featured=bool(request.form.get("featured")),
    )
    db.session.add(p)
    db.session.commit()
    flash(f"Produk '{name}' ditambahkan.", "success")
    return redirect(url_for("catalog.products"))


@bp.route("/produk/<int:pid>/ubah", methods=["POST"])
@login_required
@manage_required
def product_edit(pid):
    p = db.session.get(Product, pid)
    if p is None:
        flash("Produk tidak ditemukan.", "danger")
        return redirect(url_for("catalog.products"))
    p.name = (request.form.get("name") or p.name).strip()
    p.description = (request.form.get("description") or "").strip()
    p.price = _to_int(request.form.get("price"), p.price)
    p.compare_price = _to_int(request.form.get("compare_price"))
    p.category = (request.form.get("category") or p.category).strip()
    p.size = (request.form.get("size") or "").strip()
    p.condition = (request.form.get("condition") or "").strip()
    p.stock = _to_int(request.form.get("stock"), p.stock)
    p.active = bool(request.form.get("active"))
    p.featured = bool(request.form.get("featured"))
    new_img = _image_from_form("image")
    if new_img:
        p.image = new_img
    new_img2 = _image_from_form("image2")
    if new_img2:
        p.image2 = new_img2
    db.session.commit()
    flash("Produk diperbarui.", "success")
    return redirect(url_for("catalog.products"))


@bp.route("/produk/<int:pid>/hapus", methods=["POST"])
@login_required
@manage_required
def product_delete(pid):
    p = db.session.get(Product, pid)
    if p is None:
        flash("Produk tidak ditemukan.", "danger")
        return redirect(url_for("catalog.products"))
    name = p.name
    db.session.delete(p)
    db.session.commit()
    flash(f"Produk '{name}' dihapus.", "info")
    return redirect(url_for("catalog.products"))


# ----------------------------------------------------------------- Pesanan
@bp.route("/pesanan")
@login_required
@manage_required
def orders():
    status = request.args.get("status", "")
    q = Order.query
    if status in ORDER_STATUSES:
        q = q.filter_by(status=status)
    items = q.order_by(Order.created_at.desc()).all()
    counts = {
        "pending": Order.query.filter_by(status=ORDER_PENDING).count(),
        "all": Order.query.count(),
    }
    return render_template(
        "catalog/orders.html", items=items, status=status, counts=counts,
        statuses=ORDER_STATUSES, status_labels=ORDER_STATUS_LABELS,
    )


@bp.route("/pesanan/<int:oid>")
@login_required
@manage_required
def order_detail(oid):
    o = db.session.get(Order, oid)
    if o is None:
        flash("Pesanan tidak ditemukan.", "danger")
        return redirect(url_for("catalog.orders"))
    return render_template(
        "catalog/order_detail.html", o=o,
        statuses=ORDER_STATUSES, status_labels=ORDER_STATUS_LABELS,
    )


@bp.route("/pesanan/<int:oid>/status", methods=["POST"])
@login_required
@manage_required
def order_status(oid):
    o = db.session.get(Order, oid)
    if o is None:
        flash("Pesanan tidak ditemukan.", "danger")
        return redirect(url_for("catalog.orders"))
    new_status = request.form.get("status")
    if new_status in ORDER_STATUSES:
        o.status = new_status
        warning = apply_order_effects(o)
        db.session.commit()
        if warning:
            flash(warning, "warning")
        else:
            flash(f"Status pesanan {o.code} → {ORDER_STATUS_LABELS[new_status]}.", "success")
    return redirect(request.referrer or url_for("catalog.orders"))


@bp.route("/pesanan/<int:oid>/hapus", methods=["POST"])
@login_required
@manage_required
def order_delete(oid):
    o = db.session.get(Order, oid)
    if o is None:
        flash("Pesanan tidak ditemukan.", "danger")
        return redirect(url_for("catalog.orders"))
    # Kembalikan efek dulu (stok/keuangan) bila sempat diterapkan
    o.status = "CANCELED"
    apply_order_effects(o)
    code = o.code
    db.session.delete(o)
    db.session.commit()
    flash(f"Pesanan {code} dihapus.", "info")
    return redirect(url_for("catalog.orders"))


# ----------------------------------------------------------------- Ulasan
@bp.route("/ulasan")
@login_required
@manage_required
def reviews():
    pending = (Review.query.filter_by(approved=False)
               .order_by(Review.created_at.desc()).all())
    approved = (Review.query.filter_by(approved=True)
                .order_by(Review.created_at.desc()).limit(50).all())
    return render_template("catalog/reviews.html", pending=pending, approved=approved)


@bp.route("/ulasan/<int:rid>/setuju", methods=["POST"])
@login_required
@manage_required
def review_approve(rid):
    r = db.session.get(Review, rid)
    if r:
        r.approved = not r.approved
        db.session.commit()
        flash("Ulasan " + ("ditampilkan" if r.approved else "disembunyikan") + ".", "success")
    return redirect(url_for("catalog.reviews"))


@bp.route("/ulasan/<int:rid>/hapus", methods=["POST"])
@login_required
@manage_required
def review_delete(rid):
    r = db.session.get(Review, rid)
    if r:
        db.session.delete(r)
        db.session.commit()
        flash("Ulasan dihapus.", "info")
    return redirect(url_for("catalog.reviews"))
