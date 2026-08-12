# Floki Manager v2.10.1 — Hotfix pantalla blanca

## Objetivo
Recuperar la estabilidad en iPhone/iPad después de detectar que el Service Worker de v2.10.0 podía dejar la aplicación controlada por una caché antigua y mostrar una pantalla blanca.

## Cambios
- Se desactiva temporalmente el modo offline.
- La aplicación deja de registrar Service Workers para el sitio principal.
- Al cargar Floki se desregistran Service Workers anteriores y se eliminan sólo cachés `floki-manager-*`.
- `service-worker.js` pasa a ser un worker de recuperación que se autodesinstala y no intercepta ninguna petición.
- Se elimina el acceso de modo offline de Ajustes y el contador de pendientes de la barra superior.
- No se borra IndexedDB para no perder operaciones locales que pudieran existir de pruebas anteriores.
- Se agrega `/pwa-reset` como recuperación manual de emergencia para iPhone/iPad: desregistra workers y limpia sólo cachés de Floki.
- Se conservan todos los cambios funcionales y de PostgreSQL de v2.9.10 y v2.10.0 que no dependen del Service Worker.

## Próximo enfoque offline
El modo sin internet se rehará aislado del sitio principal, con un Service Worker de alcance exclusivo para una mini-app offline, evitando que controle Dashboard, login, reportes o navegación normal.
