# Roadmap de Floki Manager

## v2.5 — Fase cloud y PWA

- PostgreSQL para múltiples dispositivos.
- SQLite conservado para pruebas locales.
- Despliegue preparado para Railway.
- URL pública y endpoint de salud.
- Instalación PWA en celular/tablet.
- Indicador de conexión.
- Migrador SQLite → PostgreSQL.

## Próxima subfase — validación cloud

- Publicar en el repositorio GitHub del usuario.
- Crear PostgreSQL y URL en Railway.
- Probar administrador, boletería y bebidas simultáneamente.
- Revisar cierres, QR, listas, Excel y stock con datos de prueba.
- Configurar estrategia de respaldo del proveedor.

## Fase offline posterior

- Cola local de operaciones en IndexedDB.
- Identificador único por movimiento para evitar duplicados.
- Sincronización al recuperar internet.
- Detección y resolución de conflictos.
- Indicador de movimientos pendientes.
- Bloqueo de acciones no seguras sin conexión.


## v2.5.1 · Eventos con imagen opcional y banner dinámico

- Imagen opcional por evento.
- Vista previa y banner adaptativo.
- Persistencia SQLite/PostgreSQL.

## Próxima fase: v2.6 Offline First

- Cola local de operaciones.
- Sincronización al recuperar conexión.
- Prevención de duplicados y cierre condicionado a sincronización.
