# Aplicar Floki Manager v2.6.1

Con el ZIP cargado en la raíz del repositorio:

```bash
unzip -o floki_manager_v2_6_1_hotfix_pantalla_blanca.zip
cp -r floki_manager_v2_6_1_hotfix_pantalla_blanca/. .
rm -rf floki_manager_v2_6_1_hotfix_pantalla_blanca
git add .
git commit -m "Floki Manager v2.6.1 hotfix pantalla blanca"
git push
```

Esperá a que Railway muestre `Deployment successful`. En `/health` debe aparecer `version: 2.6.1` y `database: postgresql`. Después abrí `/login` en una pestaña de incógnito.
