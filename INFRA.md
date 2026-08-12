# INFRA — dónde vive cada cosa

Mapa de la infraestructura de Moret Inmobiliaria: qué servicio hace qué, con qué cuenta se
entra y qué pasa si se rompe. **Última revisión: 12/08/2026.**

> ⚠️ **Acá NO van contraseñas, tokens ni claves.** Este archivo está en el repo. Es un mapa de
> *dónde* está cada cosa, no de *cómo* se abre. Las credenciales viven en el gestor de
> contraseñas del Gmail personal (ver [Cuentas](#cuentas-y-credenciales)).

Los datos marcados con 🔎 vienen de notas viejas y **conviene confirmarlos en el panel** — no
los pude verificar desde el código.

---

## Resumen en una tabla

| Qué | Dónde | Cuenta que lo controla |
|---|---|---|
| Sitio en vivo | https://moretinmobiliaria.com | — |
| Hosting de la app | Railway, servicio `app-inmobiliaria` | `moretinmobiliaria.admin@gmail.com` |
| Base de datos | Railway, servicio Postgres | idem |
| Fotos de propiedades | Volumen de Railway en `/app/static/uploads` | idem |
| DNS y HTTPS | Cloudflare | 🔎 confirmar cuál |
| Dominio (registrador) | Namecheap | 🔎 confirmar cuál |
| Código | github.com/cerosmrt/app-inmobiliaria (privado) | usuario `cerosmrt` |
| Mails de consultas e invitaciones | SMTP de Gmail | 🔎 confirmar casilla |

---

## Dominio y DNS

- **Dominio:** `moretinmobiliaria.com`, comprado en **Namecheap**. 🔎 Registrante: Roberto Moret /
  Moret Inmobiliaria, con *Domain Privacy* activada. Costo ~USD 6,79 el primer año, ~USD 15 la
  renovación. **Ojo con la fecha de renovación: si vence, se cae el sitio.**
- **El DNS NO lo maneja Namecheap.** Los nameservers apuntan a **Cloudflare**
  (🔎 `ollie.ns.cloudflare.com` / `ram.ns.cloudflare.com`). Cualquier cambio de DNS se hace en
  Cloudflare, no en Namecheap.
- **En Cloudflare:** CNAME `@` → 🔎 `qfub0x0q.up.railway.app`, en modo **Proxied** (nube naranja),
  y SSL/TLS en **Full**.
- **El HTTPS lo da Cloudflare**, no Railway: Railway no emite certificado para la raíz del dominio
  por cómo funciona el aplanado de CNAME. Por eso el proxy naranja no es opcional — si lo pasás a
  "DNS only", el sitio deja de tener certificado válido.
- **Pendiente:** `www.moretinmobiliaria.com` no está configurado. Habría que agregar un redirect
  en Cloudflare.

## Hosting — Railway

- **Proyecto:** 🔎 "zonal-radiance". **Servicio de la app:** `app-inmobiliaria`.
- **URL interna de Railway:** `app-inmobiliaria-production.up.railway.app` (sirve para probar
  salteando Cloudflare, útil para aislar si un problema es del sitio o del DNS).
- **Runtime:** Python 3.11 (`.python-version`), región **EU West**, **1 réplica**. *(Verificado en
  el panel el 12/08/2026.)*
- **Arranque:** `Procfile` → `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120`. El timeout alto
  es a propósito: las llamadas al catastro/IGN son lentas.
- **Plan:** 🔎 Hobby, ~USD 5/mes con tope, pagado con la tarjeta del padre.
- **Cuenta:** `moretinmobiliaria.admin@gmail.com` — casilla creada para la infraestructura, a
  nombre del negocio.

### Cómo se deploya

`git push` a **`master`** y listo. No hay pasos manuales.

1. Railway detecta el push y buildea.
2. **Antes** de levantar gunicorn corre `python release.py` (declarado en `railway.json` como
   `preDeployCommand`), que deja el esquema de la base al día.
3. Si `release.py` falla, **el deploy se aborta y queda viva la versión anterior**. Nunca queda
   código nuevo contra un esquema viejo.

En Settings → Source: branch `master`, "Auto deploys when pushed to GitHub" habilitado.

> ⚠️ **Sin veredicto:** no está probado que el webhook dispare solo. El servicio se creó desde un
> template (bloque *Upstream Repo* con "Eject") y hay sospecha de que ignore el push. Si después de
> pushear no arranca un build en ~1 minuto, apretá **"Check for updates"** para forzarlo — y si eso
> pasa siempre, hay que hacer **Disconnect + reconectar** el repo en Settings → Source.
> **Nunca uses "Eject": forkea el repo** y te deja con un remote distinto.

## Base de datos

- **Postgres gestionado por Railway**, servicio aparte. La `DATABASE_URL` la inyecta Railway sola
  en el servicio de la app.
- En dev es **SQLite** (`instance/inmobiliaria.db`). Lo decide `FLASK_ENV`.
- **Backups:** pestaña **Backups** del servicio Postgres. **Hacer uno antes de cualquier cambio de
  esquema.**
- **Historia importante:** la base se creó con `create_all()` y **nunca tuvo tabla
  `alembic_version`**. Por eso existe `release.py`: detecta ese caso, stampea en la revisión
  `f498a2a5780f` y recién ahí aplica lo pendiente. Es idempotente. No corras `db upgrade` a mano
  contra producción sin entender esto.
- **Pendiente:** apagar el **"Public Access"** del Postgres, que se abrió para migrar los datos
  desde la SQLite local y quedó prendido.

## Archivos subidos

| Qué | Dónde | ¿Sobrevive un deploy? |
|---|---|---|
| Fotos de propiedades | volumen montado en `/app/static/uploads` | ✅ sí |
| Adjuntos privados (planos, escrituras) | `private_uploads/adjuntos/` | ❌ **🔎 no — disco efímero** |

> 🔴 **Riesgo conocido a verificar.** Según las notas de deploy, los adjuntos internos quedaron en
> disco efímero, o sea que **se borrarían en cada deploy**. Si esa función se está usando en serio,
> hay que montarle un segundo volumen o mudarlos a storage externo. **Confirmar en Settings →
> Volumes cuántos volúmenes hay montados.**

Los adjuntos viven fuera de `static/` a propósito: todo lo que cuelga de `static` lo sirve el
servidor directo, sin pasar por Flask y por lo tanto sin sesión. Se bajan solo por `/adjuntos/<id>`,
detrás de login.

## Repositorio

- **github.com/cerosmrt/app-inmobiliaria**, privado.
- Branch de producción: **`master`**. La rama `pendientes` ya se mergeó (12/08/2026).
- El `.env` **nunca** se commitea (está en `.gitignore`). Hay un `.env.example` con los nombres.

## Cuentas y credenciales

- **Casilla de infraestructura:** `moretinmobiliaria.admin@gmail.com`. Es la que tiene Railway y
  🔎 posiblemente Namecheap y Cloudflare. Creada para que los servicios estén a nombre del negocio
  y no de una persona.
- **Todas las contraseñas** (Google de infra, Railway, Namecheap, Cloudflare, admin del sitio)
  están en el **gestor de contraseñas del Gmail personal del usuario**. No están acá ni en el repo.
- **Admin del sitio:** el primero se creó en `/admin/setup`, ruta que se bloquea sola una vez que
  existe un admin. Hoy la cuenta principal es **`fmoret`** (usuario y contraseña, sin email
  cargado). Está anotado en el ROADMAP pasarla a la casilla del negocio.

## Variables de entorno (nombres, no valores)

Se setean en Railway → servicio de la app → **Variables**.

| Variable | Para qué | ¿Obligatoria? |
|---|---|---|
| `SECRET_KEY` | firma de sesiones — **la app no arranca sin esto en prod** | sí |
| `FLASK_ENV` | `production` | sí |
| `DATABASE_URL` | la inyecta Railway desde el Postgres | sí |
| `CONTACTO_TELEFONO`, `CONTACTO_WA`, `CONTACTO_EMAIL` | datos que muestra el sitio público | no |
| `MAIL_SMTP`, `MAIL_PORT`, `MAIL_USER`, `MAIL_PASS`, `MAIL_TO` | envío de consultas e invitaciones de admins | no |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | descripciones generadas con IA (degrada limpio si falta) | no |

Si `SECRET_KEY` cambia, **se cierran todas las sesiones abiertas**. No la rotes por las dudas.

---

## Si se rompe — por dónde empezar

1. **¿El sitio no abre?** Probá la URL interna de Railway
   (`app-inmobiliaria-production.up.railway.app`). Si esa anda y el dominio no, el problema es
   **Cloudflare/DNS**, no la app.
2. **¿Da error 500?** Railway → servicio → **View logs**. El traceback está ahí.
3. **¿Falló un deploy?** Mirá el log del pre-deploy: las líneas que empiezan con `[release]`. Si la
   migración falló, **el sitio anterior sigue vivo** — no hay apuro.
4. **¿Un deploy rompió algo?** Railway → **Deployments** → en el deploy anterior, los tres puntos →
   redeploy. Vuelve atrás en un click.
5. **¿Se perdieron datos?** Pestaña **Backups** del Postgres.

## Pendientes de infraestructura

- [ ] Confirmar si los adjuntos privados tienen volumen (🔴 si no, se borran en cada deploy)
- [ ] Apagar el "Public Access" del Postgres
- [ ] Configurar `www.moretinmobiliaria.com` (redirect en Cloudflare)
- [ ] Determinar si el auto-deploy por push funciona o hay que reconectar el repo
- [ ] Pasar la cuenta principal del admin a `moretinmobiliaria.admin@gmail.com` (ver ROADMAP)
- [ ] Anotar la fecha de renovación del dominio en algún lado con recordatorio

## Lo que NO está acá, a propósito

Contraseñas, tokens, la `SECRET_KEY`, la API key de Anthropic, las claves de aplicación de Gmail.
Nada de eso va a un archivo del repo, ni siquiera en uno privado. Si necesitás alguno, están en el
gestor de contraseñas.
