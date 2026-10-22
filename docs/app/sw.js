/* Service worker: the app opens without a network (app.js keeps the last search in localStorage).
 * Network first, so a new version is used as soon as it is online; the cache is only the fallback.
 * Geoapify API calls and map tiles are never cached here: they must be live.
 */
var CACHE = "def-20261023b";

self.addEventListener("install", function () { self.skipWaiting(); });

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin && url.hostname !== "unpkg.com") return; // Leaflet from unpkg is cached too
  e.respondWith(fetch(req).then(function (res) {
    if (res.ok) {
      var copy = res.clone();
      caches.open(CACHE).then(function (c) { c.put(req, copy); });
    }
    return res;
  }).catch(function () {
    return caches.match(req).then(function (hit) {
      if (hit) return hit;
      if (req.mode === "navigate") return caches.match("./").then(function (page) { return page || Response.error(); });
      return Response.error();
    });
  }));
});
