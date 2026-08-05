# Prompt para Google Stitch - Floki Manager

Diseñá una aplicación web responsive y mobile-first llamada **Floki Manager**, destinada a administrar un boliche nocturno. Usá el logo blanco de Floki Club que voy a adjuntar como identidad principal. El resultado debe sentirse premium, moderno y muy rápido de usar en celular, tablet y computadora.

## Dirección visual elegida

Estilo **Floki Minimal Luxe**: fondo negro profundo, violeta flúor, blanco y grises oscuros. Usar glassmorphism sutil, desenfoques tipo iPhone, tarjetas translúcidas, bordes redondeados, sombras suaves y glow violeta solamente en acciones activas o importantes. Evitar una estética recargada. La interfaz debe ser elegante, nocturna y legible en ambientes oscuros.

Paleta sugerida:
- Fondo principal: `#050407`
- Superficie/tarjetas: `#111016` con transparencia
- Violeta principal: `#A84CFF`
- Violeta intenso: `#B026FF`
- Texto principal: `#F7F4FA`
- Texto secundario: `#AAA2B3`
- Éxito: `#38D27A`
- Error: `#FF5C72`

Tipografía: **Inter**, **Sora** o similar, con números grandes y muy legibles.

## Roles y privacidad

La aplicación tiene tres accesos:
1. **Administrador - Pablo**: ve ganancias, historial financiero, eventos, configuración, usuarios, stock, reportes y exportaciones.
2. **Caja de boletería - nombre modificable**: vende entradas generales, confirma personas de listas RRPP, registra guardarropa y no ve ganancias.
3. **Caja de bebidas - nombre modificable**: vende bebidas, registra BENEFICIO RRPP y BEBIDA ESPECIAL, pero no ve el control parcial de ventas ni ganancias.

## Pantallas a diseñar

### 1. Login
- Logo Floki grande.
- Fondo de boliche oscuro con luces violetas difuminadas.
- Campos Usuario y Contraseña.
- Botón principal `INICIAR SESIÓN`.
- Tarjeta central translúcida con blur.

### 2. Dashboard administrador
- Encabezado con logo, evento activo, fecha y `Administrador - Pablo`.
- Tarjetas: Caja actual, Personas ingresadas, Boletería, Bebidas y Guardarropa.
- Accesos a Eventos, Listas RRPP, Stock, Historial y Configuración.
- Los importes y ganancias solo aparecen para administrador.

### 3. Caja de boletería
- Botones táctiles grandes: `ENTRADA GENERAL`, `LISTAS RRPP` y `GUARDARROPA`.
- No mostrar VIP ni Anticipada.
- No incluir botón FREE manual. La entrada FREE solo se confirma buscando una persona previamente cargada en listas.
- Buscador predictivo de nombres que indique en qué lista aparece cada persona.
- Una persona no puede ingresar dos veces.
- Todas las listas son válidas para FREE hasta las 03:30; luego mostrar estado bloqueado.
- Mostrar el precio vigente de la entrada según horario, sin obligar al cajero a escribir montos.

### 4. Listas RRPP
- Bloc de notas para pegar mensajes de WhatsApp/WPS y convertirlos automáticamente.
- Promotores escritos en mayúsculas; los nombres debajo se asignan a ese promotor.
- Mensajes sin promotor van a Lista común. Los encabezados PROMO/PROMOS forman una lista automática PROMOS sin QR.
- Búsqueda predictiva y confirmación de ingreso.
- Botón único `EXPORTAR PDF POR PROMOTOR`.
- En el PDF: promotores ordenados alfabéticamente; personas A-Z dentro de cada promotor; PROMOS después de los promotores; Lista común siempre como último bloque.
- QR distinto por promotor, renovado al cerrar el evento. PROMOS y Lista común no tienen QR.

### 5. Caja de bebidas
- Catálogo visual en grilla.
- Cada bebida debe mostrar tipo, marca, presentación y precio. Ejemplos: `Cerveza Quilmes - Lata 473 ml`, `Cerveza Quilmes - Vaso`, `Cerveza Heineken - Botella 330 ml`.
- Variantes de una misma bebida deben ser botones separados con precios diferentes.
- Acciones superiores: `BENEFICIO RRPP` y `BEBIDA ESPECIAL`.
- BENEFICIO RRPP no pide promotor, no suma dinero y descuenta stock.
- BEBIDA ESPECIAL pide precio y comentario obligatorio.
- El cajero no ve totales parciales ni rendimiento.

### 6. Stock administrador
- Tabla por evento con: Bebida, unidad de stock, unidad de venta, cantidad inicial, venta normal, venta especial, beneficio RRPP, total vendido, cantidad final, stock utilizado y rendimiento real del evento.
- El rendimiento se calcula al cierre con stock inicial, stock final y unidades vendidas; no mostrar promedio histórico.
- Excel solo con bebidas activas configuradas en el sector Bebidas.

### 7. Eventos
- Creación mediante calendario.
- Nombre del evento.
- Monto inicial opcional.
- Capacidad opcional.
- Posibilidad de borrar eventos cerrados solo para administrador.
- Al cerrar el evento: eliminar nombres de listas, renovar QR y conservar estadísticas, movimientos y stock.

## Navegación y responsive

- En escritorio: barra lateral o superior discreta.
- En celular: navegación inferior fija tipo iPhone.
- Botones mínimos de 48 px de alto, aptos para tocar rápido.
- Modales simples y formularios de una sola columna en móvil.
- Mantener contraste alto y evitar textos pequeños.

## Resultado esperado

Generá pantallas coherentes entre sí, componentes reutilizables y un sistema visual completo. Priorizar rapidez operativa, claridad y estética premium de boliche. No agregar funciones no mencionadas como cuentas de clientes, DNI obligatorio, ticket promedio, mesas o reservas.
