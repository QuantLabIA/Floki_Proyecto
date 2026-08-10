# Floki Manager v2.9.0

## Champagne + 2 Speed: corrección estructural

- Una venta de Champagne vuelve a ser un único movimiento monetario.
- Los 2 Speed incluidos ya no se crean como una segunda venta en `movements`.
- Se agregó `beverage_stock_adjustments`, una tabla dedicada exclusivamente a componentes automáticos de stock.
- Cada Champagne vendido descuenta automáticamente 2 Speed del stock sin generar ingreso ni ticket adicional.
- La operación es atómica: si falla el componente Speed, se revierte también la venta principal.
- Al anular el Champagne se anula automáticamente su ajuste de 2 Speed.
- Se conserva compatibilidad con movimientos `champagne_speed` históricos.
- La promo de cumpleaños Champagne + 2 Speed utiliza la misma lógica segura.

## Historial completo para Caja de Bebidas

- Nuevo acceso `Historial bebidas` para el usuario del sector Bebidas.
- Muestra operaciones de bebidas del evento actual y eventos anteriores.
- Filtros por evento, fecha y tipo: todas, ventas pagas, beneficios $0 o anuladas.
- Paginación de 100 registros para mantener velocidad con historiales grandes.
- No muestra ganancias o recaudación acumulada: conserva la separación de permisos del administrador.
- Los Speed incluidos con Champagne no aparecen como ventas separadas.

## Navegación

- Caja de Bebidas ahora tiene: Caja, Stock, Historial, Cuenta y Salir en móvil.
- En el bloque Últimos movimientos aparece `Ver historial completo`.
- Navegación adaptada a cinco accesos en iPhone respetando safe areas.

## Stock

- El consumo estimado usa los movimientos de stock reales, incluyendo componentes de combos.
- En la vista del administrador se indica cuántos Speed fueron incluidos automáticamente con Champagne.
