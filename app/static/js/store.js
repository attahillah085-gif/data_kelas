/* ThriftFlow Storefront — cart & UI */
(function () {
  "use strict";
  var CART_KEY = "tgh-cart";

  /* ---------- Tema ---------- */
  var root = document.documentElement;
  function curTheme() {
    var t = root.getAttribute("data-theme");
    if (t === "dark" || t === "light") return t;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function syncIcon() {
    var dark = curTheme() === "dark";
    var s = document.getElementById("iconSun"), m = document.getElementById("iconMoon");
    if (s && m) { s.hidden = !dark; m.hidden = dark; }
  }
  var tb = document.getElementById("themeBtn");
  if (tb) tb.addEventListener("click", function () {
    var n = curTheme() === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", n);
    try { localStorage.setItem("tf-theme", n); } catch (e) {}
    syncIcon();
  });
  syncIcon();

  /* ---------- Cart storage ---------- */
  function getCart() { try { return JSON.parse(localStorage.getItem(CART_KEY)) || []; } catch (e) { return []; } }
  function setCart(c) { try { localStorage.setItem(CART_KEY, JSON.stringify(c)); } catch (e) {} updateBadge(); }
  function rupiah(n) { return "Rp " + (n || 0).toLocaleString("id-ID"); }

  function updateBadge() {
    var el = document.getElementById("cartCount");
    if (!el) return;
    var n = getCart().reduce(function (s, i) { return s + i.qty; }, 0);
    if (n > 0) { el.textContent = n; el.hidden = false; } else { el.hidden = true; }
  }
  updateBadge();

  /* ---------- Toast ---------- */
  function toast(msg) {
    var t = document.createElement("div");
    t.className = "toast success";
    t.style.cssText = "position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:300";
    t.innerHTML = '<span class="ic"><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M20 6 9 17l-5-5"/></svg></span><span class="msg">' + msg + "</span>";
    document.body.appendChild(t);
    setTimeout(function () { t.style.transition = "opacity .3s"; t.style.opacity = "0"; setTimeout(function () { t.remove(); }, 320); }, 1800);
  }

  /* ---------- Qty +/- (product detail) ---------- */
  document.addEventListener("click", function (e) {
    var b = e.target.closest(".qty-btn");
    if (!b) return;
    var box = b.closest(".qty-box");
    var input = box && box.querySelector("input");
    if (!input) return;
    var v = parseInt(input.value || "1", 10);
    var max = parseInt(input.getAttribute("max") || "9999", 10);
    v += b.getAttribute("data-qty") === "+" ? 1 : -1;
    if (v < 1) v = 1; if (v > max) v = max;
    input.value = v;
    input.dispatchEvent(new Event("change"));
  });

  /* ---------- Add to cart ---------- */
  document.addEventListener("click", function (e) {
    var b = e.target.closest(".add-cart");
    if (!b || b.disabled) return;
    var qty = 1;
    var src = b.getAttribute("data-qty-source");
    if (src) { var qi = document.getElementById(src); if (qi) qty = Math.max(parseInt(qi.value || "1", 10), 1); }
    addItem({
      id: parseInt(b.getAttribute("data-id"), 10),
      name: b.getAttribute("data-name"),
      price: parseInt(b.getAttribute("data-price"), 10),
      image: b.getAttribute("data-image") || "",
      slug: b.getAttribute("data-slug") || "",
      qty: qty,
    });
    toast("Ditambahkan ke keranjang");
  });
  function addItem(item) {
    var c = getCart();
    var f = c.find(function (x) { return x.id === item.id; });
    if (f) f.qty += item.qty; else c.push(item);
    setCart(c);
  }

  /* ---------- Cart page ---------- */
  var cartLayout = document.getElementById("cartLayout");
  if (cartLayout) renderCart();
  function renderCart() {
    var c = getCart();
    var wrap = document.getElementById("cartItems");
    var empty = document.getElementById("cartEmpty");
    if (!c.length) { cartLayout.hidden = true; empty.hidden = false; return; }
    cartLayout.hidden = false; empty.hidden = true;
    wrap.innerHTML = "";
    var subtotal = 0;
    c.forEach(function (it, idx) {
      subtotal += it.price * it.qty;
      var row = document.createElement("div");
      row.className = "cart-item";
      var img = it.image ? '<img src="' + it.image + '" alt="">' :
        '<div class="ci-noimg"><svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M20 7h-3.5l-1-2h-7l-1 2H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2Z"/></svg></div>';
      row.innerHTML =
        img +
        '<div class="ci-main"><div class="ci-name">' + it.name + '</div>' +
        '<div class="ci-price">' + rupiah(it.price) + '</div>' +
        '<button class="ci-remove" data-idx="' + idx + '">Hapus</button></div>' +
        '<div class="qty-box"><button type="button" class="qty-btn" data-qty="-">−</button>' +
        '<input type="number" value="' + it.qty + '" min="1" data-idx="' + idx + '">' +
        '<button type="button" class="qty-btn" data-qty="+">+</button></div>' +
        '<div class="fw-800" style="min-width:90px;text-align:right">' + rupiah(it.price * it.qty) + '</div>';
      wrap.appendChild(row);
    });
    var shipping = window.STORE_SHIPPING || 0;
    document.getElementById("cartSubtotal").textContent = rupiah(subtotal);
    document.getElementById("cartTotal").textContent = rupiah(subtotal + shipping);

    wrap.querySelectorAll(".ci-remove").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var c = getCart(); c.splice(parseInt(btn.getAttribute("data-idx"), 10), 1); setCart(c); renderCart();
      });
    });
    wrap.querySelectorAll('input[type="number"]').forEach(function (inp) {
      inp.addEventListener("change", function () {
        var c = getCart(); var i = parseInt(inp.getAttribute("data-idx"), 10);
        c[i].qty = Math.max(parseInt(inp.value || "1", 10), 1); setCart(c); renderCart();
      });
    });
  }

  /* ---------- Checkout page ---------- */
  var coForm = document.getElementById("checkoutForm");
  if (coForm) {
    var c = getCart();
    if (!c.length) { window.location.href = "/keranjang"; return; }
    var box = document.getElementById("coItems");
    var subtotal = 0;
    c.forEach(function (it) {
      subtotal += it.price * it.qty;
      var d = document.createElement("div"); d.className = "co-item";
      d.innerHTML = '<span class="n">' + it.name + ' × ' + it.qty + '</span><span class="fw-700">' + rupiah(it.price * it.qty) + '</span>';
      box.appendChild(d);
    });
    var shipping = window.STORE_SHIPPING || 0;
    document.getElementById("coSubtotal").textContent = rupiah(subtotal);
    document.getElementById("coTotal").textContent = rupiah(subtotal + shipping);
    document.getElementById("itemsField").value = JSON.stringify(c.map(function (i) { return { id: i.id, qty: i.qty }; }));
  }
})();
