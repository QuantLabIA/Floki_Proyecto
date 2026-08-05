const VERSION = 'floki-manager-v2-5-1-event-banner';
const STATIC_CACHE = `${VERSION}-static`;
const PAGE_CACHE = `${VERSION}-pages`;
const CORE = [
  '/offline',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/img/floki-logo-white.png',
  '/static/img/floki-login-viking.png',
  '/static/img/floki-club-bg.jpg',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then((cache) => cache.addAll(CORE)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => ![STATIC_CACHE, PAGE_CACHE].includes(key)).map((key) => caches.delete(key))
    ))
  );
  self.clients.claim();
});

const networkFirstPage = async (request) => {
  try {
    // Las páginas contienen datos privados de caja: nunca se guardan en caché.
    return await fetch(request, { cache: 'no-store' });
  } catch (error) {
    return await caches.match('/offline');
  }
};

const staleWhileRevalidate = async (request) => {
  const cached = await caches.match(request);
  const network = fetch(request).then(async (response) => {
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  }).catch(() => null);
  return cached || network || Response.error();
};

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith(networkFirstPage(request));
    return;
  }
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(staleWhileRevalidate(request));
  }
});
