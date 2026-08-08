# Floki Manager v2.8.4

## Operación de bebidas
- Todas las ventas pagas de bebidas se guardan como efectivo operativo.
- Se elimina el selector de medio de pago para Caja de Bebidas y para 50% cumpleaños.
- BENEFICIO RRPP sigue sin sumar recaudación.
- Champagne mantiene el combo obligatorio de 1 botella + 2 Speed.

## Cierre de la noche
- Nuevo campo `declared_mercadopago` en `cash_sessions`.
- Nuevo `declared_total` y `expected_total`.
- El cierre pide **Plata en efectivo** y **Declarar plata en Mercado Pago**.
- Diferencia = `(efectivo declarado + Mercado Pago declarado) - total esperado`.
- Los eventos viejos conservan compatibilidad con el cálculo de cierre anterior.

## Dashboard
- Se retiran las tarjetas Bebida especial, Venta especial y Registrar gasto.
- El resumen de medios aclara que las bebidas se registran como efectivo operativo.
- El bloque final del evento muestra Total esperado en vez de Efectivo esperado.

## Catálogo
- Se elimina el campo manual Orden al crear una bebida.
- Las variantes se ordenan automáticamente por categoría y nombre.

## Estabilidad
- Sigue siendo una versión online estable. No se reactiva Offline First.
