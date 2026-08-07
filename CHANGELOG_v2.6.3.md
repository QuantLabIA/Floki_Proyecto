# Floki Manager v2.6.3 · Stable Recovery

- Mantiene PostgreSQL, usuarios, eventos, listas, bebidas, stock y banner dinámico.
- Retira temporalmente Offline First y la interceptación del Service Worker.
- Elimina automáticamente cachés Floki antiguas al cargar la web.
- Agrega `/diagnostic` para comprobar sesión y consultas principales.
- Agrega un error 500 visible e independiente del diseño para evitar pantallas blancas silenciosas.
- Agrega `X-Floki-Version` a las respuestas.

Una vez validada la estabilidad online, Offline First se reconstruirá sobre esta base en una versión posterior.
