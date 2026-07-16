/* Field Kit service worker — DISABLED / kill-switch.

   An earlier build shipped a shell-caching SW here, which could serve a
   stale (old) copy of index.html and make the UI flip between the old and
   new versions. This replacement caches nothing; on activation it clears
   every cache, unregisters itself, and reloads open pages so they pick up
   the current build straight from the network. Browsers re-fetch sw.js on
   navigation, so any client that still has the old SW upgrades to this one
   and self-cleans automatically. */
self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.map((k) => caches.delete(k)));
    } catch (e) {}
    try { await self.clients.claim(); } catch (e) {}
    try { await self.registration.unregister(); } catch (e) {}
    try {
      const clients = await self.clients.matchAll({ type: "window" });
      clients.forEach((c) => { try { c.navigate(c.url); } catch (e) {} });
    } catch (e) {}
  })());
});

// Never intercept fetches — everything goes straight to the network.
