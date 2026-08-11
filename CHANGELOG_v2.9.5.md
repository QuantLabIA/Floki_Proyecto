# Floki Manager v2.9.5 — Champagne y Energizante independientes

## Corrección principal
- Se elimina para operaciones nuevas la relación automática Champagne → 2 Speed/Energizantes.
- Champagne vuelve a comportarse como cualquier bebida normal: una venta de Champagne registra únicamente Champagne.
- Energizante se carga, vende y descuenta por separado con su propio botón, precio, contador e inventario.
- Una venta paga de Champagne ya no ejecuta escrituras secundarias de stock ni movimientos auxiliares.

## Beneficios
- Voucher RRPP y 50% cumpleaños también tratan Champagne como una consumición independiente.
- El regalo de cumpleaños conserva 1 Champagne + 2 Energizantes, pero ahora se guarda como dos movimientos de beneficio separados: 1 Champagne y 2 Energizantes.
- Los movimientos gratuitos continúan apareciendo al final de los reportes según la lógica vigente.

## Compatibilidad
- Los ajustes históricos `champagne_speed` de eventos anteriores siguen leyéndose para no alterar stock ni reportes viejos.
- No hace falta borrar PostgreSQL ni reiniciar la base de datos.
- Se mantienen los cambios acumulativos de v2.9.4: importación selectiva de stock y gastos desde el evento anterior.
