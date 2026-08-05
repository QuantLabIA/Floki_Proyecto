# Floki Manager v1.7 · Bloque 1

## Rendimiento automático por evento

- Ya no se carga manualmente cuántos vasos rinde una botella.
- El rendimiento se calcula con: unidades vendidas / (stock inicial - stock final).
- El cálculo se realiza únicamente para el evento actual.
- No se crea ni se guarda un promedio histórico.
- Si falta el conteo final, el rendimiento aparece pendiente.
- Si el conteo no permite calcularlo, el sistema solicita revisarlo.

## Excel dinámico

- El Excel contiene solamente las bebidas creadas y activas en el sector Bebidas.
- Una bebida nueva se agrega automáticamente al evento abierto y al próximo Excel.
- Una bebida desactivada deja de aparecer en la planilla y exportación.
- El Excel muestra ventas normales, especiales, beneficios RRPP, stock utilizado y rendimiento real.

## Nombres visibles

- El administrador puede modificar el nombre visible de cualquier acceso.
- La cabecera separa el sector o rol del nombre de la persona.
- Ejemplos: `Administrador · Pablo`, `Caja de boletería · Martina`, `Caja de bebidas · Lucas`.

## Alcance

Esta entrega mantiene el diseño visual de la v1.6. El rediseño Floki Club queda reservado para el siguiente bloque.
