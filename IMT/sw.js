// sw.js - generato da Genera-IMT.py: permette l'installazione come app.
// Strategia "prima la rete": la pagina è sempre aggiornata; la copia salvata
// serve solo quando manca la connessione.
const CACHE = 'imt-menu-20261128092417';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(
    caches.keys().then(k => Promise.all(k.filter(n => n !== CACHE).map(n => caches.delete(n))))
        .then(() => self.clients.claim())));
self.addEventListener('fetch', e => {
    const r = e.request;
    if (r.method !== 'GET' || new URL(r.url).origin !== self.location.origin) return;
    const chiave = r.url.split('?')[0].split('#')[0];
    e.respondWith(fetch(r).then(risposta => {
        if (risposta.ok) { const copia = risposta.clone(); caches.open(CACHE).then(c => c.put(chiave, copia)); }
        return risposta;
    }).catch(() => caches.match(chiave)));
});
