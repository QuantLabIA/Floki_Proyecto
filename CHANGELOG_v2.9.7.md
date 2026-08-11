# Floki Manager v2.9.7 — Hora del reporte + panel de listas limpio

## Horario del reporte completo

- Los timestamps nuevos se guardan con zona horaria explícita de Argentina (`-03:00`).
- El reporte completo normaliza todos los horarios a `America/Argentina/Buenos_Aires`.
- Los timestamps históricos sin zona horaria, creados por versiones que usaban el reloj UTC de Railway, se convierten a hora argentina al mostrarse en el reporte.
- El PDF/impresión y el CSV usan la misma normalización para evitar diferencias entre pantallas.
- La fecha predeterminada de un evento nuevo se calcula también con hora Argentina y no con la fecha del servidor.
- La sincronización offline acepta timestamps con `Z`/offset y los convierte correctamente a Argentina.

## Panel para pegar listas

- Se eliminaron los nombres y ejemplos del placeholder del campo para pegar mensajes.
- El campo queda limpio con el texto neutro `Pegá acá el mensaje de listas`.

## Compatibilidad

- Acumulativa sobre v2.9.6.
- No elimina eventos, movimientos, stock, gastos ni listas históricas.
