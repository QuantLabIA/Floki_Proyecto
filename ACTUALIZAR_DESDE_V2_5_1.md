# Actualizar GitHub y Railway desde v2.5.1

Subí `floki_manager_v2_6_offline_first.zip` a la raíz del Codespace del repositorio.

```bash
unzip -o floki_manager_v2_6_offline_first.zip
cp -r floki_manager_v2_6_offline_first/. .
rm -rf floki_manager_v2_6_offline_first
git add .
git commit -m "Floki Manager v2.6 Offline First"
git push
```

Railway volverá a desplegar automáticamente. No borres ni reemplaces el servicio PostgreSQL.

Después verificá:

```text
https://TU-DOMINIO/health
```

Debe mostrar versión `2.6.0` y base `postgresql`.

En cada dispositivo:

1. Abrí la PWA con internet.
2. Iniciá sesión con su usuario real.
3. Recargá una vez para instalar el service worker nuevo.
4. Esperá que diga `En línea`.
5. Probá el modo avión con un evento ficticio.
