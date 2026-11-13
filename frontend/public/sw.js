// FINN service worker: caches the app shell and the last API responses (network first), and shows web push.
const SHELL = "finn-shell-v1";
const DATA = "finn-data-v1";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/", "/portfolio", "/research", "/alerts", "/manifest.webmanifest"])).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => ![SHELL, DATA].includes(k)).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const isApi = url.pathname.startsWith("/api/");
  const isPage = req.mode === "navigate";
  const isStatic = url.origin === self.location.origin && url.pathname.startsWith("/_next/static/");
  if (isStatic) {
    e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((r) => { const copy = r.clone(); caches.open(SHELL).then((c) => c.put(req, copy)); return r; })));
    return;
  }
  if (isApi || isPage) {
    // network first; fall back to the last good response so the app works offline
    e.respondWith(fetch(req).then((r) => {
      if (r.ok) { const copy = r.clone(); caches.open(isApi ? DATA : SHELL).then((c) => c.put(req, copy)); }
      return r;
    }).catch(() => caches.match(req).then((hit) => hit || (isPage ? caches.match("/") : Response.error()))));
  }
});

self.addEventListener("push", (e) => {
  let d = { title: "FINN", body: "", url: "/" };
  try { d = { ...d, ...e.data.json() }; } catch (_) {}
  e.waitUntil(self.registration.showNotification(d.title, { body: d.body, icon: "/icon-192.png", badge: "/icon-192.png", data: { url: d.url } }));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(self.clients.matchAll({ type: "window" }).then((cs) => {
    for (const c of cs) { if ("focus" in c) { c.navigate(url); return c.focus(); } }
    return self.clients.openWindow(url);
  }));
});
