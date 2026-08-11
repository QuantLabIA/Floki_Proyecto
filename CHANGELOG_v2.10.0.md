# Floki Manager v2.10.0 · Offline Seguro

## Objetivo
Permitir que Floki siga operando durante cortes de internet sin volver a introducir la pantalla blanca de las primeras pruebas Offline First.

## Arquitectura
- Service Worker nuevo que guarda únicamente el shell operativo offline y recursos estáticos.
- Dashboard, login, reportes, APIs y respuestas privadas nunca se guardan en caché.
- Si una navegación falla por falta de conexión, la PWA abre automáticamente `/offline-operations`.
- IndexedDB conserva catálogo/evento/listas por dispositivo y una cola local de operaciones.
- Cada operación tiene un identificador único; PostgreSQL evita duplicados al sincronizar.
- Sincronización al recuperar conexión, al volver a enfocar la app y mediante botón manual.

## Operaciones disponibles sin internet
- Entrada general.
- Guardarropa.
- Check-in FREE de listas ya descargadas.
- Venta de bebidas.
- Bebida especial.
- Voucher RRPP con comentario opcional.
- 50% cumpleaños sujeto a validación al sincronizar.
- Gastos desde administrador.

## Seguridad operativa
- Crear/cerrar eventos, cambiar precios, importar datos, modificar stock final y anular movimientos siguen requiriendo internet.
- Antes de cerrar caja, todos los dispositivos deben mostrar 0 pendientes.
- Si el evento fue cerrado antes de sincronizar una operación, queda como conflicto para revisión y no se duplica.

## iPhone / PWA
Cada iPhone o iPad debe abrir Floki con internet al menos una vez con el usuario que lo usará durante la fecha. Después puede reabrirse sin conexión desde el icono PWA y caerá automáticamente al modo operativo offline.
