# Floki Manager v2.9.8 — Cierre automático + privacidad por sector

## Cierre de caja
- El **Reporte completo** del evento abierto se trasladó al flujo de **Cerrar caja**.
- Ventas, gastos, ganancia neta, tickets, bebidas vendidas e ingresos aparecen como cuadros informativos **sin enlaces** dentro del panel de cierre.
- El administrador **ya no declara manualmente** cuánto ganó, efectivo ni Mercado Pago para cerrar el evento.
- Floki calcula automáticamente:
  - ventas totales,
  - gastos,
  - ganancia neta = ventas - gastos,
  - total final = monto inicial + ventas - gastos.
- El cierre conserva observaciones opcionales, renueva QR y limpia listas como antes.
- Los reportes de eventos cerrados continúan siendo exclusivos del administrador.

## Dashboard administrador
- Se retiraron los cuadros económicos acumulados del dashboard para concentrarlos en **Cerrar caja**.
- Se retiró el resumen monetario por medios de pago del dashboard.
- El panel **Agregar gasto** sigue disponible durante el evento; cada gasto se incorpora automáticamente al cierre.
- El banner del evento ya no muestra el total esperado durante la operación.

## Historial de eventos
- El listado del historial ya **no muestra ventas, gastos ni ganancias**.
- Solo muestra información operativa del evento (nombre, fecha, ingresos y estado).
- Al abrir un evento cerrado, el administrador sí accede a su reporte completo.
- Si se intenta abrir el reporte histórico de un evento todavía abierto, se redirige al panel de cierre.

## Caja de bebidas
- El usuario del sector Bebidas ve **exactamente los últimos 20 movimientos de bebidas** del evento abierto.
- Ya no puede navegar eventos cerrados ni el historial general de bebidas.
- Se agregó consulta obligatoria por dos extremos de tiempo:
  - **Desde · fecha y hora**
  - **Hasta · fecha y hora**
- Al indicar ambos horarios, Floki muestra **todos** los movimientos de bebidas de ese lapso, aunque superen 20 registros.
- La consulta incluye un resumen por bebida con la cantidad registrada en el intervalo.
- Administración conserva el historial completo de bebidas y filtros históricos.
