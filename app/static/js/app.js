/* ThriftFlow — UI behaviour */
(function () {
  "use strict";

  /* ---------- Tema terang/gelap ---------- */
  var root = document.documentElement;
  function currentTheme() {
    var t = root.getAttribute("data-theme");
    if (t === "dark" || t === "light") return t;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function syncThemeIcon() {
    var dark = currentTheme() === "dark";
    var sun = document.getElementById("iconSun");
    var moon = document.getElementById("iconMoon");
    if (sun && moon) { sun.hidden = !dark; moon.hidden = dark; }
  }
  var themeBtn = document.getElementById("themeBtn");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("tf-theme", next); } catch (e) {}
      syncThemeIcon();
    });
  }
  syncThemeIcon();

  /* ---------- Dropdown menu ---------- */
  function bindDropdown(btnId, menuId) {
    var btn = document.getElementById(btnId);
    var menu = document.getElementById(menuId);
    if (!btn || !menu) return;
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      document.querySelectorAll(".menu.open").forEach(function (m) {
        if (m !== menu) m.classList.remove("open");
      });
      menu.classList.toggle("open");
    });
    menu.addEventListener("click", function (e) { e.stopPropagation(); });
  }
  bindDropdown("notifBtn", "notifMenu");
  bindDropdown("userBtn", "userMenu");
  document.addEventListener("click", function () {
    document.querySelectorAll(".menu.open").forEach(function (m) { m.classList.remove("open"); });
  });

  /* ---------- Sidebar drawer (mobile) ---------- */
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.getElementById("backdrop");
  var menuBtn = document.getElementById("menuBtn");
  function closeDrawer() { if (sidebar) sidebar.classList.remove("open"); if (backdrop) backdrop.classList.remove("show"); }
  if (menuBtn) menuBtn.addEventListener("click", function () {
    sidebar.classList.toggle("open"); backdrop.classList.toggle("show");
  });
  if (backdrop) backdrop.addEventListener("click", closeDrawer);

  /* ---------- Toast auto-dismiss ---------- */
  document.querySelectorAll("[data-toast]").forEach(function (t) {
    setTimeout(function () {
      t.style.transition = "opacity .3s, transform .3s";
      t.style.opacity = "0"; t.style.transform = "translateX(30px)";
      setTimeout(function () { t.remove(); }, 320);
    }, 4200);
  });

  /* ---------- Dialog helpers ---------- */
  window.openDialog = function (id) {
    var d = document.getElementById(id);
    if (d && typeof d.showModal === "function") d.showModal();
    else if (d) d.setAttribute("open", "");
  };
  window.closeDialog = function (id) {
    var d = document.getElementById(id);
    if (d && typeof d.close === "function") d.close();
    else if (d) d.removeAttribute("open");
  };
  document.querySelectorAll("[data-open-dialog]").forEach(function (b) {
    b.addEventListener("click", function () { window.openDialog(b.getAttribute("data-open-dialog")); });
  });
  document.querySelectorAll("[data-close-dialog]").forEach(function (b) {
    b.addEventListener("click", function () { window.closeDialog(b.getAttribute("data-close-dialog")); });
  });

  /* ---------- Format input uang (titik ribuan) ---------- */
  document.querySelectorAll("input[data-money]").forEach(function (inp) {
    var hidden = document.getElementById(inp.getAttribute("data-money"));
    function fmt() {
      var raw = inp.value.replace(/[^\d]/g, "");
      if (hidden) hidden.value = raw;
      inp.value = raw ? Number(raw).toLocaleString("id-ID") : "";
    }
    inp.addEventListener("input", fmt);
    fmt();
  });

  /* ---------- Segmented income/expense ---------- */
  document.querySelectorAll("[data-seg]").forEach(function (seg) {
    seg.addEventListener("change", function () {
      var val = seg.querySelector("input:checked");
      var target = seg.getAttribute("data-seg-target");
      if (val && target) {
        var evt = new CustomEvent("segchange", { detail: val.value });
        document.getElementById(target)?.dispatchEvent(evt);
      }
    });
  });

  /* ---------- Notifikasi polling (badge) ---------- */
  var notifCount = document.getElementById("notifCount");
  function refreshNotif() {
    if (!notifCount) return;
    fetch("/api/notifications/unread", { headers: { "X-Requested-With": "fetch" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        if (d.count > 0) { notifCount.textContent = d.count; notifCount.hidden = false; }
        else { notifCount.hidden = true; }
      }).catch(function () {});
  }
  setInterval(refreshNotif, 60000);

  /* ---------- PWA: service worker + install + push ---------- */
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").then(function (reg) {
        setupPush(reg);
      }).catch(function () {});
    });
  }

  var deferredPrompt = null;
  var installBanner = document.getElementById("installBanner");
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault(); deferredPrompt = e;
    showInstallItem();
    try { if (localStorage.getItem("tf-install-dismiss") === "1") return; } catch (er) {}
    if (installBanner) installBanner.classList.add("show");
  });
  var installBtn = document.getElementById("installBtn");
  if (installBtn) installBtn.addEventListener("click", function () {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.finally(function () {
      deferredPrompt = null; installBanner.classList.remove("show");
    });
  });
  var installClose = document.getElementById("installClose");
  if (installClose) installClose.addEventListener("click", function () {
    installBanner.classList.remove("show");
    try { localStorage.setItem("tf-install-dismiss", "1"); } catch (e) {}
  });

  /* ---------- Pasang aplikasi: menu item + panduan iOS ---------- */
  var isStandalone = (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) || window.navigator.standalone === true;
  var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  var installItem = document.getElementById("installMenuItem");
  var iosModal = document.getElementById("iosInstallModal");
  function showInstallItem() { if (installItem && !isStandalone) installItem.hidden = false; }
  // iPhone tak pernah memicu beforeinstallprompt → tetap tampilkan tombol (buka panduan)
  if (isIOS && !isStandalone) showInstallItem();
  function closeIos() { if (iosModal) { try { iosModal.close(); } catch (e) { iosModal.removeAttribute("open"); } } }
  if (installItem) installItem.addEventListener("click", function () {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.finally(function () { deferredPrompt = null; installItem.hidden = true; });
    } else if (iosModal && iosModal.showModal) {
      iosModal.showModal();
    } else if (iosModal) {
      iosModal.setAttribute("open", "");
    }
  });
  var iosClose = document.getElementById("iosClose");
  var iosOk = document.getElementById("iosOk");
  if (iosClose) iosClose.addEventListener("click", closeIos);
  if (iosOk) iosOk.addEventListener("click", closeIos);

  /* ---------- Bottom-nav "Menu" membuka sidebar penuh ---------- */
  var bottomMenuBtn = document.getElementById("bottomMenuBtn");
  if (bottomMenuBtn) bottomMenuBtn.addEventListener("click", function () {
    if (sidebar) sidebar.classList.add("open");
    if (backdrop) backdrop.classList.add("show");
  });

  function urlB64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var raw = window.atob(base64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function setupPush(reg) {
    var key = (window.TF && window.TF.vapidPublicKey) || "";
    if (!key || !("PushManager" in window)) return;
    // Aktifkan tombol "izinkan notifikasi" bila ada
    var enableBtn = document.getElementById("enablePushBtn");
    function subscribe() {
      Notification.requestPermission().then(function (perm) {
        if (perm !== "granted") return;
        reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlB64ToUint8Array(key),
        }).then(function (sub) {
          fetch("/api/push/subscribe", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(sub),
          }).then(function(){
            if (enableBtn) { enableBtn.textContent = "Notifikasi aktif ✓"; enableBtn.disabled = true; }
          });
        }).catch(function () {});
      });
    }
    if (enableBtn) enableBtn.addEventListener("click", subscribe);
    // Auto-subscribe bila izin sudah diberikan sebelumnya
    if (Notification.permission === "granted") {
      reg.pushManager.getSubscription().then(function (sub) { if (!sub) subscribe(); });
    }
  }
})();
