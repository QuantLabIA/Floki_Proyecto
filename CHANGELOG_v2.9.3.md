# Floki Manager v2.9.3 — Champagne Stable Fix

## Corrección crítica de Champagne pago

- La venta paga de Champagne deja de depender de que el registro secundario de los 2 Speed termine correctamente.
- Se usa un `SAVEPOINT` para aislar el descuento del acompañamiento en PostgreSQL/Railway.
- Ruta principal: los 2 Speed se guardan en `beverage_stock_adjustments`.
- Si esa escritura falla, Floki usa automáticamente un movimiento histórico `champagne_speed` de $0, vinculado a la venta principal.
- El fallback está excluido de tickets, recaudación y ranking de bebidas pagas: **1 Champagne = 1 ticket**.
- Si incluso el fallback de stock falla, la venta principal de Champagne se conserva y se muestra una advertencia de stock en vez de borrar el cobro completo.
- La anulación de la venta principal continúa anulando tanto ajustes nuevos como componentes históricos vinculados.

## Resultado esperado

1. Tocar Champagne con precio normal.
2. Registrar exactamente una venta paga y un ticket.
3. Descontar una unidad de Champagne del stock.
4. Descontar dos Speed automáticamente, sin sumar ventas ni ingresos adicionales.
5. Evitar el error genérico que revertía la compra completa cuando fallaba el componente Speed.

## Versión

- `APP_VERSION`: `2.9.3`
- Acumulativa sobre v2.9.2.
