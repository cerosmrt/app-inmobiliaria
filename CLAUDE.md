# CLAUDE.md — Moret Inmobiliaria

Contexto para cualquier sesión de Claude Code que trabaje en este proyecto. Leer antes de tocar código.

## Qué es
CRM inmobiliario para la inmobiliaria familiar (Moret, Gualeguay, Entre Ríos). Reemplaza una carpeta impresa de propiedades. Tiene un **sitio público** (de cara al cliente) y un **back-office admin** para gestionar propiedades, personas, consultas, captación de leads y catastro geoespacial. UI en **español**. En producción en `moretinmobiliaria.pythonanywhere.com`.

## Cómo trabajar en este proyecto (regla de colaboración — IMPORTANTE)
- **Una modificación por vez.** No avanzar en varias cosas juntas ni en batch.
- **Antes de tocar código, recapitular el cambio con el usuario mediante preguntas multiple-choice** (herramienta AskUserQuestion) hasta confirmar que ambos están en la misma página.
- **Todo lo nuevo entra primero como "Pendiente" en `ROADMAP.md`.** Al completar un ítem, moverlo a "Hecho".
- No asumir intención: si hay ambigüedad de alcance, preguntar antes.

## Stack
- **Backend:** Flask 3 + Flask-SQLAlchemy 3.1 + Flask-Migrate/Alembic.
- **DB:** SQLite en dev (`instance/inmobiliaria.db`), Postgres en prod (vía `DATABASE_URL`).
- **Frontend:** Jinja2 + **JS vanilla, sin build step ni framework**. Las páginas llegan casi vacías y se rellenan con `fetch` a APIs JSON.
- **Mapas:** Leaflet 1.9.4 vía CDN (+ Leaflet.draw, togeojson, turf, shpjs donde aplica).
- **Imágenes:** Pillow (WebP + thumbnails).
- **Prod:** gunicorn (Procfile, estilo Railway) — pero el deploy real es **PythonAnywhere** (WSGI propio).

## Estructura
```
app.py                  Monolito: ~110 rutas, toda la lógica (2000+ líneas, sin blueprints)
models.py               13 modelos SQLAlchemy + 3 tablas M2M
config.py               DevelopmentConfig / ProductionConfig
manage.py               Wrapper casero de Flask-Migrate (init/migrate/upgrade)
migrations/             Alembic
load_demo.py            Seed de datos demo
templates/
  index.html            Landing pública + listado
  propiedad.html        Ficha PÚBLICA de propiedad (de cara al cliente)
  admin/
    base.html           Layout admin (sidebar, modales, command palette)
    index.html          Dashboard con tabs (Interesados/Propietarios/Propiedades/Archivados)
    propiedad.html      Ficha ADMIN de propiedad (editor)
    perfil.html         Ficha de cliente
    captacion.html      Pipeline de leads
    catastro.html       Mapa GIS (cockpit catastral)
    consultas.html      Bandeja de consultas web
static/
  admin.css / admin.js  Design system del admin (fuente de estilos central) + utilidades JS
  public.css            Tokens del sitio público (el CSS real está inline en los templates)
  geo/ater/             GeoJSON de parcelas de Gualeguay (8.5 MB, 13.761 features)
  geo/ign/              GeoJSON IGN (departamentos, planta urbana, red vial, etc.)
  uploads/              Fotos subidas (ignorado en git)
```

## Modelos (models.py)
`Propiedad` (urbanas + campos rurales en una tabla), `Cliente`, `Admin`, `Consulta`, `CaptacionLead` + `PropietarioLead` + `CaptacionActividad`, `ParcelaCatastral` + `OportunidadTerreno` + `InvestigacionPropietario` + `PropietarioCatastral` + `ActividadParcela`. Relaciones M2M: propietarios/interesados de propiedades, propietarios catastrales.

## Convenciones del código
- Cada modelo expone **`as_dict()`** para serializar a JSON.
- Auth por decoradores: **`@login_required`** (páginas, redirige a login) y **`@api_login_required`** (API, 401 JSON + verifica **CSRF** con `hmac.compare_digest` en métodos mutantes).
- **Soft-delete** con `deleted_at` en entidades importantes; las queries públicas filtran por `deleted_at IS NULL` y `publicada=True`.
- Helpers de parseo `_bool` / `_float` / `_int` para coercionar input.
- Fotos: se guardan como **CSV en un String** (`Propiedad.fotos`), paths con forward-slashes; helpers `_fotos_from_str` / `_fotos_to_str`.
- Front admin: interceptor de `fetch` en `admin.js` inyecta `X-CSRFToken` y redirige a login en 401. Usar `esc()` para escapar HTML.
- Separación **pública vs admin** es real y debe mantenerse: templates, APIs (`/api/public/...` vs `/api/...`) y decoradores distintos. Nunca exponer datos internos en la vista pública.

## Comandos
```bash
# Arranque local (usa FLASK_ENV del .env; DEBUG viene de la config)
python app.py

# Migraciones (wrapper casero de Flask-Migrate)
python manage.py db init      # solo la primera vez
python manage.py db migrate   # genera migración desde los cambios de models.py
python manage.py db upgrade    # aplica

# Seed demo (NO correr en prod)
python load_demo.py

# Tests funcionales (HTTP contra la app corriendo)
python audit_test.py
```
**Deploy (PythonAnywhere):** `git push` desde local → en PythonAnywhere `git pull` en el directorio del proyecto → **Reload** del web app desde el panel. Env vars (`SECRET_KEY`, `FLASK_ENV=production`, `DATABASE_URL`, contacto, SMTP) se setean en el panel/WSGI, no en git. El `.env` nunca se commitea.

## Reglas SÍ / NO de este proyecto
- **SÍ** escapar siempre el HTML que se inyecta por `innerHTML` (hoy hay interpolación sin escapar en la ficha pública → XSS latente).
- **SÍ** hacer guard de `request.get_json(silent=True)` y validar claves antes de indexar (`data['x']` directo tira 500).
- **SÍ** mantener `admin.css` como fuente central de estilos del admin; mover CSS inline hacia ahí en vez de duplicar.
- **SÍ** en el mapa: cargar datasets grandes con gating de bbox/zoom y `preferCanvas` (patrón de la capa ATER).
- **NO** agregar `ALTER TABLE` crudos al arranque de `app.py` — usar Alembic. (Hoy existe ese bloque en `app.py:1960`; es deuda a eliminar, no a imitar.)
- **NO** meter credenciales/passwords en scripts ni en el repo.
- **NO** cargar GeoJSON completos de golpe sin gating (13k+ features congelan el browser).
- **NO** servir uploads por Flask en prod si se pueden mapear como estáticos.

## Estado y prioridades
Ver **`ROADMAP.md`**. Lo urgente hoy: fixes de config/seguridad de producción (DEBUG por defecto, `SECRET_KEY` efímera, credenciales hardcodeadas), luego el rediseño de la ficha admin y la performance del mapa de catastro.
