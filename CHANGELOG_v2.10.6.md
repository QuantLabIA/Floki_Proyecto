# Floki Manager v2.10.6 — Speed $0 + Anular/Borrar bebidas

## Speed incluido con Champagne sin volver a crear combos
- Speed conserva su botón y precio normal de venta.
- Cada variante Speed muestra además un botón operativo `$0 · incluido con Champagne`.
- Ambos botones usan el mismo `beverage_product_id`, por lo que descuentan del mismo stock físico y no duplican inventario.
- El movimiento $0 usa la categoría `drink_zero`: no suma recaudación ni tickets pagos, sí descuenta stock y aparece entre los beneficios/$0 al final del reporte completo.
- El filtro `Beneficios $0` del historial de bebidas también incluye estos movimientos.
- El modo `/floki-offline/` soporta la misma operación `beverage_zero` y la sincroniza con el backend.

## Corrección de una bebida registrada
Para movimientos de bebidas del evento abierto, el administrador puede elegir:
- **Anular**: el movimiento permanece visible como ANULADO, pero no cuenta en ventas, stock consumido ni reportes económicos.
- **Borrar**: el movimiento desaparece de la lista operativa y tampoco cuenta. Se eliminan también ajustes/componentes dependientes del movimiento.

La opción Borrar se limita al evento abierto para preservar la auditoría de eventos ya cerrados.

## Offline
- Se mantiene la arquitectura `Fresh Scope` de v2.10.5.
- Service Worker aislado bajo `/floki-offline/` actualizado a v2.10.6.
