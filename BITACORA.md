# BITÁCORA — Moret Inmobiliaria

Diario cronológico de las sesiones de trabajo: qué se charló, qué se decidió y qué quedó
pendiente de decidir. Sirve para que cualquier sesión futura (con Claude o no) retome con
contexto. **No reemplaza** a `ROADMAP.md` (backlog vivo, Pendiente/Hecho) ni a `CLAUDE.md`
(reglas del proyecto): esto es la conversación, aquello es el estado.

## Cómo se mantiene
- **Una entrada por sesión**, arriba de todo (más nueva primero), con fecha `AAAA-MM-DD`.
- Anotar tres cosas: **qué se hizo**, **qué se decidió** (con el porqué) y **qué quedó abierto**.
- Las fechas relativas ("la semana que viene") se convierten a fecha absoluta al escribir.
- Breve: bullets, no prosa. El detalle fino va al commit y al ROADMAP.
- Al cerrar la sesión, actualizar también `ROADMAP.md` si cambió el estado de algo.

---

## 2026-08-28 — Bitácora + asistente de completitud de propiedades

**Qué se hizo**
- Se creó `BITACORA.md` (este archivo). Es un **resumen** de lo charlado, no una
  transcripción: qué se hizo, qué se decidió y por qué, qué quedó abierto.
- **Asistente de completitud de propiedades** (una sola tanda, decisión del usuario de
  avanzar sin más preguntas):
  - `Propiedad.completitud()` en `models.py` — fuente única. 10 ítems (7 del aviso, 3
    internos), rurales piden hectáreas en vez de ambientes. Expuesto en `as_dict()`, fuera
    de `_CAMPOS_PUBLICOS`.
  - Tabla de Propiedades: columna "Completá" (barra + N/10, ordenable, tooltip) + filtro
    "Incompletas".
  - Ficha admin: panel "Qué falta" en el rail público, cada faltante linkeado a su campo.
  - `PUT /api/propiedades/<id>` ahora devuelve la propiedad entera (antes `{message}`).
  - Toast de aviso al publicar con faltantes del aviso — nunca bloquea.
  - Suite: 125 PASS / 0 FAIL. `admin.css?v=14`.

**Qué se decidió**
- **Nada bloquea publicar.** La idea explícita del usuario: poder crear propiedades rápido
  con un solo dato, y que la app avise qué falta (para el aviso *y* lo interno). Si él
  decide publicar sin foto, se publica; solo se avisa.
- El cálculo vive en el modelo, no duplicado en el front, para que tabla y ficha usen lo
  mismo.

**Qué quedó abierto**
- El mock inicial mostraba también un chip "N sin publicar" en la barra de stats; no se
  implementó (el filtro "Incompletas" cubre el caso). Si se quiere, es un paso aparte.

---

## Antes de la bitácora — resumen de lo charlado (reconstruido del ROADMAP y los commits)

Entradas sin fecha exacta de sesión; se listan por tema para no perder el contexto de las
decisiones ya tomadas.

### Marca / logo (últimos commits, ~2026-08)
- Entró el logo real (`M.png` + `RobertoMoretInmobiliaria.png`), recortado al contenido y
  con el fondo `~#FAFAFA` pasado a transparente. Quedaron `static/logo.png`,
  `static/isotipo.png` y `static/favicon.png`. Se borró el `favicon.svg` dibujado a mano.
- El favicon salió chico la primera vez (el fondo no era blanco puro); se corrigió el
  umbral de recorte. Los `<link rel="icon">` van con `?v=2` por el caché del browser.
- `notas.txt` tiene un recordatorio viejo sobre extraer un pedacito del logo para el tab
  de Chrome — ya resuelto con `favicon.png`.

### Charlas con Roberto (el papá)
- **2026-08-14 · "Precio sugerido":** quiere publicar con precio pero rotulado como
  *"Precio sugerido"* / *"Sugerido U$S xxx"*, porque casi siempre se negocia. Falta definir
  si va en todas las operaciones o sólo casas, y si el rótulo se guarda por propiedad o es
  fijo del sitio. **No tocar hasta charlarlo más.**
- **2026-08-14 · Fotos huérfanas:** al sacar/reemplazar una foto se quita la ruta del CSV
  pero el archivo queda en `static/uploads/`. 36 archivos huérfanos en la base local (que
  NO es la de prod). Dos decisiones separadas: recuperarlas (vista para reenganchar) y que
  no vuelva a pasar (borrar al sacar, o limpieza aparte). En prod esto crece dentro del
  volumen pago de Railway.

### Revisiones de diseño
- **2026-08-13 · Ficha pública:** tres tandas de pulido visual hechas. Queda a propósito
  un solo punto: pasar el rojo de marca a un borgoña apagado — es cambio de identidad
  (afecta landing + logo + admin), decisión del usuario, no técnica.
- **2026-07-23 · Identidad visual alineada al logo:** serif sólo en títulos del portal
  público, sans en todo el admin; paleta del admin de cálida a gris frío; rojo de acento
  muestreado del logo; `.btn-ver` negro sólido. Revirtió un "todo a sans" decidido ese
  mismo día más temprano.
- **2026-07-23 · Galería de fotos:** decidido pasar a 2×2 con «+N» y mudar el manejo
  (reordenar/subir/borrar) a un modal grande. Agrega un clic por cambio.
- **2026-07-22 · Assessment del admin:** barrido de las 6 pantallas. Lo que era bug se
  arregló; quedó para revisar junto lo que es decisión de diseño/negocio (accesibilidad de
  24 inputs, contraste en hover, endpoints que crean registros vacíos, etc.).

### Infraestructura / deploy
- **2026-08-12 · Rama `pendientes` mergeada a `master` y en producción.** Tres features:
  gestor de administradores (login por email + permisos por sección), panel de textos del
  sitio, y "captar desde cualquier dato". Verificado en prod.
- **2026-08-12 · Migraciones automáticas en cada deploy:** `railway.json` declara
  `preDeployCommand: ["python release.py"]`. Si la migración falla, aborta el deploy.
- **Pendientes de infra:** confirmar si el auto-deploy lo dispara el webhook o hay que
  hacer "Check for updates" a mano; apagar el "Public Access" del Postgres; pasar la cuenta
  principal (`fmoret`, una persona) a la casilla del negocio
  (`moretinmobiliaria.admin@gmail.com`); configurar SMTP en Railway (`MAIL_SMTP`,
  `MAIL_USER`, `MAIL_PASS`) — sin eso no sale ningún mail.
