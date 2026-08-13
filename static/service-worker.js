// Floki Manager v2.10.2 — worker raíz de recuperación heredada.
// NO se registra en v2.10.2. Si un navegador viejo lo solicita, se autodesinstala.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    try {
      const keys = await caches.keys();
      await Promise.all(keys.filter((key) => key.startsWith('floki-manager-')).map((key) => caches.delete(key)));
    } catch (_) {}
    try { await self.registration.unregister(); } catch (_) {}
  })());
});
// Sin handler fetch: jamás intercepta navegación.
