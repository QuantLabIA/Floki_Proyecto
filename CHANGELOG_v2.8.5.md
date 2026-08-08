# Floki Manager v2.8.5 · Voucher RRPP

- Voucher RRPP visible para Administrador y Caja de Bebidas.
- Valor fijo: **$0**.
- Cantidad fija: **1 consumición** por operación.
- Se eliminan del formulario los campos de cantidad y valor.
- El backend fuerza cantidad 1 y precio 0 aunque una petición manual intente enviar otros valores.
- La bebida elegida descuenta exactamente una unidad vendida según su unidad física/rendimiento de stock.
- Si la bebida elegida es Champagne, mantiene la regla global del catálogo: 1 Champagne + 2 Speed.
- No se elige promotor y no suma recaudación.
- Mantiene la base online estable, sin reactivar Offline First.
