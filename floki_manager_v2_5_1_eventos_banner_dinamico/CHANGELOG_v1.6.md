# Floki Manager v1.6

## Caja de bebidas

- Nuevo voucher **BENEFICIO RRPP**.
- No solicita ni asigna promotor.
- Permite elegir bebida, cantidad y valor de referencia en múltiplos de $1.000.
- El beneficio no suma recaudación, pero descuenta mercadería del stock.
- Nueva venta de **Bebida especial** con precio variable, medio de pago y comentario obligatorio.
- La bebida especial queda vinculada al producto seleccionado para descontar el stock correcto.

## Unidades de venta y stock

Cada bebida ahora configura:

- Unidad de stock: botella, lata, caja, etc.
- Unidad de venta: vaso, lata, botella, etc.
- Rendimiento: cuántas unidades de venta salen de una unidad de stock.

Ejemplo: una botella de Fernet con rendimiento 10 puede vender 10 vasos. Si se venden 3 vasos, el sistema descuenta 0,3 botella.

## Ventas parciales

La caja de bebidas y el administrador pueden ver durante la noche:

- Ventas normales.
- Ventas especiales.
- Beneficios RRPP.
- Total de unidades entregadas.
- Stock físico consumido.
- Stock final esperado.

## Excel dinámico

- La exportación incluye las unidades, rendimiento y ventas separadas.
- Toda bebida nueva se incorpora automáticamente al stock del evento abierto.
- También aparece automáticamente en el próximo Excel descargado.
- Se agregó una guía de columnas dentro de la planilla.
