"""
Suite de regresión — Moret Inmobiliaria
========================================

Corre OFFLINE: no necesita servidor levantado, ni credenciales, ni paquetes
extra (usa el test client de Flask). Arma una base SQLite temporal y limpia
todo al terminar, así que nunca toca `instance/inmobiliaria.db`.

    python test_regresion.py

Sale con código 1 si algo falla, para poder engancharlo a un hook o CI.

Qué cubre — pensado para avisar si rompimos algo al implementar lo próximo:
  1. Auth        — páginas y APIs protegidas
  2. CSRF        — métodos mutantes sin token
  3. Rutas       — todas las pantallas del admin renderizan
  4. Seguridad   — path traversal al borrar fotos, escapado en el sitio público
  5. Robustez    — ningún endpoint de escritura tira 500 con body vacío o basura
  6. Reglas      — alta de cliente sólo con nombre
  7. Plantillas  — invariantes que el JS necesita para funcionar
"""
import json
import os
import shutil
import sys
import tempfile

PROJ = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJ)
sys.path.insert(0, PROJ)

# Base temporal — antes de importar app, que lee DATABASE_URL al importarse.
_TMP = tempfile.mkdtemp(prefix='moret_test_')
os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(_TMP, 'test.db').replace('\\', '/')
os.environ['SECRET_KEY'] = 'clave-solo-para-tests'
os.environ['FLASK_ENV'] = 'development'

import app as A                                                    # noqa: E402
from models import db, Propiedad, Cliente, Admin, Consulta, CaptacionLead  # noqa: E402

PASS, FAIL = [], []


def check(nombre, condicion, detalle=''):
    if condicion:
        PASS.append(nombre)
        print('  PASS  %s' % nombre)
    else:
        FAIL.append((nombre, detalle))
        print('  FAIL  %s%s' % (nombre, ('  -> ' + str(detalle)) if detalle else ''))


def seccion(titulo):
    print('\n' + titulo)
    print('-' * len(titulo))


# ── Datos de prueba ───────────────────────────────────────────────────────────
XSS = '<img src=x onerror=alert(1)>'

with A.app.app_context():
    db.create_all()
    adm = Admin(username='test')
    adm.set_password('test-1234')
    db.session.add(adm)
    prop = Propiedad(direccion='Sarmiento 450', barrio='Centro', tipo='casa',
                     operacion='venta', estado='disponible', publicada=True)
    cli = Cliente(nombre='Ana', apellido='Ruiz', telefono='3444111222', tipo='propietario')
    db.session.add_all([prop, cli])
    db.session.commit()
    PROP_ID, CLI_ID, ADMIN_ID = prop.id, cli.id, adm.id

cli_http = A.app.test_client()


def login():
    with cli_http.session_transaction() as s:
        s['admin_id'] = ADMIN_ID
        s['admin_username'] = 'test'
        s['csrf_token'] = 'token-de-test'


def logout():
    with cli_http.session_transaction() as s:
        s.clear()


H = {'X-CSRFToken': 'token-de-test'}


def tpl(nombre):
    with open(os.path.join(PROJ, 'templates', nombre), encoding='utf-8') as f:
        return f.read()


# ── 1. Auth ───────────────────────────────────────────────────────────────────
seccion('1. Auth — nada del admin es accesible sin sesión')
logout()
for ruta in ['/admin', '/admin/catastro', '/admin/captacion', '/admin/consultas',
             '/admin/propiedad/%d' % PROP_ID, '/cliente/%d' % CLI_ID]:
    r = cli_http.get(ruta)
    check('anonimo en %s redirige al login' % ruta, r.status_code == 302, r.status_code)

for ruta in ['/api/propiedades', '/api/clientes', '/api/consultas']:
    r = cli_http.get(ruta)
    check('anonimo en %s da 401' % ruta, r.status_code == 401, r.status_code)

# ── 2. CSRF ───────────────────────────────────────────────────────────────────
seccion('2. CSRF — los métodos mutantes exigen token')
login()
r = cli_http.post('/api/clientes', json={'nombre': 'X', 'tipo': 'interesado'})
check('POST sin X-CSRFToken da 403', r.status_code == 403, r.status_code)
r = cli_http.post('/api/clientes', json={'nombre': 'X', 'tipo': 'interesado'},
                  headers={'X-CSRFToken': 'token-equivocado'})
check('POST con token incorrecto da 403', r.status_code == 403, r.status_code)

# ── 3. Rutas ──────────────────────────────────────────────────────────────────
seccion('3. Rutas — todas las pantallas del admin renderizan')
for ruta in ['/admin', '/admin/catastro', '/admin/captacion', '/admin/consultas',
             '/admin/propiedad/%d' % PROP_ID, '/cliente/%d' % CLI_ID]:
    r = cli_http.get(ruta)
    check('GET %s da 200' % ruta, r.status_code == 200, r.status_code)

# El login se sirve sin sesión; con sesión abierta redirige, que es lo correcto.
logout()
r = cli_http.get('/admin/login')
check('GET /admin/login da 200 sin sesión', r.status_code == 200, r.status_code)
login()
r = cli_http.get('/admin/login')
check('GET /admin/login redirige con sesión abierta', r.status_code == 302, r.status_code)

for ruta in ['/', '/propiedad/%d' % PROP_ID]:
    r = cli_http.get(ruta)
    check('GET %s (público) da 200' % ruta, r.status_code == 200, r.status_code)

# ── 4. Seguridad ──────────────────────────────────────────────────────────────
seccion('4. Seguridad — path traversal al borrar fotos')
centinela = os.path.join(PROJ, '__test_centinela.txt')
with open(centinela, 'w') as f:
    f.write('no me borres')
try:
    for ataque in ['__test_centinela.txt',
                   'static/uploads/../../__test_centinela.txt',
                   '..%2F__test_centinela.txt']:
        r = cli_http.delete('/api/propiedades/%d/fotos/%s' % (PROP_ID, ataque), headers=H)
        check('borrado fuera de uploads rechazado (%s)' % ataque[:34],
              r.status_code == 400, r.status_code)
    check('el archivo de afuera sigue existiendo', os.path.exists(centinela))
finally:
    if os.path.exists(centinela):
        os.remove(centinela)

# El camino legítimo tiene que seguir funcionando.
updir = A.app.config['UPLOAD_FOLDER']
os.makedirs(updir, exist_ok=True)
legit_rel = updir.replace('\\', '/') + '/__test_foto.webp'
with open(os.path.join(PROJ, legit_rel), 'w') as f:
    f.write('foto')
r = cli_http.delete('/api/propiedades/%d/fotos/%s' % (PROP_ID, legit_rel), headers=H)
check('borrado legítimo de una foto da 200', r.status_code == 200, r.status_code)
check('la foto legítima se borró del disco', not os.path.exists(os.path.join(PROJ, legit_rel)))

seccion('4b. Seguridad — el sitio público escapa lo que viene de la DB')
pub_prop, pub_index = tpl('propiedad.html'), tpl('index.html')
for campo in ['p.direccion', 'p.barrio', 'p.tipo', 'p.operacion']:
    check('propiedad.html escapa %s' % campo, 'escHtml(%s)' % campo in pub_prop)
for campo in ['p.direccion', 'p.barrio', 'p.tipo', 'p.operacion', 'p.estado']:
    check('index.html escapa %s' % campo, 'escHtml(%s)' % campo in pub_index)
check('index.html define escHtml', 'function escHtml' in pub_index)

# ── 5. Robustez ───────────────────────────────────────────────────────────────
seccion('5. Robustez — ningún endpoint de escritura tira 500')
SALTEAR = ('upload', 'fotos', 'import', 'permanente', 'logout', 'login', 'setup')
quinientos = []
probados = 0
for regla in A.app.url_map.iter_rules():
    metodos = (regla.methods or set()) - {'HEAD', 'OPTIONS', 'GET'}
    ruta = str(regla)
    if any(s in ruta for s in SALTEAR) or '<' in ruta.replace('<int:id>', ''):
        continue
    concreta = ruta.replace('<int:id>', str(PROP_ID))
    if '<' in concreta:
        continue
    for m in sorted(metodos & {'POST', 'PUT', 'PATCH'}):
        for cuerpo, kw in [('vacío', dict(json={})),
                           ('basura', dict(data=b'no soy json',
                                           content_type='text/plain'))]:
            r = cli_http.open(concreta, method=m, headers=H, **kw)
            probados += 1
            if r.status_code == 500:
                quinientos.append('%s %s (body %s)' % (m, ruta, cuerpo))
check('cero 500 en %d combinaciones de endpoint/body' % probados,
      not quinientos, '; '.join(quinientos))

# ── 6. Reglas de negocio ──────────────────────────────────────────────────────
seccion('6. Reglas — alta de cliente sólo con el nombre')
r = cli_http.post('/api/clientes', json={'nombre': 'Pedro', 'tipo': 'propietario'}, headers=H)
check('alta con sólo nombre da 201', r.status_code == 201, r.status_code)
if r.status_code == 201:
    d = r.get_json()
    check('apellido queda en cadena vacía, no None', d.get('apellido') == '', d.get('apellido'))
    check('teléfono queda en cadena vacía, no None', d.get('telefono') == '', d.get('telefono'))
r = cli_http.post('/api/clientes', json={'tipo': 'propietario'}, headers=H)
check('alta sin nombre da 400 (no 500)', r.status_code == 400, r.status_code)
r = cli_http.post('/api/clientes', data=b'basura', content_type='text/plain', headers=H)
check('alta con body no-JSON da 400 (no 500)', r.status_code == 400, r.status_code)

seccion('6b. Reglas — el dato sucio no rompe las APIs del admin')
with A.app.app_context():
    p = db.session.get(Propiedad, PROP_ID)
    p.direccion, p.barrio = XSS, XSS
    db.session.commit()
r = cli_http.get('/api/propiedades')
check('/api/propiedades responde con datos que contienen HTML', r.status_code == 200, r.status_code)
r = cli_http.get('/admin/propiedad/%d' % PROP_ID)
check('la ficha admin renderiza con datos que contienen HTML', r.status_code == 200, r.status_code)
check('el HTML crudo no aparece sin escapar en la ficha',
      b'<img src=x onerror' not in r.data)

# ── 6c. Adjuntos privados ─────────────────────────────────────────────────────
# Lo importante acá no es que suban: es que NO se puedan bajar sin sesión y que
# no queden guardados abajo de static/, que el servidor sirve sin pasar por
# Flask (o sea, sin auth). Ver el docstring de models.Adjunto.
seccion('6c. Adjuntos — privados de verdad')
login()
import io as _io                                                   # noqa: E402

_PDF = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'
r = cli_http.post('/api/propiedades/%d/adjuntos' % PROP_ID,
                  data={'file': (_io.BytesIO(_PDF), 'plano.pdf')},
                  content_type='multipart/form-data', headers=H)
check('subir un PDF da 201', r.status_code == 201, r.status_code)
ADJ = r.get_json() if r.status_code == 201 else {}
ADJ_ID = ADJ.get('id')

# Un .pdf que adentro no es un PDF no entra: se mira el encabezado, no la extensión.
r = cli_http.post('/api/propiedades/%d/adjuntos' % PROP_ID,
                  data={'file': (_io.BytesIO(b'esto no es un pdf'), 'trucho.pdf')},
                  content_type='multipart/form-data', headers=H)
check('un PDF falso (magic bytes) da 400', r.status_code == 400, r.status_code)

r = cli_http.post('/api/propiedades/%d/adjuntos' % PROP_ID,
                  data={'file': (_io.BytesIO(b'MZ...'), 'virus.exe')},
                  content_type='multipart/form-data', headers=H)
check('una extensión no permitida da 400', r.status_code == 400, r.status_code)

r = cli_http.get('/api/propiedades/%d/adjuntos' % PROP_ID)
check('el listado devuelve el adjunto subido',
      r.status_code == 200 and any(a['id'] == ADJ_ID for a in r.get_json()))

if ADJ_ID:
    r = cli_http.get('/adjuntos/%d' % ADJ_ID)
    check('con sesión el adjunto se descarga', r.status_code == 200 and r.data == _PDF,
          r.status_code)

    logout()
    r = cli_http.get('/adjuntos/%d' % ADJ_ID)
    check('SIN sesión el adjunto redirige al login (no se sirve)',
          r.status_code == 302 and _PDF not in r.data, r.status_code)
    r = cli_http.get('/api/propiedades/%d/adjuntos' % PROP_ID)
    check('SIN sesión el listado de adjuntos da 401', r.status_code == 401, r.status_code)
    login()

    with A.app.app_context():
        from models import Adjunto as _Adj
        _a = db.session.get(_Adj, ADJ_ID)
        _ruta = os.path.join(A._ADJUNTOS_FOLDER, _a.filename) if _a else ''
    check('el archivo no vive abajo de static/',
          'static' not in _ruta.replace('\\', '/').split('/'), _ruta)
    check('el archivo existe en disco', os.path.exists(_ruta), _ruta)

    r = cli_http.delete('/api/adjuntos/%d' % ADJ_ID, headers=H)
    check('borrar el adjunto da 200', r.status_code == 200, r.status_code)
    check('el archivo se borró del disco', not os.path.exists(_ruta), _ruta)

# ── 7. Invariantes de plantilla ───────────────────────────────────────────────
seccion('7. Plantillas — lo que el JS necesita para funcionar')
ficha = tpl('admin/propiedad.html')
invariantes = [
    ('typeahead de propietarios',        "'ta-input-prop'" in ficha),
    ('typeahead de interesados',         "'ta-input-inter'" in ficha),
    ('el typeahead no busca con <2 letras', '_TA_MIN = 2' in ficha),
    ('se puede crear desde el buscador',  'function taFormNuevo' in ficha),
    ('la lista completa ya no se vuelca', 'renderDispList' not in ficha),
    ('booleanos como switch',             'class="switch"' in ficha),
    ('selector de moneda',                "type: 'moneda'" in ficha),
    ('personas dentro del card Datos',    ficha.find('<h2>Datos</h2>') < ficha.find('class="personas-grid"')),
    ('el mapa vive en un modal',          'id="modal-geo"' in ficha),
    ('el mapa se inicializa al abrirlo',  'function abrirMapa' in ficha),
    ('el rail no tiene scroll propio',    'overflow-y: auto' not in ficha.split('.prop-rail')[1][:300]),
    ('labels con contraste AA',           'color: var(--text-2)' in ficha),
    # El card del rail no pasa de una pantalla y la galería scrollea adentro
    # suyo: es lo que evita que el rail sea la columna más alta y estire la
    # página cuando la propiedad tiene 10+ fotos.
    ('el card del rail tope una pantalla',
     'max-height: calc(100vh - 95px)' in ficha),
    # Los matches automáticos salieron de la ficha (siguen en el listado) y el
    # typeahead ya no vive siempre abierto: lo destapa un botón del subtítulo.
    ('la ficha ya no pide matches',        '/matches' not in ficha),
    # La ficha se lee como "privado | público": los rótulos están escritos y el
    # switch de publicar vive encima de lo que efectivamente publica.
    ('la columna izquierda dice Privado',  'col-rotulo-privado' in ficha),
    ('la columna derecha dice Público',    'col-rotulo-publico' in ficha),
    ('el switch de publicar está en el rótulo',
     'renderRotuloPublicada' in ficha
     and "field: 'publicada'" not in ficha),
    ('la ficha tiene bloque de adjuntos',
     'adjuntos-lista' in ficha and 'function subirAdjuntos' in ficha),
    ('el buscador de personas se abre con un botón',
     'class="ta-abrir"' in ficha and 'function taToggle' in ficha
     and 'class="ta-wrap" id=' in ficha and 'hidden>' in ficha),
    ('la galería es el bloque elástico',
     'flex: 0 1 auto' in ficha.split('.fotos-admin-grid {')[1][:260]
     and 'overflow-y: auto' in ficha.split('.fotos-admin-grid {')[1][:260]),
]
for nombre, ok in invariantes:
    check(nombre, ok)

base = tpl('admin/base.html')
check('el admin carga Inter, no Lora', 'family=Inter' in base and 'Lora' not in base)
check('admin.css va versionado (cache-busting)', "admin.css') }}?v=" in base)

listado = tpl('admin/index.html')
check('el modal de propietarios permite crear', 'formNuevoPropietarioModal' in listado)

# Sitio público: la inmobiliaria hoy solo opera venta y nadie busca por barrio
# en una ciudad chica. Y el carrusel dibuja un dot por foto — cuando eran 5
# fijos, una propiedad con 8 fotos parecía quedarse clavada al pasar la quinta.
check('el sitio público no ofrece alquiler',
      'tab-alquiler' not in pub_index and "setTab('alquiler')" not in pub_index)
check('el sitio público no busca por barrio', 'f-barrio' not in pub_index)
check('sin barra de solapas', 'tabs-bar' not in pub_index and 'setTab' not in pub_index)
check('el carrusel no recorta los dots', 'fotos.slice(0, 5)' not in pub_index)

# ── Resumen ───────────────────────────────────────────────────────────────────
shutil.rmtree(_TMP, ignore_errors=True)
print('\n' + '=' * 62)
print('  %d PASS   %d FAIL' % (len(PASS), len(FAIL)))
if FAIL:
    print('\n  Fallaron:')
    for nombre, detalle in FAIL:
        print('   - %s%s' % (nombre, ('  (%s)' % detalle) if detalle else ''))
print('=' * 62)
sys.exit(1 if FAIL else 0)
