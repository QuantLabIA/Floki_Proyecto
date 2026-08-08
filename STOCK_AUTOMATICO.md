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
