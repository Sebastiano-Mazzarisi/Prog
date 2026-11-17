// Service worker di "Cose da fare!" (DaFare)
// Serve per installare l'app sul telefono e per aprirla anche senza rete.
// Strategia "prima la rete": si vede sempre l'ultima versione pubblicata;
// la copia salvata viene usata solo quando la rete non c'e'.
// I dati (Worker Cloudflare) non passano mai dalla cache.

const CACHE = "dafare-v2";
const FILES = [
  "./todo-priorita.html",
  "./manifest.webmanifest",
  "./icon-192.png",
  "./icon-512.png",
  "./apple-touch-icon.png",
  "./favicon.ico"
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE)
      .then(function (cache) { return cache.addAll(FILES); })
      .catch(function () {})
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.filter(function (key) { return key !== CACHE; }).map(function (key) { return caches.delete(key); }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (event) {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    fetch(request, { cache: "no-store" })
      .then(function (response) {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then(function (cache) {
            cache.put(url.pathname.endsWith("/") ? "./todo-priorita.html" : request, copy);
          });
        }
        return response;
      })
      .catch(function () {
        return caches.match(request, { ignoreSearch: true }).then(function (cached) {
          return cached || caches.match("./todo-priorita.html");
        });
      })
  );
});
