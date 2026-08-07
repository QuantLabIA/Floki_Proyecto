# Floki Manager v2.6.2 · Compatibilidad visual post-login

- Corrige la pantalla blanca que podía aparecer después de iniciar sesión en equipos o GPU antiguos.
- Elimina `backdrop-filter`, máscaras y luces difuminadas pesadas de las pantallas internas, conservando negro + violeta Minimal Luxe.
- El módulo Offline First se carga 450 ms después del render principal para que nunca bloquee el dashboard.
- Actualiza la caché PWA a `floki-manager-v2-6-2-render-safe`.
- Las navegaciones ya no dependen de la pantalla operativa offline precargada.
- Mantiene PostgreSQL, Offline First y toda la lógica de v2.6.1.
