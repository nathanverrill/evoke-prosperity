/* Field Kit service worker — network-first with cache fallback for the app
   shell, so the Companion opens instantly on a phone and survives flaky
   school Wi-Fi. APIs and the live WebSocket are never cached: stale quest/
   award/presence data presented as fresh would be worse than an error. */
const CACHE = "fieldkit-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/") || url.pathname === "/ws") return;
  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      try {
        const fresh = await fetch(e.request);
        cache.put(e.request, fresh.clone());
        return fresh;
      } catch {
        const cached = await cache.match(e.request);
        return cached || Response.error();
      }
    })
  );
});
