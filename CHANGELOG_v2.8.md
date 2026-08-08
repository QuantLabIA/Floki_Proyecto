# Floki Manager v2.8 · Stock y dashboard simplificado

## Carga inteligente de stock

- Nueva planilla Excel oficial descargable desde la pestaña Stock.
- La planilla se entrega con las bebidas activas del evento y columnas simples para completar cantidad inicial y final.
- El mismo archivo XLSX puede volver a cargarse desde Carga inteligente de stock.
- La importación sigue aceptando archivos externos PDF/XLSX y categoriza automáticamente las bebidas cuando puede reconocerlas.

## Stock y conteo

- Se simplificó la tabla para dejar solo los datos importantes.
- El administrador ve: bebida, inicial, vendido, consumo aproximado, final y rendimiento real.
- La columna Vendido funciona como contador parcial de unidades entregadas durante la noche.
- El personal de bebidas mantiene un conteo ciego: solo bebida, cantidad inicial y cantidad final.
- El control parcial duplicado fue retirado del dashboard; la información vive en Stock.

## Rendimiento aproximado

- Cada bebida activa tiene ahora un rendimiento aproximado configurable.
- El valor sirve para estimar consumo durante el evento y no reemplaza el rendimiento real calculado al cierre.
- Si se deja en Automático, Floki propone un valor según presentación y unidad de stock.
- “Vaso grande” pasa a identificarse como “Vaso grande 750 ml”.

## Catálogo de bebidas

- Las bebidas eliminadas/desactivadas dejan de mostrarse en el catálogo activo y en nuevas planillas.
- Los registros históricos se conservan internamente para no romper eventos cerrados.

## Dashboard

- Carga inteligente de stock retirada del dashboard; queda en la pestaña Stock.
- Tarjetas del administrador: Ventas, Tickets vendidos, Ingresos y Guardarropa.
- Se elimina el panel Control parcial del dashboard.
- Evento abierto, banner, cambio de imagen y cierre de caja pasan al final del dashboard.
- Operación manual de caja deja de mostrar Ventas parciales.

## Compatibilidad

- Mantiene PostgreSQL, Railway, PWA y Offline Seguro Etapa 1 de v2.7.
- No vuelve a cachear dashboards ni pantallas.
