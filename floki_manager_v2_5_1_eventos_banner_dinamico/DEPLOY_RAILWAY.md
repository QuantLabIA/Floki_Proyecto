# Publicar Floki Manager en Railway

## Resultado

Al terminar vas a tener una dirección parecida a:

```text
https://floki-manager-production.up.railway.app
```

La aplicación quedará disponible desde celular, tablet y computadora sin dejar una PC encendida.

## 1. Subir el proyecto a GitHub

Subí **el contenido de esta carpeta** a un repositorio privado. No subas:

- `.env`
- `.venv`
- `data/floki.db` si contiene información real
- archivos de `backups/`

El `.gitignore` ya excluye esos elementos.

## 2. Crear el proyecto

1. Entrá a Railway.
2. Creá un proyecto nuevo.
3. Elegí desplegar desde tu repositorio de GitHub.
4. Autorizá el repositorio privado cuando Railway lo solicite.

Railway leerá `railway.json`, instalará `requirements.txt` y arrancará Gunicorn.

## 3. Agregar PostgreSQL

Dentro del mismo proyecto:

1. Seleccioná `+ New`.
2. Elegí `Database`.
3. Elegí `PostgreSQL`.

## 4. Configurar variables

En el servicio de Floki Manager agregá:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
FLOKI_ENV=production
FLOKI_SECURE_COOKIES=1
FLOKI_SECRET_KEY=UNA_CLAVE_LARGA_Y_ALEATORIA
```

Para generar la clave:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

No uses la clave de ejemplo incluida en el proyecto.

## 5. Generar la URL

En Networking/Public Networking elegí `Generate Domain`.

Cuando tengas la URL, agregá otra variable:

```text
FLOKI_PUBLIC_URL=https://TU-DOMINIO-DE-RAILWAY
```

No coloques `/` al final. Esta variable se utiliza para generar correctamente los QR de promotores.

## 6. Verificar el despliegue

Abrí:

```text
https://TU-DOMINIO/health
```

El resultado correcto es parecido a:

```json
{"status":"ok","version":"2.5.1","database":"postgresql"}
```

Después abrí la URL principal e ingresá con el administrador.

## 7. Seguridad inicial

Antes del primer evento:

1. Cambiá las contraseñas de administrador, boletería y bebidas.
2. Creá un evento de prueba.
3. Registrá una entrada y una bebida.
4. Abrí la aplicación en dos celulares al mismo tiempo.
5. Verificá que ambos vean la misma información.
6. Cerrá y eliminá el evento de prueba.

## 8. Instalar como aplicación

### iPhone

1. Abrí la URL con Safari.
2. Tocá Compartir.
3. Elegí `Agregar a pantalla de inicio`.

### Android

1. Abrí la URL con Chrome.
2. Tocá `Instalar app` dentro de Floki Manager o la opción del menú del navegador.

## Migrar una SQLite existente

Solo hace falta si ya utilizaste Floki Manager y querés conservar datos.

1. Obtené una URL pública de conexión a PostgreSQL desde Railway.
2. En tu computadora instalá dependencias:

```bash
python -m pip install -r requirements.txt
```

3. Ejecutá:

```bash
python migrate_sqlite_to_postgres.py \
  --sqlite data/floki.db \
  --database-url "URL_POSTGRES_PUBLICA" \
  --replace
```

4. Reiniciá el despliegue y comprobá el historial.

**Advertencia:** `--replace` borra el contenido anterior del PostgreSQL destino antes de copiar SQLite.

## Límites de esta subfase

- Necesita internet para registrar movimientos.
- Si el indicador muestra `Sin conexión`, no se deben confirmar ventas ni ingresos.
- El modo offline con cola local y sincronización será una fase posterior, una vez validado el uso simultáneo en la nube.
