# Floki Manager v2.8.1 — Estable sin Offline

## Motivo
La pantalla blanca reapareció al incorporar Offline Seguro en v2.7. La v2.6.4 había quedado estable, por lo que v2.8.1 vuelve al mismo criterio de estabilidad online y conserva las mejoras funcionales de v2.8.

## Cambios
- Se desactiva por completo la carga automática de `offline-sync.js`.
- Se retira el registro del Service Worker.
- Al cargar, se desregistran Service Workers anteriores y se eliminan cachés `floki-manager-*`.
- El Service Worker incluido se auto-retira y no intercepta solicitudes.
- No se elimina IndexedDB automáticamente para no perder posibles operaciones offline pendientes.
- Se mantienen las mejoras v2.8 de Stock, planilla XLSX, dashboard, rendimiento aproximado, vasos grandes de 750 ml y eliminación de bebidas.
- PostgreSQL, usuarios, listas, caja y configuración no cambian.

## Estado
Versión recomendada para producción hasta rediseñar Offline First como un módulo separado y probado.
