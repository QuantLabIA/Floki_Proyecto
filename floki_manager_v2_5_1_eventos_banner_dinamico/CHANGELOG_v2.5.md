# Floki Manager v2.5

## Producción y nube

- Compatibilidad dual SQLite/PostgreSQL.
- Configuración para Railway mediante `railway.json`.
- Gunicorn como servidor WSGI de producción.
- Endpoint `/health` con verificación de base.
- Soporte para URL pública detrás de proxy HTTPS.
- Script para migrar SQLite a PostgreSQL.

## PWA

- Manifest ampliado con nombre, alcance, íconos y accesos rápidos.
- Botón para instalar la aplicación.
- Instrucción específica para iPhone.
- Estado visible En línea/Sin conexión.
- Service worker con caché de recursos estáticos.
- Datos privados y páginas de caja excluidos de la caché.

## Seguridad

- Cookies seguras en producción.
- Sesiones de 12 horas.
- Cabeceras de seguridad básicas.
- Caché privada deshabilitada en páginas operativas.
- Aumento controlado del límite de archivos a 8 MB.

## Importante

Esta versión no registra movimientos offline. El modo sin conexión muestra una pantalla segura y mantiene la interfaz instalable, pero las operaciones requieren conexión con PostgreSQL.
