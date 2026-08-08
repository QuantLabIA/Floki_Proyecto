# Floki Manager v2.8.4 · Cierre efectivo + Mercado Pago

Versión operativa estable para Railway/PostgreSQL. Mantiene el modo **online estable sin Offline First** para evitar la pantalla blanca que apareció al introducir la capa offline.

## Cambios principales

- Caja de Bebidas registra todas las ventas pagas como **efectivo operativo**, sin pedir medio de pago en cada consumición.
- Al cerrar la noche, Administración declara por separado **Plata en efectivo** y **Mercado Pago**. Floki suma ambos y compara el total contra la recaudación teórica.
- `Bebida especial`, `Venta especial` y `Registrar gasto` fueron retirados del dashboard para simplificar la operación. Las rutas históricas se mantienen por compatibilidad.
- El campo manual **Orden** al crear bebidas fue eliminado. Las variantes se agrupan por categoría y se ordenan automáticamente por nombre.
- Se mantienen categorías CERVEZAS, FERNET, VODKA, WHISKY, TRAGOS, GASEOSAS, SHOTS y CHAMPAGNE.
- Todo Champagne sigue incluyendo automáticamente **2 Speed por unidad**.
- Se conserva stock automático, conteo final y rendimiento real del evento.

## Lógica del cierre

Durante la noche no hace falta marcar qué bebida se pagó por Mercado Pago. Al finalizar:

1. contás el dinero físico y lo cargás en **Plata en efectivo**;
2. cargás lo recibido por **Mercado Pago**;
3. Floki calcula `total declarado = efectivo + Mercado Pago`;
4. compara ese total con `monto inicial + ventas - gastos` y muestra la diferencia.

Los medios de pago de boletería pueden seguir registrándose individualmente. En bebidas, el campo se fija deliberadamente en efectivo para priorizar velocidad.

## Instalación local

### Windows

```text
start_windows.bat
```

### Linux/macOS

```bash
./start_linux_mac.sh
```

Sin `DATABASE_URL`, utiliza SQLite en:

```text
data/floki.db
```

## Railway y PostgreSQL

La v2.6 actualiza automáticamente el esquema y agrega la tabla `offline_operations`. No hay que borrar PostgreSQL ni crear otro proyecto.

Para actualizar:

```bash
git add .
git commit -m "Floki Manager v2.6 Offline First"
git push
```

Railway detectará el cambio y volverá a desplegar el servicio.

Comprobación:

```text
https://TU-DOMINIO/health
```

Debe indicar:

```json
{
  "status": "ok",
  "version": "2.6.0",
  "database": "postgresql"
}
```

## PWA

- Android: Chrome → Instalar aplicación.
- iPhone/iPad: Safari → Compartir → Agregar a pantalla de inicio.
- Windows: Edge/Chrome → Instalar aplicación.

## Usuarios iniciales

- Administrador: `admin` / `admin123`
- Boletería: `cajero` / `floki123`
- Bebidas: `bebidas` / `floki123`

Cambiá las contraseñas antes de usar dinero real.

## Archivos principales

```text
app.py                         Flask, validaciones y sincronización
 database.py                   SQLite/PostgreSQL
 static/js/offline-sync.js     IndexedDB, cola e idempotencia cliente
 static/js/offline-page.js     Pantalla operativa sin conexión
 static/service-worker.js      App shell y apertura offline
 templates/offline_operations.html
 tests/test_offline_first.py
```

Antes de usar la versión en una fecha real, completá las pruebas de [OFFLINE_TEST_CHECKLIST.md](OFFLINE_TEST_CHECKLIST.md).
