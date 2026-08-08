const RETIRE_VERSION = 'floki-manager-v2-8-3-stable-online';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key.startsWith('floki-manager-')).map((key) => caches.delete(key)));
    await self.registration.unregister();
    const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    clients.forEach((client) => client.postMessage({ type: 'FLOKI_SW_RETIRED', version: RETIRE_VERSION }));
  })());
});
// Sin listener fetch: Railway entrega directamente todas las pantallas y recursos.
