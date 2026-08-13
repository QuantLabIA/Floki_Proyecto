// Floki Manager v2.10.2 — Service Worker AISLADO.
// Scope exclusivo: /offline-app/. Nunca controla Dashboard, Login, Ajustes, Historial ni reportes.
const CACHE_PREFIX = 'floki-offline-app-';
const CACHE_VERSION = `${CACHE_PREFIX}v2-10-2`;
const SHELL = '/offline-app/';
const PRECACHE = [
  SHELL,
  '/offline-app/manifest.webmanifest',
  '/offline-app/assets/app.css',
  '/offline-app/assets/offline-sync.js',
  '/offline-app/assets/offline-page.js',
  '/offline-app/assets/icon-192.png',
  '/offline-app/assets/icon-512.png',
  '/offline-app/assets/floki-logo-white.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_VERSION);
    for (const url of PRECACHE) {
      try {
        const response = await fetch(url, { cache: 'reload', credentials: 'same-origin' });
        if (response && response.ok) await cache.put(url, response.clone());
      } catch (_) {
        // Un asset aislado no debe impedir instalar/actualizar el worker.
      }
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys
      .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_VERSION)
      .map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

const shellFallback = async () => {
  const cache = await caches.open(CACHE_VERSION);
  return (await cache.match(SHELL, { ignoreSearch: true })) || new Response(
    '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body style="background:#08060d;color:#fff;font-family:system-ui;padding:24px"><h1>Floki Offline</h1><p>No se pudo abrir el shell local. Conectate una vez y volvé a entrar a Modo offline.</p></body>',
    { headers: { 'Content-Type': 'text/html; charset=utf-8' } },
  );
};

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // La sincronización y el bootstrap siempre dependen de red; jamás se cachean respuestas privadas.
  if (url.pathname.startsWith('/api/')) return;

  if (request.mode === 'navigate' && url.pathname.startsWith('/offline-app/')) {
    event.respondWith((async () => {
      try {
        const response = await fetch(request, { cache: 'no-store' });
        if (response && response.ok) {
          const cache = await caches.open(CACHE_VERSION);
          await cache.put(SHELL, response.clone());
        }
        return response;
      } catch (_) {
        return shellFallback();
      }
    })());
    return;
  }

  if (url.pathname.startsWith('/offline-app/assets/') || url.pathname === '/offline-app/manifest.webmanifest') {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_VERSION);
      const cached = await cache.match(request, { ignoreSearch: true });
      if (cached) return cached;
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
