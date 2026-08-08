# Floki Manager v2.8.9 — Historial de bebidas y tickets

## Correcciones

- **Tickets vendidos** ahora suma cada entrada paga y cada bebida paga vendida.
- Una bebida paga equivale a **1 ticket por unidad**.
- Los vouchers/beneficios RRPP de $0 no inflan el contador de tickets vendidos.
- Los movimientos auxiliares de los 2 Speed incluidos con Champagne tampoco cuentan como tickets extra.
- En **Historial / Auditoría** se muestra el nombre real de la bebida y su presentación, en lugar del texto genérico `Consumición × 1`.
- El reporte imprimible usa el mismo detalle real de cada venta.

Ejemplo: `Fernet Branca · Vaso grande 750 ml × 1` o `Cerveza Quilmes · Lata 473 ml × 1`.

Se mantiene la rama estable **sin Offline First**.
