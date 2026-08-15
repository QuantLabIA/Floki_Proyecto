# Floki Manager v2.10.5 — Offline Fresh Scope

- Nuevo namespace `/floki-offline/` para escapar completamente del Service Worker/caché histórico de `/offline-app/`.
- La aplicación online ya no registra ningún Service Worker. El worker se instala únicamente desde la mini-app offline.
- Nuevo `/floki-offline-test`: HTML puro, sin JS ni CSS externo, para confirmar que Railway desplegó v2.10.5.
- Nuevo `/floki-offline-reset`: elimina workers/cachés viejas sin borrar IndexedDB ni operaciones pendientes.
- Cache prefix nuevo `floki-offline-v2105-*` y Service Worker con scope exclusivo `/floki-offline/`.
- `/offline-app/` se conserva solo por compatibilidad; ya no debe usarse para las nuevas instalaciones.
