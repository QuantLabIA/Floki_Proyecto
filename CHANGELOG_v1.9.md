# Floki Manager v1.9 · Listas y catálogo de bebidas

## Boletería

- La entrada FREE ya no puede registrarse con un botón manual.
- Cada FREE se genera únicamente al confirmar una persona previamente cargada en Listas RRPP o Lista común.
- Se eliminaron de las nuevas ventas las categorías Anticipada y VIP.
- La entrada general conserva el precio automático antes/después del horario configurado.
- Los movimientos históricos de VIP y anticipadas se conservan en SQLite y en reportes anteriores.

## Privacidad del sector Bebidas

- La caja de bebidas no ve unidades vendidas, movimientos acumulados, rendimiento ni totales parciales.
- El endpoint de estado tampoco entrega conteos de bebidas a usuarios no administradores.
- El Excel de stock es exclusivo del administrador.
- La caja de bebidas mantiene un conteo ciego para cargar cantidad inicial y cantidad final.

## Catálogo de bebidas por variantes

- Alta guiada mediante opciones de tipo, marca, presentación, unidad de stock y precio.
- Opción de marca personalizada para productos no incluidos en el catálogo.
- Cada combinación crea un botón independiente, por ejemplo:
  - Cerveza Quilmes · Lata 473 ml.
  - Cerveza Quilmes · Vaso.
- Cada variante puede tener un precio distinto.
- Latas, vasos, botellas, copas, shots, jarras y baldes se mantienen separados.
- Las variantes nuevas se agregan automáticamente al evento abierto, stock y Excel administrativo.
