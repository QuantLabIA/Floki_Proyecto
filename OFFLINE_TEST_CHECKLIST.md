# Prueba controlada de Floki Manager v2.6

Realizar primero con un evento ficticio.

## Preparación

- [ ] Railway muestra `Deployment successful`.
- [ ] `/health` indica versión `2.6.0` y base `postgresql`.
- [ ] Administrador, boletería y bebidas tienen contraseñas propias.
- [ ] El evento de prueba está abierto.
- [ ] Cada dispositivo abrió el dashboard con internet.
- [ ] Los dispositivos fueron instalados como PWA o abiertos en navegador compatible.

## Boletería

- [ ] Desactivar Wi-Fi/datos.
- [ ] Registrar una entrada general.
- [ ] Registrar guardarropa.
- [ ] Buscar una persona y confirmar FREE.
- [ ] Verificar que el contador de pendientes aumente.
- [ ] Cerrar y volver a abrir la PWA sin conexión.
- [ ] Confirmar que aparece el evento guardado.
- [ ] Recuperar internet y sincronizar.
- [ ] Verificar movimientos en administración.

## Bebidas

- [ ] Desactivar Wi-Fi/datos.
- [ ] Registrar una bebida normal.
- [ ] Registrar BENEFICIO RRPP.
- [ ] Registrar una bebida especial con comentario.
- [ ] Recuperar internet y sincronizar.
- [ ] Verificar movimientos y descuento de stock.

## Conflictos

- [ ] Con dos dispositivos offline, confirmar el mismo nombre.
- [ ] Reconectar el primero: debe aplicar el ingreso.
- [ ] Reconectar el segundo: debe mostrar conflicto, sin duplicar ingreso.
- [ ] Descartar el conflicto desde `/offline-operations`.

## Cierre

- [ ] Confirmar `0 pendientes` en cada dispositivo.
- [ ] Completar stock final.
- [ ] Cerrar el evento desde administración con internet.
- [ ] Revisar reportes y totales.
