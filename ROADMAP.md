# ROADMAP — Moret Inmobiliaria

CRM inmobiliario (Flask + SQLAlchemy + Leaflet) para la inmobiliaria familiar.
En producción en `moretinmobiliaria.pythonanywhere.com`.

> **Forma de trabajo:** todo lo nuevo entra primero acá como **Pendiente**. Se avanza de a **una modificación por vez**, recapitulando con el usuario (multiple-choice) antes de tocar código. Al completar un ítem, se mueve a **Hecho**.

---

## ✅ Hecho

### Seguridad, datos e IA (reciente)
- **Config segura de prod:** `SECRET_KEY` obligatoria en producción (falla al arrancar si falta, no más clave efímera que rompe sesiones); warning si corre en DEBUG sin `FLASK_ENV`. Credenciales hardcodeadas de `load_demo.py` eliminadas.
- **Guards de entrada:** helpers `_json_body()`/`_missing()`; `add_propiedad` y `bulk-estado` devuelven 400 limpio en vez de 500.
- **F1 · Instrumentación de eventos:** modelo `Evento` + beacon público `/api/public/track` + `/api/stats/eventos` (funnel: visitantes únicos, vistas, contactos, tasas, top propiedades). Front público trackea view_ficha, contacto_wa/email, view_listado, buscar.
- **C1 · Descripciones con IA:** endpoint que genera descripciones vía API de Claude (degrada limpio sin key) + botón "✨ Generar con IA" en la ficha admin.


### Propiedades
- CRUD completo de propiedades con **soft-delete** (`deleted_at`) y archivado/restaurar/borrado permanente.
- Campos dinámicos según tipo de propiedad (urbano vs. **campo**: hectáreas, subdivisible, uso de suelo, nombre del campo).
- Estados (disponible/vendida/rentada/cerrada), operación (venta/alquiler), destacada y publicada.
- Edición **inline campo-por-campo** (click → input → PUT individual) con autosave en la descripción.
- Número de propiedad como link a su ficha.
- **Ficha admin en dos columnas** (`templates/admin/propiedad.html`), todo en una sola página sin tabs ni acordeones: izquierda datos + personas + descripción; derecha **rail pegajoso** con fotos y mapa, que queda a la vista mientras se scrollea. Ancho hasta 1500px (antes 1060). **Franja de cabecera** con precio / estado / tipo / operación en grande, editables inline igual que el resto. Colapsa a una columna por debajo de 1180px.
- **Densidad de la ficha admin:** los campos de Datos son **filas** (etiqueta y valor en la misma línea, sin recuadro) agrupadas en *Identificación · Dimensiones · Precio y publicación* (en Dimensiones, `Terreno m² | Cubierto m²` comparten la primera fila — son el mismo dato en dos versiones y se leen juntos — y `Ambientes` va debajo) — de ~56px a ~26px por campo. Propietarios e interesados viven en **un único card "Personas" a dos columnas** en vez de dos tarjetas apiladas. Los bloques vacíos no imprimen texto ni separador: alcanza con el `(0)` del subtítulo. Se eliminó el `<h1>` con la dirección, que duplicaba el breadcrumb del topbar (mismo dato, `propData.direccion`): ahora el breadcrumb **es** el `<h1>`. **Fotos y descripción comparten un card en el rail, sin títulos**: el recuadro de subida y el placeholder del textarea alcanzan como etiqueta. **El mapa salió del rail a un modal**, que se abre con el 📍 del campo Dirección (apagado si la propiedad no tiene ubicación marcada) — se inicializa recién al abrirlo, y es bastante más grande que antes (950×506 vs 470×330), lo que ayuda a dibujar polígonos. Con esto la ficha entra en una pantalla.

### Performance del admin
- **Las librerías del mapa se bajan recién al abrirlo.** La ficha traía Leaflet (144 KB), Leaflet.draw (66 KB), turf (528 KB), shpjs (228 KB) y togeojson como `<script>` bloqueantes en el `<head>`: casi **1 MB desde tres CDNs distintos**, medido en ~5 segundos, para un mapa que vive en un modal que casi nunca se abre — y si un CDN tardaba o lo frenaba un adblocker, la página no terminaba de cargar nunca. Ahora se cargan a demanda (en serie, porque `leaflet.draw` se registra sobre `L`), con la promesa cacheada y olvidada si falla para poder reintentar. La capa ESRI se arma adentro de `initGeoMap`: era una var de nivel superior y con las libs a demanda `L` todavía no existe cuando el script se parsea.
- **URL de togeojson arreglada:** `@mapbox/togeojson` ya no existe en npm (jsdelivr devolvía **404**), así que `toGeoJSON` quedaba `undefined` y el import de KML estaba muerto sin avisar. El paquete pasó a llamarse `@tmcw/togeojson`.

### Privado / público y adjuntos
- **🔴 Cerrada una fuga de datos personales en la API pública.** `GET /api/public/propiedades` devolvía `p.as_dict()` **entero** a cualquier visitante anónimo: nombre y **teléfono** de propietarios e interesados, más el código interno. Verificado contra la base real (dos propietarios con teléfono expuestos). Ahora las dos rutas públicas usan **`as_dict_publico()`**, con **lista blanca** de 24 campos — y no lista negra a propósito: con lista negra, cualquier columna interna que se agregue mañana a `as_dict()` saldría publicada sola. La suite fija que no viajen `propietarios`, `interesados`, `propietario_id`, `notas` ni `codigo`, y que sí sigan llegando los que el sitio necesita.
- **Notas internas por propiedad** (`Propiedad.notas`, migración `1a3f5a7bde4b`): textarea privada en la columna izquierda, separada de la descripción, que es el texto del aviso. **Desde ahí se adjuntan los archivos** (el botón vive en Notas, porque un archivo casi siempre llega con la nota que lo explica), y la lista de adjuntos se dibuja en su propio card, que **no aparece si no hay ninguno**.
- **La ficha admin se lee como "privado | público"** y lo dice escrito: la columna izquierda es 🔒 *Privado · sólo lo ve la inmobiliaria* (datos, personas, adjuntos) y la derecha 🌎 *Público · lo que ve el cliente* (fotos + descripción, que es exactamente lo que se publica). El **switch de publicar se mudó** del grupo *Precio y publicación* al rótulo de la columna pública, encima de lo que publica, y muestra el estado en palabras (*Publicada* / *Oculta*): un toggle solo no dice si "encendido" es publicado u oculto. Es el mismo campo `publicada` de siempre — no se inventó un flag nuevo.
- **Adjuntos privados** (`Adjunto` 1:N, migración `a1f4c8d92b07`): PDF, JPG, PNG o WebP subidos desde la ficha, con **visor inline** (los PDF en `<iframe>`, las imágenes en `<img>`) y descarga con el nombre original. Es lo que el padre hoy guarda en papel: planos, escrituras, mensuras.
  - **Nunca salen al sitio público, y eso está forzado por dónde viven:** el archivo se guarda en `private_uploads/adjuntos/`, **afuera de `static/`** — todo lo que cuelga de static lo sirve el servidor web directo, sin pasar por Flask y por lo tanto sin sesión. Se bajan sólo por `/adjuntos/<id>`, detrás de `@login_required` (no `api_`: lo abre el navegador, así que sin sesión tiene que mandar al login y no devolver un 401 en JSON).
  - Validación **por magic bytes** como las fotos: un `.pdf` que adentro es otra cosa no entra, y las extensiones fuera de la lista tampoco. La suite cubre las dos cosas, más que sin sesión el archivo no se sirve y que al borrarlo desaparece del disco.

### Fotos
- Upload con **validación por magic bytes**, conversión a **WebP**, generación de **thumbnails**, límite 10 MB.
- Reordenar por **drag & drop**; borrar; galería con **lightbox** (teclado + swipe táctil) en la ficha pública.
- **El card del rail no pasa de una pantalla** (`max-height: calc(100vh - 95px)`, donde 95 = topbar 46+1 + los 24px de padding arriba y abajo del `.container`) y adentro la **galería es el único bloque elástico** (`flex: 0 1 auto` + scroll propio): crece lo que necesita y se achica cuando el card toca el techo. Antes crecía sin límite y con 10+ fotos el rail pasaba a ser la columna más alta y estiraba toda la página. *Un primer intento con `max-height: 480px` fijo no alcanzó — sumado al recuadro de subida y la descripción el rail seguía midiendo ~780px contra ~520px de la izquierda.* El rail sigue **sin** sticky a propósito (ver comentario en `propiedad.html:46`), así no vuelve el bug del scrollbar doble.

### Personas y comercial
- Clientes / **propietarios** / **interesados** (compradores) con relaciones M2M y **matching automático** propiedad↔interesado.
- **Crear al asignar, también desde el listado:** el modal de propietarios de la tabla de propiedades (`admin/index.html`) ofrece **"+ Crear «lo tipeado»"** con el mismo mini-form que la ficha (solo el nombre obligatorio) y asigna en el mismo paso, sin salir del modal.
- **El buscador de personas se abre con un botón** (`+ Agregar`, pegado al subtítulo *Propietarios (n)* / *Interesados (n)*) en vez de vivir siempre desplegado: la ficha se lee bastante más de lo que se edita y dos inputs vacíos permanentes ocupaban lugar sin dar nada. Escape lo cierra y limpia lo tipeado; al asignar se cierra solo. **Los matches automáticos salieron de la ficha**: sumaban un subtítulo más del lado de Interesados que del de Propietarios y dejaban la columna desbalanceada, casi siempre para mostrar un `(0)`. La sugerencia sigue viva en el listado de propiedades (`admin/index.html`), que es donde se usa, y el endpoint `/api/propiedades/<id>/matches` quedó intacto.
- **Typeahead para asignar personas** en la ficha admin (Propietarios e Interesados): en reposo no muestra nada — antes volcaba la lista completa de clientes debajo del input. Desde 2 letras aparecen hasta 6 coincidencias, con navegación por teclado (↓↑ / Enter / Esc), y ofrece **crear con lo tipeado** en un mini-form prellenado. **Solo el nombre es obligatorio**: `POST /api/clientes` acepta alta sin apellido ni teléfono (se guardan como `''`, sin migración) y devuelve 400 en vez de 500 si falta lo requerido.
- **Impresión de listados unificada:** un solo botón *Imprimir* (el del header, `window.print()` con `@media print`); se sacaron los botones *Imprimir* redundantes de cada pestaña (Interesados/Propietarios/Propiedades) y la función `imprimirTabla`. En papel la columna *Teléfono* muestra el **número real** (span `.tel-print`) en vez del ícono de WhatsApp, que solo sirve clickeable en pantalla.
- **Consultas** del formulario público con notificación por email (SMTP en thread) y bandeja de no-leídas.
- **Captación**: pipeline de leads en frío (lead → propietario → actividades → convertir a cliente), import CSV.

### Geoespacial / catastro
- Mapeo de propiedades como **punto o polígono**; editor con **Leaflet.draw**, import **KML / GeoJSON / Shapefile**, cálculo de área con turf.
- **Catastro**: parcelas en DB, capa **ATER en vivo** (WFS por bbox + gating de zoom + debounce + caché 24h), integración **IGN** (provincias/departamentos) con fallback a estáticos locales.
- Mapa arranca centrado en **Gualeguay** (zoom 13); geocoding vía Nominatim.

### Sitio público
- **Sin alquileres.** La inmobiliaria hoy solo opera venta: se sacó la solapa *En Alquiler*, y un `?tab=alquiler` viejo (link guardado, buscador) cae en *Todas* en vez de filtrar por una operación que ya no se ofrece y devolver una grilla vacía. También salió de `<title>`, meta description, OG y hero. El valor `alquiler` sigue existiendo en el modelo y en el admin: se sacó de la oferta, no de los datos.
- **Sin búsqueda por barrio ni dirección.** Gualeguay es chica y nadie busca así; quedan tipo, ambientes y precio. La API sigue aceptando `barrio` por si alguna vez vuelve.
- **Fotos de las cards con las cuatro esquinas redondeadas** (van metidas adentro de la card, con margen y radio concéntricos) — antes cortaban en escuadra contra el cuerpo blanco.
- **Carrusel: un dot por foto.** Se dibujaban 5 como máximo mientras las flechas recorrían todas, así que en una propiedad con 8 fotos los pasos 6 a 8 no encendían ningún dot y parecía que se quedaba clavado en la misma foto. Pasadas 8 fotos va un contador `n / total` en vez de la fila de puntitos. Además el swipe táctil ahora corta la propagación: en el celular pasar de foto abría la ficha.

### Plataforma
- **Admin en sans (Inter)**: se sacó Lora del `<body>` de todo el panel — los remates ensucian labels chicos, mayúsculas e inputs, y el sidebar ya venía en sans. El sitio público no se tocó.
- **Controles de la ficha**: switches en vez de checkbox + "Sí"/"No" (redundante); moneda como selector ARS/USD sobre el mismo booleano `es_usd`; labels con `--text-2` en vez de `--muted` (2.7:1 → 4.9:1 de contraste, WCAG AA pide 4.5:1); miniaturas de fotos a 2 por fila.
- Auth por sesión (hashing Werkzeug, **CSRF**, rate-limit de login, cookies seguras en prod), setup del primer admin.
- **Command palette** (Ctrl/Cmd+K), toasts, confirm modal, sidebar colapsable ("Portfolio / Inteligencia / Comunicación").
- **El panel abre en Propiedades**, no en Interesados: es el portfolio, lo que se mira todos los días; Interesados se consulta cuando hay una consulta concreta puntual. El default vivía repetido en dos lugares que estaban desalineados (`admin/index.html` decía `interesados`, `admin/base.html` decía `clientes` — que ni siquiera es una pestaña, así que el sidebar no marcaba nada activo al entrar sin `?tab=`); ahora los dos dicen `propiedades`.
- Config por entorno (dev SQLite / prod Postgres), deploy en PythonAnywhere.

---

## 🔜 Pendiente (ordenado por prioridad / impacto)

### 🔴 Crítico — estabilidad y seguridad de producción
1. ~~Config peligrosa en prod (SECRET_KEY efímera / DEBUG por defecto).~~ ✅ **Hecho.** *Nota de deploy: asegurarse de que PythonAnywhere tenga `FLASK_ENV=production` y `SECRET_KEY` seteadas en el WSGI/panel.*
2. ~~Credenciales hardcodeadas en `load_demo.py`.~~ ✅ **Hecho.**
3. **Doble sistema de esquema.** Alembic (`migrations/`) conviviendo con un bloque de `ALTER TABLE` crudos + `db.create_all()` en cada arranque (`app.py:1960-2012`), todo en `try/except: pass`. *Por qué importa: el esquema depende del orden de arranque, hay carreras entre workers y los errores se silencian. Requiere backup de la DB de prod antes de tocar.*
4. **Validación de entrada — parcial.** ✅ Guards aplicados a `add_propiedad`, `bulk-estado` y `add_cliente`. Falta extender el patrón `_json_body()`/`_missing()` al resto de endpoints de escritura (edición de clientes, captación, catastro). *Por qué importa: todavía quedan rutas que pueden tirar 500 por body ausente.*
5. **Posible path traversal** al borrar fotos por `<path:filename>` sin validar que el path resuelto quede dentro de `static/uploads/` (`app.py:642`). *Por qué importa: un nombre con `../` podría borrar fuera de la carpeta.*

### 🔵 Del assessment del 22/07/2026 — para revisar juntos (NO tocado)

> Barrido de las 6 pantallas del admin. Lo que era **bug** ya está arreglado y commiteado; esto es lo que quedó porque es decisión de diseño o de negocio.
>
> **Confirmado que NO son problemas** (medido, no supuesto): cero errores JS en las 9 vistas; cero 500 en 50 combinaciones de endpoint/body; y **cero XSS en el admin** — se inyectaron 30 payloads en campos de la DB y los 30 salieron escapados. (El XSS que sí existía era en el **sitio público** y ya está arreglado.)

**a. Accesibilidad — 24 inputs sin nombre accesible.** `captacion.html` (10), `index.html` (7), `catastro.html` (6), `consultas.html` (1). Casi todos se construyen por JS con `id` pero sin `<label for>` ni `aria-label`. *Por qué importa: un lector de pantalla los anuncia como "edición, en blanco".* Los del login y la ficha ya se arreglaron.

**b. Contraste en estados de hover.** `--muted` sobre `--surface-2` (4.29:1) y `--surface-3` (3.99:1) queda en AA-grande, no AA. Igual `--text-2` sobre `--surface-3` (4.24:1). *Por qué importa: es texto chico en hover; se arregla oscureciendo un punto más los grises o aclarando los fondos de hover.*

**c. Revisar el cambio de `--muted` en las 6 pantallas.** Pasó de `#9B9A97` a `#737270` por accesibilidad. Es más oscuro y se nota en labels, hints y placeholders de todo el admin. *Por qué importa: puede pedir reequilibrio visual en pantallas que no miramos (catastro, captación).*

**d. Endpoints que aceptan crear registros vacíos.** `POST /api/catastro/parcelas` devuelve **201** con body `{}`, y lo mismo `investigaciones`, `propietarios` y `layers/register`. *Por qué importa: se llena la base de registros fantasma. No lo toqué porque "qué campo es obligatorio" es una regla tuya, no técnica.*

**e. `PATCH /api/propiedades/bulk-estado` quedó sin llamador.** Se borró la UI de selección masiva (era código muerto), pero el endpoint sigue vivo. *Decidir: se recupera la feature o se borra la ruta.*

**f. La columna izquierda de la ficha queda más corta que el rail.** Con Datos + Personas termina a media altura y abajo queda un hueco blanco, mientras el rail sigue hasta el final de las fotos. *Opciones: mover algo a la izquierda, o angostar el rail.*

**g. `audit_test.py` no se puede correr.** Necesita `requests` (no está en el venv), un servidor en `:5000` y credenciales reales. Quedó desactualizado respecto del UI nuevo salvo las assertions que reescribí. *Decidir: se migra a `test_regresion.py` (que corre offline) o se instala `requests` y se mantienen los dos.*

**h. Sigue abierto del rediseño:** si arriba de la ficha va una **"vista cliente"** (galería + descripción + precio como la ve un visitante), que era la forma original del ítem 6.

### 🟠 Alto — experiencia y performance

6g. **Identidad visual alineada al logo** *(decidido el 23/07/2026)*. El logo es serif pesada + sans geométrica + rojo pleno sobre negro. Decisiones tomadas:
   - **Serif sólo en títulos del portal público** (logo, direcciones de propiedad, H1/H2) y **sans en todo lo demás**, incluido el admin entero. *Esto revierte el "pasar el público a sans también" decidido un rato antes el mismo día.*
   - **Paleta del admin de cálida a gris frío** (`#F8F9FA` / `#F1F3F5` / bordes `#E5E7EB`, texto `#333` / `#666`).
   - **Rojo de acento: muestreado del logo** — pendiente de que `static/logo.png` exista. **Hoy el archivo no está**: `index.html:415` lo referencia con un `onerror` que lo esconde, así que el sitio muestra un fallback de texto y el logo real nunca se vio.
   - **`.btn-ver` negro sólido** (`#111` con texto blanco), no rojo: en la misma card ya hay un badge rojo de VENTA sobre la foto, y el propio spec pide no saturar de rojo.
   - *Ojo con el spec de origen: recomienda Playfair Display / Bodoni, que son didonas de alto contraste, mientras la serif del logo es pesada y de bajo contraste (slab). De su lista, Merriweather es la única que se acerca. Y dice que el sidebar es `#111111` cuando en realidad es `#000000`.*

6c. **Galería de fotos en 2×2 + modal de gestión.** *(decidido el 23/07/2026, revierte parte de lo hecho ese mismo día)* En el rail se ven **4 miniaturas (2×2)** y la cuarta lleva el contador **«+N»**; el manejo real —reordenar por drag & drop, subir y borrar— se muda a un **modal grande**, que da mucho más lugar para arrastrar. Reemplaza el scroll interno con techo elástico que quedó hoy. *Costo: agrega un clic para cualquier cambio en las fotos. Ojo: el techo del rail (`100vh - 95px`) sigue haciendo falta para el resto del card.*


6e. **Captación como canvas de nodos — etapa 1: visualización.** *(decidido: las dos etapas, pero primero esta)* Cada lead es un nodo en un lienzo libre con zoom, pan y minimapa, arrastrable entre etapas; es el Kanban actual en otro formato, apoyado en datos que ya existen (`CaptacionLead.estado`, propietario, potencial, días en etapa). Se suma como una vista más al conmutador que ya está (`setView()`: Kanban / Lista / Seguimientos). **Sin React ni build step**: SVG + JS vanilla, o una librería que cargue por CDN (Drawflow / jsPlumb). *Descartado React Flow a propósito: exige React + bundler, y el deploy en PythonAnywhere es `git pull` + Reload, sin build.*

6f. **Captación — etapa 2: motor de automatizaciones.** *(sólo después de 6e, y es un proyecto aparte, no una pantalla)* Diseñar flujos que los leads recorran solos: nodos de condición («¿respondió en 48hs?»), de acción («investigar dueño», «asignar agente») y de salida. **Requiere** motor de ejecución en el backend, scheduler (hoy no hay ninguno) y, para el auto-WhatsApp, la **API de WhatsApp Business** — con un link `wa.me` no se puede mandar solo. *Por qué importa: es la diferencia entre dibujar el flujo y que el flujo funcione.*

6. ~~**Rediseño de la ficha de propiedad del ADMIN** — layout de dos columnas.~~ ✅ **Hecho.** *Ver detalle en Hecho › Propiedades.* Queda **pendiente aparte (a decidir):** si además va arriba una **"vista cliente"** (galería + descripción + precio como la ve un visitante del front).
7. **Performance del mapa de catastro.** Los **13.761 polígonos de Gualeguay** se cargan de golpe sin canvas/clustering/gating (`catastro.html:947`) → congela el navegador. Aplicar el mismo patrón que ATER (bbox + `preferCanvas` + gating de zoom). *Por qué importa: descongela la feature estrella.*
8. **`nearest` O(n) en Python** sin índice espacial (`app.py:1685`), ignorando el `neighbor_cache` que el modelo ya define. *Por qué importa: escala mal y se recalcula en cada apertura.*

### 🟡 Medio — deuda técnica y datos
9. **Normalizar `fotos`** (hoy CSV en un String) a una tabla `Foto` 1:N, y coords/bbox/neighbor_cache (hoy strings) a tipos reales. *Por qué importa: integridad referencial y menos parsing manual frágil.*
10. **Fotos privadas de a una.** Hoy las fotos son públicas por definición (lo que no se publica va como adjunto). Para poder marcar una foto suelta como privada —el contrafrente feo, un plano escaneado— primero hay que **normalizar `fotos`** (pendiente 9): con el CSV en un String no hay dónde colgarle el flag. *Por qué importa: es la única parte del modelo privado/público que quedó afuera.*
11. **Modularizar `app.py`** (2015 líneas, ~110 rutas) en blueprints (público / propiedades / clientes / consultas / captación / catastro). *Por qué importa: sostenibilidad; hoy todo cuelga de un archivo.*
12. **Vincular propiedad ↔ parcela catastral** (FK) para surfacear cédula/partida en la ficha. *Por qué importa: hoy son entidades paralelas sin relación.*

### 🚀 Estratégico — Inteligencia inmobiliaria (visión de producto)

> Detalle completo, con framework de 7 puntos por feature, KPIs y Top 20 rankeado, en **`VISION.md`**.
> Tesis: no copiar a Zillow — ganar con lo que es único de Gualeguay (catastro ATER + dueños, WhatsApp nativo, campos rurales). Las "features de IA" se hacen llamando a la API de Claude, no entrenando modelos.

Los 6 primeros por impacto/esfuerzo (arrancar por acá):
- ~~F1 · Instrumentar eventos + KPIs del funnel.~~ ✅ **Hecho** (base). Falta el **dashboard visual** en el admin que consuma `/api/stats/eventos` (E3).
- **A1 · Radar de captación catastral** (parcela → lead priorizado). *Por qué importa: genera inventario, el cuello de botella real; usa tu moat catastral.*
- ~~C1 · Descripciones de propiedad generadas por IA.~~ ✅ **Hecho.** Requiere setear `ANTHROPIC_API_KEY` para activarse.
- **B1 · Buyer Intent Score** (priorizar leads por temperatura). *Por qué importa: más ventas por lead con el mismo esfuerzo — ahora es posible porque ya se registran eventos.*
- **F2 · Búsqueda server-side + URLs por filtro + búsquedas guardadas.** *Por qué importa: escala el listado y hace la búsqueda compartible por WhatsApp.*
- **B2+D2 · Guardados + alertas de price-drop / "nuevo parecido".** *Por qué importa: convierte anónimos en leads y los reactiva sin pauta.*

Resto del backlog estratégico (rankeado 7-20): asistente IA para compradores, seller readiness score, dashboard de negocio, identidad ligera del visitante, AVM por comparables, copiloto del agente, calidad de fotos, feed personalizado, ficha PDF, agendar visita, oportunidades de tierra/subdivisión, auto-follow-up WhatsApp, detección de duplicados, comparador. → ver `VISION.md`.

### 🟢 Bajo — pulido
13. **Pinnear dependencias** (`requirements.txt` usa `>=` sin lock). *Por qué importa: reproducibilidad de builds.*
14. **Cachés geo in-memory sin límite** (`_GEO_CACHE`, `_ATER_CACHE`) → crecimiento ilimitado por bbox. *Por qué importa: fuga de memoria en workers de larga vida.*
15. **TLS sin verificar** hacia IGN/ATER (`_create_unverified_context`). *Por qué importa: MITM en las llamadas a servicios externos.*
16. **Eliminar `templates/perfil.html`** (huérfano, otro design system, ninguna ruta lo usa) y mover el CSS público inline a `public.css`. *Por qué importa: limpieza y evitar confusión.*
17. **Búsqueda geográfica** (geocoder en el mapa) y **caché de geocoding** para no arriesgar bloqueo de Nominatim. *Por qué importa: UX y evitar bans de IP.*
