const CACHE_VERSION = 'floki-manager-v2-10-0-offline-shell';
const OFFLINE_SHELL = '/offline-operations';
const PRECACHE = [
  OFFLINE_SHELL,
  '/manifest.webmanifest',
  '/static/css/app.css',
  '/static/js/app.js',
  '/static/js/offline-sync.js',
  '/static/js/offline-page.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/img/floki-logo-white.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_VERSION);
    for (const url of PRECACHE) {
      try {
        const response = await fetch(url, { cache: 'reload', credentials: 'same-origin' });
        if (response && response.ok) await cache.put(url, response.clone());
      } catch (_) {
        // Un recurso aislado nunca debe impedir instalar el shell offline.
      }
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys
      .filter((key) => key.startsWith('floki-manager-') && key !== CACHE_VERSION)
      .map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

const offlineShellResponse = async () => {
  const cache = await caches.open(CACHE_VERSION);
  return (await cache.match(OFFLINE_SHELL, { ignoreSearch: true })) || Response.error();
};

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // APIs, login/logout y descargas siempre van directo a red. Nunca se cachean datos privados.
  if (url.pathname.startsWith('/api/') || url.pathname === '/login' || url.pathname === '/logout') return;

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        return await fetch(request);
      } catch (_) {
        return offlineShellResponse();
      }
    })());
    return;
  }

  if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.webmanifest') {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_VERSION);
      const cached = await cache.match(request, { ignoreSearch: true });
      if (cached) {
        event.waitUntil(fetch(request).then((response) => {
          if (response && response.ok) return cache.put(request, response.clone());
        }).catch(() => undefined));
        return cached;
      }
      try {
        const response = await fetch(request);
        if (response && response.ok) await cache.put(request, response.clone());
        return response;
      } catch (_) {
        return Response.error();
      }
    })());
  }
});
