# Floki Manager v2.10.7 — Online Estable · Offline eliminado

## Decisión de arquitectura
Floki Manager vuelve a funcionar exclusivamente con conexión a Internet. Se elimina el modo Offline/Offline Aislado para priorizar estabilidad operativa en iPhone, iPad y navegador.

## Cambios
- Se elimina el acceso **Modo offline** de la interfaz.
- Se elimina el panel Offline de Ajustes.
- Se eliminan `/offline-app/`, `/floki-offline/`, APIs de bootstrap/sincronización offline y sus assets.
- Se eliminan IndexedDB/cola offline del frontend: la aplicación ya no crea ni usa operaciones locales.
- Las ventas, bebidas, listas, gastos, stock y cierres vuelven a registrarse únicamente contra el servidor/PostgreSQL.
- Se conserva `/pwa-reset` solo como herramienta de limpieza de Service Workers y cachés heredadas de versiones anteriores.
- La app normal intenta desregistrar silenciosamente cualquier Service Worker viejo al cargar y borrar sus cachés, sin borrar IndexedDB legado.
- `diagnostic` informa `offline_mode: removed` y `connection_mode: online_only`.

## Importante después del deploy
Abrir una vez `/pwa-reset` en cada iPhone/iPad que haya probado el modo offline. Luego volver a iniciar Floki normalmente.
