// Floki Manager v2.10.6 — Service Worker AISLADO y recuperable.
// Scope exclusivo: /floki-offline/. Nunca controla Dashboard, Login, Ajustes, Historial ni reportes.
const CACHE_PREFIX = 'floki-offline-v2105-';
const CACHE_VERSION = `${CACHE_PREFIX}v2-10-6`;
const SHELL_KEY = '/floki-offline/?shell=v2.10.6';
const PRECACHE = [
  SHELL_KEY,
  '/floki-offline/manifest.webmanifest',
  '/floki-offline/assets/offline-sync.js',
  '/floki-offline/assets/offline-page.js',
  '/floki-offline/assets/icon-192.png',
  '/floki-offline/assets/icon-512.png',
  '/floki-offline/assets/floki-logo-white.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_VERSION);
    for (const url of PRECACHE) {
      try {
        const response = await fetch(url, { cache: 'reload', credentials: 'same-origin' });
        if (response && response.ok) await cache.put(url, response.clone());
      } catch (_) {}
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_VERSION).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

const fallbackShell = async () => {
  const cache = await caches.open(CACHE_VERSION);
  return (await cache.match(SHELL_KEY)) || new Response(
    '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:0;background:#050508;color:#fff;font-family:system-ui;padding:24px"><h1>Floki Offline</h1><p>Conectate una vez y abrí nuevamente el modo offline.</p><p><a style="color:#d39aff" href="/floki-offline-reset">Reparar caché offline</a></p></body>',
    { headers: { 'Content-Type': 'text/html; charset=utf-8' } },
  );
};

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  if (request.mode === 'navigate' && url.pathname.startsWith('/floki-offline/')) {
    event.respondWith((async () => {
      try {
        const response = await fetch(request, { cache: 'no-store', credentials: 'same-origin' });
        if (response && response.ok) {
          const cache = await caches.open(CACHE_VERSION);
          await cache.put(SHELL_KEY, response.clone());
        }
        return response;
      } catch (_) {
        return fallbackShell();
      }
    })());
    return;
  }

  if (url.pathname.startsWith('/floki-offline/assets/') || url.pathname === '/floki-offline/manifest.webmanifest') {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_VERSION);
      try {
        const response = await fetch(request, { cache: 'no-cache', credentials: 'same-origin' });
        if (response && response.ok) await cache.put(url.pathname, response.clone());
        return response;
      } catch (_) {
        return (await cache.match(url.pathname)) || Response.error();
      }
    })());
  }
});
