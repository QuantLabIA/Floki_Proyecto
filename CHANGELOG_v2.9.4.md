# Floki Manager v2.9.4 — Importación selectiva entre eventos

## Nuevo flujo al abrir una jornada

Cuando no hay un evento abierto y existe un evento anterior cerrado, el formulario de **Nuevo evento** muestra el bloque **Importar del evento anterior**.

El administrador puede decidir con casilleros qué reutilizar:

- **Inventario / stock**
  - El stock final del evento anterior pasa a ser stock inicial del evento nuevo.
  - Cada bebida tiene su propio casillero para poder excluir productos puntuales.
  - Si no se marca Inventario, el evento nuevo arranca con stock inicial 0 y se puede cargar manualmente.

- **Gastos**
  - Cada gasto no anulado del evento anterior aparece con descripción, importe y medio de pago.
  - Se pueden destildar gastos que no correspondan a la nueva jornada.
  - Los gastos importados se crean como movimientos nuevos del evento actual, con fecha/hora nueva.

## Aislamiento entre eventos

No se copian ventas, entradas, tickets, vouchers, beneficios, listas RRPP, cumpleaños ni check-ins. Esos datos continúan siendo históricos y exclusivos de cada evento.

## Seguridad de datos

- La importación usa únicamente el último evento cerrado existente en la base.
- Los IDs enviados desde el formulario se validan contra el stock y los gastos de ese evento.
- La creación del evento + stock + gastos se confirma en una sola transacción. Si algo falla, se revierte todo para evitar un evento parcialmente creado.
- Compatible con SQLite y PostgreSQL/Railway.

## Versión

- `APP_VERSION`: `2.9.4`
