# Recuperación de pantalla blanca

1. Publicá v2.6.3 en el mismo servicio Railway. No borres PostgreSQL.
2. Esperá a que el deployment quede ACTIVE.
3. Abrí `/health`: debe decir 2.6.3 + postgresql.
4. Abrí la URL principal y volvé a iniciar sesión.
5. Si el dashboard no carga, abrí `/diagnostic` en la misma sesión.
   - Si `/diagnostic` devuelve status=ok, el backend y PostgreSQL están bien.
   - Si devuelve status=error, el JSON indica exactamente la consulta que falló.
6. Offline First queda temporalmente desactivado para priorizar estabilidad.
