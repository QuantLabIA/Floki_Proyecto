# Floki Manager v2.9.1 — Horarios + Ranking + Reporte de beneficios

## Cambios principales

- Hora oficial de la aplicación fijada en `America/Argentina/Buenos_Aires`, independiente de la zona horaria del servidor/Railway.
- Operaciones offline sincronizadas por epoch se convierten explícitamente a hora argentina.
- Cada botón de bebida muestra `vendidas hoy` (solo ventas pagas para el contador operativo).
- Las categorías y variantes de bebidas se ordenan automáticamente según las unidades pagas del evento cerrado anterior. Los beneficios $0 no alteran el ranking.
- Champagne pago queda desacoplado del ajuste auxiliar de Speed: la venta principal se registra como un único ticket aunque falte una variante activa de Speed. Si Speed existe, descuenta 2 unidades automáticamente por Champagne.
- El reporte completo, impresión/PDF y CSV muestran primero movimientos pagos y dejan al final beneficios, FREE y movimientos de $0.
- El voucher RRPP permite agregar un comentario opcional / nombre del beneficiario, visible luego en el historial y reportes.
- El voucher continúa forzado en backend a 1 consumición y $0.

## Compatibilidad

- Conserva SQLite y PostgreSQL.
- No elimina datos ni cambia IDs históricos.
- Mantiene compatibilidad con movimientos históricos `champagne_speed` de versiones anteriores.
