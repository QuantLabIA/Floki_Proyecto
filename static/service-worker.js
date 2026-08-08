const FLOKI_SW_VERSION = 'floki-manager-v2-8-safe-stage-1';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // Retira cualquier caché de las versiones experimentales anteriores.
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith('floki-manager-')).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

// IMPORTANTE: no usamos event.respondWith().
// Todas las páginas y recursos continúan yendo directamente a Railway.
// La cola offline de Etapa 1 vive en IndexedDB y funciona mientras la app ya está abierta.
self.addEventListener('fetch', () => {});
