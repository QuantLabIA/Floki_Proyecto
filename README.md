# Floki Manager v2.8 · Stock y dashboard simplificado

Esta versión parte de la base estable v2.7 y simplifica el trabajo diario: agrega una planilla oficial de stock descargable/reimportable, un conteo más claro, rendimiento aproximado configurable por bebida y un dashboard administrativo más directo.

> El modo Offline Seguro Etapa 1 se conserva: no cachea páginas ni dashboards y solo prepara operaciones locales después de que la interfaz ya cargó.


Esta versión mantiene PostgreSQL, Railway, la PWA instalable y los banners dinámicos de eventos, y agrega una **cola local de operaciones** para continuar trabajando durante cortes temporales de internet.

## Qué funciona sin conexión

Después de abrir el evento y entrar al sistema al menos una vez con internet, el dispositivo guarda localmente el evento, los precios y el catálogo autorizado para ese usuario.

Pueden registrarse sin conexión:

- entrada general;
- guardarropa;
- venta normal de bebidas;
- bebida especial con comentario;
- BENEFICIO RRPP;
- 50% OFF de cumpleaños, sujeto a validación al sincronizar;
- confirmación de personas cargadas en listas RRPP, PROMOS, cumpleaños o Lista común.

Cada operación recibe un identificador único. Cuando vuelve internet, se envía a PostgreSQL y el servidor evita que se registre dos veces aunque el dispositivo reintente.

## Qué continúa requiriendo internet

Por seguridad y para evitar conflictos entre celulares:

- crear, eliminar o cerrar eventos;
- modificar usuarios y permisos;
- cambiar precios o catálogo;
- importar listas o stock;
- modificar el conteo de stock;
- anular movimientos;
- entregar el regalo físico de cumpleaños;
- exportar PDF o Excel.

## Preparar un dispositivo para trabajar offline

1. Abrí Floki Manager con internet.
2. Iniciá sesión con el usuario que realmente utilizará ese teléfono o computadora.
3. Abrí el evento y esperá unos segundos en el dashboard.
4. Confirmá que aparezca `En línea`.
5. Desde ese momento, el evento, precios, bebidas y listas disponibles quedan preparados en ese dispositivo.

Las colas pertenecen al usuario y al evento que estaban activos al momento de guardar la operación. Para sincronizarlas hay que volver a iniciar sesión con ese mismo usuario.

## Indicadores

La barra superior muestra:

- `En línea` o `Sin conexión`;
- cantidad de operaciones pendientes;
- cantidad de conflictos;
- botón `Sincronizar`.

La pantalla `/offline-operations` permite trabajar con el último evento guardado, revisar conflictos y borrar los datos locales del dispositivo.

## Conflictos posibles

Una operación queda en conflicto cuando, por ejemplo:

- otra caja ya confirmó el mismo nombre;
- el evento fue cerrado antes de sincronizar;
- se modificó o desactivó una bebida;
- el horario del beneficio ya había vencido;
- se intenta sincronizar con otro usuario.

Los conflictos no se suman a la caja. Quedan visibles en el dispositivo para poder revisarlos o descartarlos.

## Advertencia para el cierre

El administrador no debería cerrar la caja hasta que todos los dispositivos muestren `0 pendientes`. La web bloquea el cierre cuando **ese dispositivo** tiene operaciones locales pendientes, pero un servidor no puede conocer la cola de un celular que continúa completamente desconectado.

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
