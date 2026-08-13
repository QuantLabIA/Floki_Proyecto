# Checklist v2.10.2 — Offline Aislado

1. Con internet, iniciar sesión y abrir Floki.
2. Confirmar que aparece `Modo offline 0` en la barra superior.
3. Entrar a `Modo offline` y esperar `MODO AISLADO LISTO`.
4. En iPhone/iPad, agregar esa pantalla a Inicio.
5. Activar modo avión.
6. Abrir el icono `Floki Offline` desde Inicio.
7. Registrar una entrada y una bebida. Debe mostrar 2 pendientes.
8. Cerrar y volver a abrir Floki Offline todavía sin internet. Los 2 pendientes deben seguir allí.
9. Reactivar internet y tocar `Actualizar / sincronizar`.
10. Debe quedar 0 pendientes y cada operación debe aparecer una sola vez en Floki online.
11. Abrir Dashboard, Ajustes, Historial y Cerrar caja: ninguno debe quedar controlado por el worker offline.
12. En DevTools/Application o diagnóstico, el único scope operativo debe ser `/offline-app/`.
