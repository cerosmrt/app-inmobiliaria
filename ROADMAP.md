# ROADMAP — Moret Inmobiliaria

CRM inmobiliario (Flask + SQLAlchemy + Leaflet) para la inmobiliaria familiar.
En producción en `moretinmobiliaria.pythonanywhere.com`.

> **Forma de trabajo:** todo lo nuevo entra primero acá como **Pendiente**. Se avanza de a **una modificación por vez**, recapitulando con el usuario (multiple-choice) antes de tocar código. Al completar un ítem, se mueve a **Hecho**.

---

## ✅ Hecho

### Propiedades
- CRUD completo de propiedades con **soft-delete** (`deleted_at`) y archivado/restaurar/borrado permanente.
- Campos dinámicos según tipo de propiedad (urbano vs. **campo**: hectáreas, subdivisible, uso de suelo, nombre del campo).
- Estados (disponible/vendida/rentada/cerrada), operación (venta/alquiler), destacada y publicada.
- Edición **inline campo-por-campo** (click → input → PUT individual) con autosave en la descripción.
- Número de propiedad como link a su ficha.

### Fotos
- Upload con **validación por magic bytes**, conversión a **WebP**, generación de **thumbnails**, límite 10 MB.
- Reordenar por **drag & drop**; borrar; galería con **lightbox** (teclado + swipe táctil) en la ficha pública.

### Personas y comercial
- Clientes / **propietarios** / **interesados** (compradores) con relaciones M2M y **matching automático** propiedad↔interesado.
- **Consultas** del formulario público con notificación por email (SMTP en thread) y bandeja de no-leídas.
- **Captación**: pipeline de leads en frío (lead → propietario → actividades → convertir a cliente), import CSV.

### Geoespacial / catastro
- Mapeo de propiedades como **punto o polígono**; editor con **Leaflet.draw**, import **KML / GeoJSON / Shapefile**, cálculo de área con turf.
- **Catastro**: parcelas en DB, capa **ATER en vivo** (WFS por bbox + gating de zoom + debounce + caché 24h), integración **IGN** (provincias/departamentos) con fallback a estáticos locales.
- Mapa arranca centrado en **Gualeguay** (zoom 13); geocoding vía Nominatim.

### Plataforma
- Auth por sesión (hashing Werkzeug, **CSRF**, rate-limit de login, cookies seguras en prod), setup del primer admin.
- **Command palette** (Ctrl/Cmd+K), toasts, confirm modal, sidebar colapsable ("Portfolio / Inteligencia / Comunicación").
- Config por entorno (dev SQLite / prod Postgres), deploy en PythonAnywhere.

---

## 🔜 Pendiente (ordenado por prioridad / impacto)

### 🔴 Crítico — estabilidad y seguridad de producción
1. **Config peligrosa en prod.** Si falta `FLASK_ENV`, la app cae a `DevelopmentConfig` con `DEBUG=True` (`config.py:43`) → debugger de Werkzeug expuesto. Además `SECRET_KEY` es aleatoria por arranque si falta la env var (`config.py:6`) → con varios workers de gunicorn cada uno tiene su key y **el login se rompe**. *Por qué importa: es la diferencia entre un prod seguro y uno con la puerta abierta.* **← próxima modificación**
2. **Credenciales hardcodeadas** `roberto` / `moret2024` en `load_demo.py`. *Por qué importa: si el script corre en prod deja una cuenta con password conocida.*
3. **Doble sistema de esquema.** Alembic (`migrations/`) conviviendo con un bloque de `ALTER TABLE` crudos + `db.create_all()` en cada arranque (`app.py:1960-2012`), todo en `try/except: pass`. *Por qué importa: el esquema depende del orden de arranque, hay carreras entre workers y los errores se silencian. Requiere backup de la DB de prod antes de tocar.*
4. **Validación de entrada casi nula.** Endpoints de escritura acceden a `data['direccion']` directo → **KeyError 500**; `request.get_json()` sin guard. *Por qué importa: cualquier request mal formado tira 500 en vez de un 400 limpio.*
5. **Posible path traversal** al borrar fotos por `<path:filename>` sin validar que el path resuelto quede dentro de `static/uploads/` (`app.py:642`). *Por qué importa: un nombre con `../` podría borrar fuera de la carpeta.*

### 🟠 Alto — experiencia y performance
6. **Rediseño de la ficha de propiedad del ADMIN** (`templates/admin/propiedad.html`): arriba una **"vista cliente"** (galería + descripción + precio + specs, como la ve un visitante del front); debajo las **secciones privadas** de gestión (datos, fotos, geometría, propietarios, interesados, catastro, actividad). *Por qué importa: pedido explícito; es la pantalla que más usa el dueño.*
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
- **F1 · Instrumentar eventos de comportamiento + KPIs del funnel.** Cimiento de todo lo demás; hoy no se mide nada. *Por qué importa: sin datos, todo es opinión.*
- **A1 · Radar de captación catastral** (parcela → lead priorizado). *Por qué importa: genera inventario, el cuello de botella real; usa tu moat catastral.*
- **C1 · Descripciones de propiedad generadas por IA.** *Por qué importa: quick win de días; listings completos venden más.*
- **B1 · Buyer Intent Score** (priorizar leads por temperatura). *Por qué importa: más ventas por lead con el mismo esfuerzo.*
- **F2 · Búsqueda server-side + URLs por filtro + búsquedas guardadas.** *Por qué importa: escala el listado y hace la búsqueda compartible por WhatsApp.*
- **B2+D2 · Guardados + alertas de price-drop / "nuevo parecido".** *Por qué importa: convierte anónimos en leads y los reactiva sin pauta.*

Resto del backlog estratégico (rankeado 7-20): asistente IA para compradores, seller readiness score, dashboard de negocio, identidad ligera del visitante, AVM por comparables, copiloto del agente, calidad de fotos, feed personalizado, ficha PDF, agendar visita, oportunidades de tierra/subdivisión, auto-follow-up WhatsApp, detección de duplicados, comparador. → ver `VISION.md`.

### 🟢 Bajo — pulido
13. **Pinnear dependencias** (`requirements.txt` usa `>=` sin lock). *Por qué importa: reproducibilidad de builds.*
14. **Cachés geo in-memory sin límite** (`_GEO_CACHE`, `_ATER_CACHE`) → crecimiento ilimitado por bbox. *Por qué importa: fuga de memoria en workers de larga vida.*
15. **TLS sin verificar** hacia IGN/ATER (`_create_unverified_context`). *Por qué importa: MITM en las llamadas a servicios externos.*
16. **Eliminar `templates/perfil.html`** (huérfano, otro design system, ninguna ruta lo usa) y mover el CSS público inline a `public.css`. *Por qué importa: limpieza y evitar confusión.*
17. **Búsqueda geográfica** (geocoder en el mapa) y **caché de geocoding** para no arriesgar bloqueo de Nominatim. *Por qué importa: UX y evitar bans de IP.*
