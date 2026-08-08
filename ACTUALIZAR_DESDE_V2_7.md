# Actualizar Floki Manager v2.7 → v2.8

No borres PostgreSQL ni las variables de Railway.

1. Subí `floki_manager_v2_8_stock_dashboard_simplificado.zip` a la raíz del Codespace conectado al repositorio de Floki.
2. Ejecutá:

```bash
unzip -o floki_manager_v2_8_stock_dashboard_simplificado.zip
cp -r floki_manager_v2_8_operacion_stock/. .
rm -rf floki_manager_v2_8_operacion_stock

git add .
git commit -m "Floki Manager v2.8 stock y dashboard simplificado"
git push
```

3. Esperá que Railway deje el nuevo deployment en `ACTIVE`.
4. Comprobá `/health`. Debe indicar versión `2.8.0` y base `postgresql`.
5. Entrá como administrador y revisá:
   - Dashboard: Ventas / Tickets vendidos / Ingresos / Guardarropa.
   - Stock: planilla descargable, carga XLSX/PDF y conteo simplificado.
   - Configuración → Bebidas: rendimiento aproximado y botón Eliminar.

La migración agrega `approx_yield` a las bebidas existentes y renombra `vaso grande` a `vaso grande 750 ml` automáticamente.
