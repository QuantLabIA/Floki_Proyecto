# Floki Manager v2.5 · Cloud + PWA

Versión preparada para la fase de producción de Floki Manager. Conserva todas las funciones y el diseño **Floki Minimal Luxe** de la v2.4.1, pero agrega una arquitectura dual:

- **SQLite local** para probar en una computadora sin configurar servicios externos.
- **PostgreSQL cloud** cuando existe la variable `DATABASE_URL`.
- **PWA instalable** desde celular, tablet o computadora.
- **Gunicorn** y configuración lista para Railway.

## Qué cambia en esta fase

- La aplicación ya puede vivir en un servidor y abrirse mediante una URL aunque la computadora personal esté apagada.
- Administrador, boletería y bebidas utilizan una misma base PostgreSQL.
- Se agregó `/health` para comprobar aplicación y base de datos.
- Se agregaron cookies seguras, cabeceras de seguridad y compatibilidad con proxy HTTPS.
- El ícono **Instalar app** aparece cuando el navegador lo permite.
- Se muestra el estado `En línea` / `Sin conexión`.
- Los archivos estáticos se guardan para que la aplicación abra con rapidez.
- Las páginas privadas y datos de caja **no se guardan en la caché del navegador**.

> Esta entrega instala la aplicación y muestra una pantalla segura cuando no hay red. Las ventas sin conexión y su sincronización automática corresponden a la siguiente subfase; no deben registrarse operaciones cuando el indicador diga `Sin conexión`.

## Uso local con SQLite

### Windows

Ejecutá:

```text
start_windows.bat
```

### Linux/macOS

```bash
./start_linux_mac.sh
```

Sin `DATABASE_URL`, la aplicación crea y utiliza:

```text
data/floki.db
```

Usuarios iniciales:

- Administrador: `admin` / `admin123`
- Boletería: `cajero` / `floki123`
- Bebidas: `bebidas` / `floki123`

Cambiá las tres contraseñas antes de usarla con dinero real.

## Publicación cloud

Seguí [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md). La carpeta ya incluye:

- `railway.json`
- `Procfile`
- `.env.example`
- `Gunicorn`
- cliente PostgreSQL
- endpoint `/health`

## Migrar datos locales

Para una base PostgreSQL nueva:

```bash
python migrate_sqlite_to_postgres.py \
  --sqlite data/floki.db \
  --database-url "postgresql://..." \
  --replace
```

El comando reemplaza el contenido de la base PostgreSQL destino. No debe ejecutarse sobre una base que ya tenga operaciones nuevas.

## Instalar desde el celular

Después de publicar la URL:

- Android/Chrome: abrí la URL y usá `Instalar app`.
- iPhone/Safari: Compartir → `Agregar a pantalla de inicio`.

La aplicación queda con el ícono de Floki y se abre sin la barra normal del navegador.

## Base de datos y respaldos

- En modo local, Configuración permite generar respaldos `.db`.
- En modo PostgreSQL, los respaldos deben configurarse en el proveedor cloud. La aplicación no crea copias SQLite de una base remota.

## Archivos principales de producción

```text
app.py                         Aplicación Flask
 database.py                   Compatibilidad SQLite/PostgreSQL
 migrate_sqlite_to_postgres.py Migración opcional
 railway.json                  Configuración Railway
 Procfile                      Inicio con Gunicorn
 .env.example                  Variables necesarias
 static/manifest.webmanifest   Instalación PWA
 static/service-worker.js      Caché segura de recursos
```
