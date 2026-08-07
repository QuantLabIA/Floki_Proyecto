# Floki Manager v2.6.1 · Hotfix pantalla blanca

- Login y HTML dinámico con `no-store`.
- El Service Worker deja de interceptar `/login` y `/logout`.
- CSS/JS críticos usan estrategia network-first y URLs versionadas.
- El login no inicializa IndexedDB ni el motor Offline First antes de autenticar.
- Se fuerza la actualización del Service Worker y se purgan caches anteriores.
- Se reducen efectos de blur costosos en el login para mejorar compatibilidad con equipos/GPU antiguos.
- PostgreSQL y la funcionalidad Offline First se mantienen.
