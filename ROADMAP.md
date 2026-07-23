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

### Fotos
- Upload con **validación por magic bytes**, conversión a **WebP**, generación de **thumbnails**, límite 10 MB.
- Reordenar por **drag & drop**; borrar; galería con **lightbox** (teclado + swipe táctil) en la ficha pública.
- **El card del rail no pasa de una pantalla** (`max-height: calc(100vh - 95px)`, donde 95 = topbar 46+1 + los 24px de padding arriba y abajo del `.container`) y adentro la **galería es el único bloque elástico** (`flex: 0 1 auto` + scroll propio): crece lo que necesita y se achica cuando el card toca el techo. Antes crecía sin límite y con 10+ fotos el rail pasaba a ser la columna más alta y estiraba toda la página. *Un primer intento con `max-height: 480px` fijo no alcanzó — sumado al recuadro de subida y la descripción el rail seguía midiendo ~780px contra ~520px de la izquierda.* El rail sigue **sin** sticky a propósito (ver comentario en `propiedad.html:46`), así no vuelve el bug del scrollbar doble.

### Personas y comercial
- Clientes / **propietarios** / **interesados** (compradores) con relaciones M2M y **matching automático** propiedad↔interesado.
- **Crear al asignar, también desde el listado:** el modal de propietarios de la tabla de propiedades (`admin/index.html`) ofrece **"+ Crear «lo tipeado»"** con el mismo mini-form que la ficha (solo el nombre obligatorio) y asigna en el mismo paso, sin salir del modal.
- **El buscador de personas se abre con un botón** (`+ Agregar`, pegado al subtítulo *Propietarios (n)* / *Interesados (n)*) en vez de vivir siempre desplegado: la ficha se lee bastante más de lo que se edita y dos inputs vacíos permanentes ocupaban lugar sin dar nada. Escape lo cierra y limpia lo tipeado; al asignar se cierra solo. **Los matches automáticos salieron de la ficha**: sumaban un subtítulo más del lado de Interesados que del de Propietarios y dejaban la columna desbalanceada, casi siempre para mostrar un `(0)`. La sugerencia sigue viva en el listado de propiedades (`admin/index.html`), que es donde se usa, y el endpoint `/api/propiedades/<id>/matches` quedó intacto.
- **Typeahead para asignar personas** en la ficha admin (Propietarios e Interesados): en reposo no muestra nada — antes volcaba la lista completa de clientes debajo del input. Desde 2 letras aparecen hasta 6 coincidencias, con navegación por teclado (↓↑ / Enter / Esc), y ofrece **crear con lo tipeado** en un mini-form prellenado. **Solo el nombre es obligatorio**: `POST /api/clientes` acepta alta sin apellido ni teléfono (se guardan como `''`, sin migración) y devuelve 400 en vez de 500 si falta lo requerido.
- **Consultas** del formulario público con notificación por email (SMTP en thread) y bandeja de no-leídas.
- **Captación**: pipeline de leads en frío (lead → propietario → actividades → convertir a cliente), import CSV.

### Geoespacial / catastro
- Mapeo de propiedades como **punto o polígono**; editor con **Leaflet.draw**, import **KML / GeoJSON / Shapefile**, cálculo de área con turf.
- **Catastro**: parcelas en DB, capa **ATER en vivo** (WFS por bbox + gating de zoom + debounce + caché 24h), integración **IGN** (provincias/departamentos) con fallback a estáticos locales.
- Mapa arranca centrado en **Gualeguay** (zoom 13); geocoding vía Nominatim.

### Plataforma
- **Admin en sans (Inter)**: se sacó Lora del `<body>` de todo el panel — los remates ensucian labels chicos, mayúsculas e inputs, y el sidebar ya venía en sans. El sitio público no se tocó.
- **Controles de la ficha**: switches en vez de checkbox + "Sí"/"No" (redundante); moneda como selector ARS/USD sobre el mismo booleano `es_usd`; labels con `--text-2` en vez de `--muted` (2.7:1 → 4.9:1 de contraste, WCAG AA pide 4.5:1); miniaturas de fotos a 2 por fila.
- Auth por sesión (hashing Werkzeug, **CSRF**, rate-limit de login, cookies seguras en prod), setup del primer admin.
- **Command palette** (Ctrl/Cmd+K), toasts, confirm modal, sidebar colapsable ("Portfolio / Inteligencia / Comunicación").
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

6. ~~**Rediseño de la ficha de propiedad del ADMIN** — layout de dos columnas.~~ ✅ **Hecho.** *Ver detalle en Hecho › Propiedades.* Queda **pendiente aparte (a decidir):** si además va arriba una **"vista cliente"** (galería + descripción + precio como la ve un visitante del front).
7. **Performance del mapa de catastro.** Los **13.761 polígonos de Gualeguay** se cargan de golpe sin canvas/clustering/gating (`catastro.html:947`) → congela el navegador. Aplicar el mismo patrón que ATER (bbox + `preferCanvas` + gating de zoom). *Por qué importa: descongela la feature estrella.*
8. **`nearest` O(n) en Python** sin índice espacial (`app.py:1685`), ignorando el `neighbor_cache` que el modelo ya define. *Por qué importa: escala mal y se recalcula en cada apertura.*

### 🟡 Medio — deuda técnica y datos
9. **Normalizar `fotos`** (hoy CSV en un String) a una tabla `Foto` 1:N, y coords/bbox/neighbor_cache (hoy strings) a tipos reales. *Por qué importa: integridad referencial y menos parsing manual frágil.*
10. **Modelo de adjuntos** (planos, escrituras PDF) subibles desde el admin y descargables. *Por qué importa: valor real para una inmobiliaria; hoy solo hay fotos.*
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
