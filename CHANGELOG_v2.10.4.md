# Floki Manager v2.10.4 — Offline Recovery + Self-contained Shell

- `/offline-app/` incluye su CSS dentro del HTML para no depender de una hoja de estilos cacheada.
- Nueva ruta `/offline-recover`, fuera del alcance del Service Worker, para desregistrar solamente el worker offline y limpiar cachés offline sin borrar IndexedDB ni operaciones pendientes.
- Service Worker v2.10.4 con navegación y assets network-first cuando hay conexión.
- El registro del Service Worker se retrasa hasta después del primer render para priorizar que Safari pinte la pantalla.
- Ajustes incorpora accesos Abrir offline y Reparar caché.
- El Service Worker conserva scope exclusivo `/offline-app/`.
