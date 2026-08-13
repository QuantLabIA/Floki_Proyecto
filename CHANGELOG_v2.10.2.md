# Floki Manager v2.10.2 — Offline Aislado

## Objetivo
Recuperar el funcionamiento sin internet sin volver a exponer Dashboard, Login, Ajustes, Historial ni reportes al Service Worker que produjo la pantalla blanca en v2.10.0.

## Arquitectura
- Nueva mini-app operativa en `/offline-app/`.
- Service Worker servido desde `/offline-app/service-worker.js` con alcance máximo `/offline-app/`.
- La aplicación normal queda fuera del scope y no puede ser interceptada por este worker.
- El worker raíz anterior queda como archivo de recuperación sin `fetch` y no se registra.
- Las cachés nuevas usan prefijo `floki-offline-app-*`, separado de las cachés heredadas `floki-manager-*`.

## Preparación automática
- Al abrir Floki online, un bridge liviano registra únicamente el worker aislado y descarga a IndexedDB el evento, usuario, precios, listas, bebidas y cumpleaños disponibles para ese sector.
- El bridge no intercepta formularios ni navegación del sitio principal.
- Hay acceso visible `Modo offline` en la parte superior con contador local de pendientes.

## Operaciones offline
- Boletería: entrada general, guardarropa y confirmación FREE de personas descargadas.
- Bebidas: ventas, bebida especial, voucher RRPP con beneficiario opcional y 50% cumpleaños.
- Administrador: además puede registrar gastos.
- Cada operación recibe un ID único y el backend mantiene sincronización idempotente para no duplicarla.
- Si vuelve internet, la mini-app sincroniza y actualiza el bootstrap.

## Seguridad operativa
- Crear/cerrar evento, modificar precios, importar datos, stock final, usuarios y anulaciones siguen requiriendo internet.
- Antes de cerrar caja, todos los dispositivos deben mostrar 0 pendientes.
- Si expira la sesión mientras hay operaciones locales, no se borran: el usuario debe volver a iniciar sesión con la misma cuenta para sincronizarlas.

## iPhone/iPad
Para poder abrir Floki Offline desde cero durante un corte, abrir `/offline-app/` con internet una vez y usar Safari > Compartir > Agregar a pantalla de inicio. Ese icono abre únicamente la mini-app aislada.
