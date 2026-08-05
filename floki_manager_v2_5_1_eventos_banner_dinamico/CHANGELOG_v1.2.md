# Cambios de Floki Manager v1.2

## Agregado

- Tablas SQLite `entry_prices`, `beverage_products`, `promoter_guests` y `guest_checkins`.
- Carga de listas CSV, TXT y XLSX sin dependencias adicionales.
- Normalización de nombres para detectar mayúsculas, tildes y espacios repetidos.
- Restricción de un ingreso por nombre y jornada.
- Venta rápida de entradas y bebidas.
- Precios automáticos por horario.
- Gestión de bebidas activas e inactivas.
- Pantalla móvil exclusiva para listas RRPP.

## Modificado

- Dashboard orientado a botones rápidos.
- Navegación móvil con acceso directo a Listas.
- Precios de venta seleccionables solo en múltiplos de $1.000.
- Anulación de un ingreso por lista libera el nombre para corregirlo.

## Compatibilidad

- Instalación desde cero.
- Migración automática desde bases v1.0 y v1.1.
