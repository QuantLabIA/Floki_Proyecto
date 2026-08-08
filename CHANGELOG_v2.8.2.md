# Floki Manager v2.8.2 — Bebidas agrupadas y stock automático

## Stock y rendimiento
- La cantidad vendida representa la consumición entregada al cliente, no la unidad física del depósito.
- Ejemplo: 1 Fernet vendido = 1 vaso. Si el rendimiento automático es 8 vasos por botella, se registra un consumo estimado de 0,125 botella.
- Las ventas físicas 1 a 1 mantienen equivalencia directa: 1 lata vendida = 1 lata de stock; 1 botella vendida = 1 botella de stock.
- El rendimiento aproximado deja de ser editable y se calcula automáticamente según unidad física, presentación y tipo de bebida.
- El stock muestra consumo estimado y stock estimado restante sin agregar nuevas columnas.
- El rendimiento real sigue calculándose al cierre con stock inicial, stock final y consumiciones registradas en ese evento.

## Categorías de bebidas
Las variantes activas se agrupan automáticamente en este orden:
1. CERVEZAS
2. FERNET
3. VODKA
4. WHISKY
5. TRAGOS
6. GASEOSAS
7. SHOTS
8. CHAMPAGNE

Las marcas y variantes ya creadas se conservan. Gin, Ron, Gancia, aperitivos y otros tragos se muestran dentro de TRAGOS. Energizantes, agua y gaseosas se muestran dentro de GASEOSAS. Una variante cuya presentación sea `shot` se muestra en SHOTS.

La agrupación aparece tanto en Administración como en el usuario Caja de bebidas, incluyendo los selectores de beneficio RRPP, cumpleaños y bebida especial.

## Precios
- Los precios de bebidas ahora permiten incrementos de $500.
- Se aceptan valores como $4.500, $5.500, $6.500, etc.
- Las entradas y el resto de la operación manual conservan sus reglas anteriores de $1.000.

## Estabilidad
- Continúa basada en la rama estable online v2.8.1.
- Offline First sigue desactivado.
- No se modifica ni reinicia PostgreSQL.
