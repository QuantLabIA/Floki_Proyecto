# Cómo funciona el stock automático

Floki separa dos conceptos:

- **Unidad de venta:** lo que recibe el cliente. Ej.: vaso grande 750 ml, shot, lata o botella.
- **Unidad física de stock:** lo que contás al abrir/cerrar. Ej.: botella, lata o unidad.

Ejemplos:

| Venta | Unidad física | Rendimiento automático | Una venta consume aprox. |
|---|---|---:|---:|
| Fernet · vaso grande 750 ml | botella | 8 vasos/botella | 0,125 botella |
| Vodka · vaso grande 750 ml | botella | 8 vasos/botella | 0,125 botella |
| Shot | botella | 20 shots/botella | 0,05 botella |
| Cerveza · lata | lata | 1 lata/lata | 1 lata |
| Champagne · botella | botella | 1 botella/botella | 1 botella |

Durante la noche el sistema muestra consumo y remanente estimados. Al final se carga el conteo físico real; con ese dato se calcula el rendimiento real del evento.


## Regla Champagne + Speed (v2.8.3)

Toda unidad de Champagne se maneja como combo operativo: **1 Champagne + 2 Speed**.
Esto aplica a venta normal, bebida a precio especial, BENEFICIO RRPP y 50% cumpleaños.
La promo de cumpleaños ya registra el mismo combo.
El precio corresponde al Champagne/combo y los Speed se descuentan como componente de stock con ingreso $0.
Si se venden 3 Champagne, el sistema registra 3 botellas de Champagne y 6 Speed.
Al anular la venta original, también se anula automáticamente el descuento de Speed asociado.
