# Floki Manager v2.10.3 — Offline iPhone Render Fix

## Corrección principal
- Corrige la pantalla blanca exclusiva de `/offline-app/` en iPhone/iPad.
- El servidor ya entregaba correctamente el HTML; el problema estaba en el renderizado WebKit del shell offline, que seguía usando efectos de composición pesados (blur/backdrop-filter/mask) que ya habían dado problemas en la app principal.
- El módulo offline ahora usa un modo visual seguro: sin backdrop-filter, sin blur fijo, sin máscaras y con fondos sólidos.
- Se eliminó la recarga automática posterior a instalar el Service Worker, evitando bucles o flashes en Safari/PWA.
- El Service Worker sigue limitado exclusivamente a `/offline-app/`; Dashboard, Login, Ajustes, Historial y Cerrar caja continúan fuera de su alcance.
- Se incrementa la caché aislada a v2-10-3 para descartar assets viejos del módulo offline.

## Funcionalidad
- No se elimina el modo sin conexión.
- Se conserva IndexedDB, cola local, sincronización y protección contra duplicados de v2.10.2.
