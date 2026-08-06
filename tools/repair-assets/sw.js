const CACHE = 'du-llb-cases-v2';
const BASE = new URL('./', self.location.href).pathname;
const CORE = [
  BASE,
  `${BASE}index.html`, `${BASE}styles.css`, `${BASE}app.js`,
  `${BASE}node.css`, `${BASE}node.js`,
  `${BASE}case.css`, `${BASE}case.js`,
  `${BASE}cases/index.html`, `${BASE}cases/trails/index.html`,
  `${BASE}data/curriculum.json`, `${BASE}data/content-index.json`, `${BASE}data/cases-index.json`,
  `${BASE}manifest.webmanifest`, `${BASE}assets/icon.svg`, `${BASE}offline.html`
];
self.addEventListener('install', event => event.waitUntil((async () => {
  const cache = await caches.open(CACHE);
  await cache.addAll(CORE);
  await self.skipWaiting();
})()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  const keys = await caches.keys();
  await Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)));
  await self.clients.claim();
})()));
async function networkFirst(request, offlineFallback = false) {
  const cache = await caches.open(CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (_) {
    const cached = await cache.match(request);
    if (cached) return cached;
    if (offlineFallback) return cache.match(`${BASE}offline.html`);
    return Response.error();
  }
}
async function cacheFirst(request) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith(BASE)) return;
  if (event.request.mode === 'navigate' || event.request.destination === 'document') {
    event.respondWith(networkFirst(event.request, true));
    return;
  }
  if (['style', 'script', 'manifest'].includes(event.request.destination) || url.pathname.includes('/data/')) {
    event.respondWith(networkFirst(event.request));
    return;
  }
  event.respondWith(cacheFirst(event.request));
});
