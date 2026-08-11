# Floki Manager v2.9.10 — PostgreSQL Percent Fix

## Corrección crítica
- Corrige `ProgrammingError: only '%s', '%b', '%t' are allowed as placeholders, got '%'`.
- La adaptación SQLite → PostgreSQL ahora escapa correctamente porcentajes SQL usados en `LIKE`.
- Corrige específicamente el cierre de caja: al cerrar se limpia la descripción de listas con `LIKE 'Lista:%'`, consulta que PostgreSQL/psycopg rechazaba.
- Corrige además las consultas de Speed, Energizantes y Champagne que contienen patrones `%...%`.
- No elimina ni modifica datos históricos.

## Validación
- Prueba específica del patrón `%speed%`.
- Prueba específica de la consulta ejecutada al limpiar listas durante el cierre de caja.
