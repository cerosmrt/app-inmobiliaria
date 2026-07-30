# Deploy en Railway — paso a paso

Guía para poner el sitio online en **Railway** con auto-deploy (cada `git push` a
`master` publica solo). El código ya está listo; esto es la parte de Railway.

## 0. Qué ya quedó preparado en el repo
- `Procfile`: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120` (escucha el puerto de Railway; timeout alto para las llamadas al catastro/IGN).
- `.python-version`: `3.11` (misma versión que en local).
- `config.py`: `ProductionConfig` con `DEBUG=False`, cookies seguras y `DATABASE_URL` (Railway lo inyecta).
- Al arrancar, la app crea el esquema solo (`create_all()`), así que en Postgres nuevo **no hay que correr migraciones**.

## 1. Crear el proyecto
1. Railway → **New Project** → **GitHub Repository** → elegí `cerosmrt/app-inmobiliaria`.
2. Si pide instalar la Railway GitHub App, aceptá y dale acceso al repo.
3. Railway detecta Python + Procfile y hace el primer build. (Va a fallar/quedar a medias hasta agregar la base y las variables — normal, seguimos.)

## 2. Agregar la base de datos Postgres
1. En el proyecto → **New** → **Database** → **Add PostgreSQL**.
2. Railway crea la base y expone `DATABASE_URL`.
3. En el servicio de la **app** (no la base) → pestaña **Variables** → asegurate de que tenga
   `DATABASE_URL` referenciando la de Postgres (Railway suele enlazarlo solo; si no, agregá una
   variable `DATABASE_URL` con el valor `${{Postgres.DATABASE_URL}}`).

## 3. Variables de entorno (en el servicio de la app → Variables)
Obligatorias:
- `FLASK_ENV` = `production`
- `SECRET_KEY` = *(una clave larga y secreta — generala, ver abajo — NO la subas al repo)*

Opcionales (contacto público y envío de mails de consultas):
- `CONTACTO_TELEFONO`, `CONTACTO_WA`, `CONTACTO_EMAIL`
- `MAIL_SMTP`, `MAIL_PORT`, `MAIL_USER`, `MAIL_PASS`, `MAIL_TO`

Para generar el `SECRET_KEY` (en tu compu):
```
python -c "import secrets; print(secrets.token_hex(32))"
```
Copiás lo que imprime y lo pegás en la variable `SECRET_KEY` de Railway.

## 4. Volumen para las fotos (importante)
Sin esto, las fotos de las propiedades se borran en cada deploy.
1. En el servicio de la app → **Settings** → **Volumes** → **Add Volume**.
2. Mount path: `/app/static/uploads`
3. Tamaño: arrancá con 1–2 GB (se agranda después).

Así las fotos viven en el volumen (persistente) y se siguen sirviendo como estáticas.

> Pendiente conocido: los **adjuntos internos** (`private_uploads/adjuntos`) todavía quedan en
> disco efímero. Si se usa esa función, se agrega un segundo volumen o se mueve a storage
> externo. No bloquea salir online.

## 5. Primer deploy y crear el admin
1. Con la base + variables + volumen listos, Railway redeploya (o forzás **Deploy**).
2. Cuando esté verde, abrí la URL pública que te da Railway.
3. Entrá a **`/admin/setup`** y creá el primer usuario admin. (Esa ruta se bloquea sola una vez
   que existe un admin.)
4. Listo: entrás por `/admin` con ese usuario.

## 6. Dominio propio (cuando lo tengas)
1. Comprá el dominio en cualquier registrador (Namecheap, etc.).
2. Railway → servicio app → **Settings** → **Networking** → **Custom Domain** → agregás el dominio.
3. Railway te da un registro **CNAME** para cargar en el DNS del registrador.
4. En unos minutos/horas queda con HTTPS automático.

## 7. De ahí en más
Cada `git push origin master` dispara un deploy automático. No hay que hacer nada más.
