# Floki Manager v2.8.3 — Champagne + 2 Speed

- Toda venta/entrega de una variante agrupada como CHAMPAGNE descuenta automáticamente 2 Speed por cada Champagne.
- Aplica a venta normal, bebida especial, BENEFICIO RRPP y 50% cumpleaños.
- La promo de cumpleaños conserva 1 Champagne + 2 Speed.
- Los Speed incluidos se registran como movimiento de stock con ingreso $0, vinculado a la operación principal.
- Si el administrador anula la operación principal, se anula también el descuento de Speed asociado.
- No se puede anular el componente Speed por separado.
- Si no existe una variante activa de Speed, el sistema bloquea la operación de Champagne y muestra qué falta configurar.
- La Caja de bebidas y los selectores muestran “incluye 2 Speed” en CHAMPAGNE.
- Se mantiene el modo online estable; Offline First sigue retirado.
