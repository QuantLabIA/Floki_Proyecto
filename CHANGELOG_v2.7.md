# Floki Manager v2.7.0 · Offline Seguro — Etapa 1

Esta versión parte de la v2.6.4 estable.

## Qué vuelve a estar disponible sin conexión
- Ventas rápidas de boletería mientras la pantalla ya está abierta.
- Guardarropa.
- Ventas rápidas de bebidas.
- Bebida especial.
- BENEFICIO RRPP.
- 50% OFF de cumpleaños.
- Confirmación FREE de personas de lista desde una pantalla ya cargada.

Las operaciones se guardan en IndexedDB con un identificador único y se sincronizan al recuperar conexión.

## Protección contra la pantalla blanca
- El Service Worker NO intercepta ni cachea páginas, login, dashboard, CSS ni JavaScript.
- Con internet, los formularios funcionan exactamente igual que en la v2.6.4: el módulo offline no los intercepta.
- `offline-sync.js` se carga 900 ms después del render y cualquier fallo queda aislado de la interfaz principal.
- Se eliminan cachés PWA experimentales anteriores.

## Alcance de Etapa 1
Para trabajar sin conexión es necesario haber abierto e iniciado sesión con internet y mantener esa pantalla/app abierta. Cerrar por completo la app y volver a abrirla sin internet quedará para una etapa posterior.

Siguen requiriendo internet: crear/cerrar/eliminar eventos, usuarios, configuración, precios, importaciones, exportaciones, stock final y anulaciones.
