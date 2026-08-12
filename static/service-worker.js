// Floki Manager v2.10.1 — Service Worker de recuperación.
// Este archivo existe únicamente para retirar de forma segura el Service Worker
// de v2.10.0 que podía controlar toda la aplicación en iPhone.

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.filter((key) => key.startsWith('floki-manager-')).map((key) => caches.delete(key)));
    } catch (_) {}
    try {
      await self.registration.unregister();
    } catch (_) {}
    try {
      const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      for (const client of clients) client.navigate(client.url);
    } catch (_) {}
  })());
});

// Deliberadamente NO hay handler de fetch: ninguna navegación ni recurso de Floki
// queda interceptado por este worker.
