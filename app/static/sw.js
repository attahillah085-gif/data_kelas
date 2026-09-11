/* The Girl House Service Worker — Offline Level 1 (fokus manajemen) */
const CACHE = "thegirlhouse-v8";
const APP_SHELL = [
  "/offline",
  "/static/css/style.css",
  "/static/css/store.css",
  "/static/js/app.js",
  "/static/js/store.js",
  "/static/icons/icon-192.png",
  "/static/icons/favicon.svg",
  "/static/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  // Jangan cache endpoint dinamis/aksi (API, login, dsb) — selalu ke jaringan.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/logout")) {
    return; // biarkan default (butuh online)
  }

  // Aset statis (CSS/JS/gambar): stale-while-revalidate — tampil instan dari
  // cache, sambil diperbarui di latar belakang. Ringan & cepat di HP.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(req).then((cached) => {
          const network = fetch(req).then((res) => {
            if (res && res.status === 200) cache.put(req, res.clone());
            return res;
          }).catch(() => cached);
          return cached || network;
        })
      )
    );
    return;
  }

  // Navigasi halaman: network-first (selalu coba data terbaru), lalu jatuh ke
  // salinan halaman yang pernah dibuka, terakhir ke halaman "offline".
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).then((res) => {
        if (res && res.status === 200) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        }
        return res;
      }).catch(() =>
        caches.match(req).then((cached) => cached || caches.match("/offline"))
      )
    );
    return;
  }
});

/* ---- Web Push ---- */
self.addEventListener("push", (event) => {
  let data = { title: "The Girl House", body: "Ada pembaruan baru.", url: "/" };
  try { if (event.data) data = Object.assign(data, event.data.json()); } catch (e) {
    if (event.data) data.body = event.data.text();
  }
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/static/icons/icon-192.png",
      badge: "/static/icons/badge-72.png",
      data: { url: data.url || "/" },
      vibrate: [80, 40, 80],
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if ("focus" in c) { c.navigate(target); return c.focus(); }
      }
      return clients.openWindow(target);
    })
  );
});
