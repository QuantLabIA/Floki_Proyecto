# Floki Manager v2.6 · Offline First

- Cola local en IndexedDB.
- Identificador único por operación.
- Sincronización idempotente con PostgreSQL.
- Ventas rápidas y check-ins pasan primero por la cola local, incluso cuando hay internet.
- Recuperación automática al volver la conexión.
- Pantalla `/offline-operations` utilizable desde la PWA.
- Catálogo, precios, evento y listas descargados por usuario/sector.
- Conflictos visibles y descartables.
- Bloqueo local del cierre cuando quedan pendientes en el dispositivo.
- Nueva tabla `offline_operations` compatible con SQLite y PostgreSQL.
- Service worker actualizado para abrir la pantalla operativa sin conexión.
- Banners dinámicos de eventos conservados.
