# Floki Manager v2.8.8 · Hotfix Champagne + guardado sin recarga

- Corrige el error 500 al vender Champagne en instalaciones PostgreSQL antiguas.
- El combo sigue siendo 1 Champagne + 2 Speed y la venta normal conserva el precio del Champagne.
- El movimiento auxiliar de Speed usa un vínculo compatible (`combo #ID`) además de reconocer vínculos históricos.
- Si una venta rápida falla, se revierte completa: no queda cobro ni stock a medias.
- Guardar precios/configuración de bebidas ya no recarga la página.
- Podés cambiar varios precios, stock físico y presentación y guardar todo junto al final.
- El diagnóstico incluye la presencia de Speed activa y movimientos de combo.
- Offline First continúa desactivado.
