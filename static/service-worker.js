const VERSION = 'floki-manager-v2-6-2-render-safe';
const STATIC_CACHE = `${VERSION}-static`;
const CORE = [
  '/offline',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/offline-sync.js',
  '/static/js/offline-page.js',
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
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key !== STATIC_CACHE).map((key) => caches.delete(key))
  )).then(() => self.clients.claim()));
});

const networkFirstNavigation = async (request) => {
  try { return await fetch(request, { cache: 'no-store' }); }
  catch (_) { return (await caches.match('/offline')) || Response.error(); }
};

const networkFirstAsset = async (request) => {
  try {
    const response = await fetch(request, { cache: 'no-store' });
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      await cache.put(request, response.clone());
    }
    return response;
  } catch (_) { return (await caches.match(request)) || Response.error(); }
};

const staleWhileRevalidate = async (request) => {
  const cached = await caches.match(request);
  const network = fetch(request, { cache: 'no-store' }).then(async (response) => {
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
    if (url.pathname === '/login' || url.pathname === '/logout') return; // Red pura: sin Service Worker.
    event.respondWith(networkFirstNavigation(request));
    return;
  }

  if (url.pathname.startsWith('/api/') || url.pathname === '/health') return;
  if (url.pathname === '/static/css/app.css' || url.pathname === '/static/js/app.js' || url.pathname === '/static/js/offline-sync.js') {
    event.respondWith(networkFirstAsset(request));
    return;
  }
  if (url.pathname.startsWith('/static/') || CORE.includes(url.pathname)) event.respondWith(staleWhileRevalidate(request));
});
