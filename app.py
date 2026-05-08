from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_migrate import Migrate
from models import db, Propiedad, Cliente, Admin, Consulta
from config import config as app_config
from functools import wraps
import os
import hmac
import secrets
import time
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

try:
    from PIL import Image as _PillowImage
    _PILLOW = True
except ImportError:
    _PILLOW = False

app = Flask(__name__)

env = os.environ.get('FLASK_ENV', 'default')
app.config.from_object(app_config[env])

for folder in [app.config['UPLOAD_FOLDER'], 'templates', 'static']:
    if not os.path.exists(folder):
        os.makedirs(folder)

db.init_app(app)
migrate = Migrate(app, db)

# ── CSRF ──────────────────────────────────────────────────────────────────────

def get_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

app.jinja_env.globals['csrf_token'] = get_csrf_token

# ── Rate limiting (login) ─────────────────────────────────────────────────────

_login_attempts: dict = {}
_RATE_WINDOW = 60
_RATE_MAX    = 10

def _check_login_rate(ip: str) -> bool:
    now = time.time()
    attempts = [t for t in _login_attempts.get(ip, []) if now - t < _RATE_WINDOW]
    _login_attempts[ip] = attempts
    if len(attempts) >= _RATE_MAX:
        return False
    _login_attempts[ip].append(now)
    return True

# ── File upload ───────────────────────────────────────────────────────────────

_JPEG_MAGIC = b'\xff\xd8\xff'
_PNG_MAGIC  = b'\x89PNG'

def allowed_file(file) -> bool:
    if not file or not file.filename:
        return False
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in app.config['ALLOWED_EXTENSIONS']:
        return False
    header = file.read(4)
    file.seek(0)
    return header[:3] == _JPEG_MAGIC or header[:4] == _PNG_MAGIC

def _unique_filename(prefix: str, original: str) -> str:
    ext = secure_filename(original).rsplit('.', 1)[-1].lower()
    return f"{prefix}_{uuid.uuid4().hex[:10]}.{ext}"

def _save_image(file, filepath: str) -> None:
    if not _PILLOW:
        file.save(filepath)
        return
    try:
        img = _PillowImage.open(file)
        if img.width > 1920 or img.height > 1920:
            img.thumbnail((1920, 1920), _PillowImage.LANCZOS)
        ext = filepath.rsplit('.', 1)[-1].lower()
        if ext in ('jpg', 'jpeg'):
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(filepath, 'JPEG', quality=85, optimize=True)
        else:
            img.save(filepath, 'PNG', optimize=True)
    except Exception:
        file.seek(0)
        file.save(filepath)

# ── Auth decorators ───────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

def api_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return jsonify({"error": "No autorizado"}), 401
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            token = request.headers.get('X-CSRFToken', '')
            stored = session.get('csrf_token', '')
            if not token or not stored or not hmac.compare_digest(token, stored):
                return jsonify({"error": "Token CSRF inválido"}), 403
        return f(*args, **kwargs)
    return decorated

# ── Context processor ─────────────────────────────────────────────────────────

@app.context_processor
def inject_admin_context():
    return {'admin_username': session.get('admin_username', '')}

# ── Contacto helper ───────────────────────────────────────────────────────────

def _contacto():
    return {
        'contacto_telefono': app.config.get('CONTACTO_TELEFONO', ''),
        'contacto_wa':       app.config.get('CONTACTO_WA', ''),
        'contacto_email':    app.config.get('CONTACTO_EMAIL', ''),
    }

# ── Public pages ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', **_contacto())

@app.route('/propiedad/<int:id>')
def propiedad_publica(id):
    return render_template('propiedad.html', propiedad_id=id, **_contacto())

# ── Admin pages ───────────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
def admin_index():
    return render_template('admin/index.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin_index'))
    get_csrf_token()
    if request.method == 'POST':
        form_token = request.form.get('csrf_token', '')
        stored     = session.get('csrf_token', '')
        if not form_token or not stored or not hmac.compare_digest(form_token, stored):
            return render_template('admin/login.html', error='Error de validación. Intentá de nuevo.')
        if not _check_login_rate(request.remote_addr):
            return render_template('admin/login.html', error='Demasiados intentos. Esperá un minuto.')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        admin = Admin.query.filter_by(username=username).first()
        if admin and admin.check_password(password):
            session['admin_id']       = admin.id
            session['admin_username'] = admin.username
            return redirect(url_for('admin_index'))
        return render_template('admin/login.html', error='Usuario o contraseña incorrectos')
    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/admin/consultas')
@login_required
def admin_consultas():
    return render_template('admin/consultas.html')

@app.route('/admin/setup', methods=['GET', 'POST'])
def admin_setup():
    if Admin.query.count() > 0:
        return redirect(url_for('admin_login'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            error = 'Completá usuario y contraseña'
        else:
            admin = Admin(username=username)
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            return redirect(url_for('admin_login'))
    return render_template('admin/setup.html', error=error)

@app.route('/cliente/<int:id>')
@login_required
def cliente_perfil(id):
    return render_template('admin/perfil.html', cliente_id=id)

@app.route('/admin/propiedad/<int:id>')
@login_required
def admin_propiedad(id):
    return render_template('admin/propiedad.html', propiedad_id=id)

# ── Public API ────────────────────────────────────────────────────────────────

@app.route('/api/public/propiedades')
def api_public_propiedades():
    tipo      = request.args.get('tipo', '')
    operacion = request.args.get('operacion', '')
    ambientes = request.args.get('ambientes', '')
    barrio    = request.args.get('barrio', '')
    precio_max = request.args.get('precio_max', '')

    query = Propiedad.query.filter_by(publicada=True).filter(Propiedad.deleted_at.is_(None))
    if tipo:
        query = query.filter(Propiedad.tipo == tipo)
    if operacion:
        query = query.filter(Propiedad.operacion == operacion)
    if ambientes:
        try:
            query = query.filter(Propiedad.ambientes == int(ambientes))
        except ValueError:
            pass
    if barrio:
        query = query.filter(Propiedad.barrio.ilike(f'%{barrio}%'))
    if precio_max:
        try:
            pmax = float(precio_max)
            query = query.filter(
                db.or_(
                    Propiedad.precio_a_consultar == True,
                    Propiedad.rango_min <= pmax
                )
            )
        except ValueError:
            pass

    return jsonify([p.as_dict() for p in query.order_by(Propiedad.id.desc()).all()])

@app.route('/api/public/propiedades/<int:id>')
def api_public_propiedad(id):
    p = Propiedad.query.filter_by(id=id, publicada=True).filter(Propiedad.deleted_at.is_(None)).first()
    if not p:
        return jsonify({"error": "Propiedad no encontrada"}), 404
    return jsonify(p.as_dict())

@app.route('/api/public/consultas', methods=['POST'])
def api_public_consultas():
    data = request.get_json()
    if not data or not data.get('nombre') or not data.get('mensaje'):
        return jsonify({"error": "Nombre y mensaje son requeridos"}), 400
    consulta = Consulta(
        nombre=data['nombre'],
        telefono=data.get('telefono', ''),
        email=data.get('email', ''),
        mensaje=data['mensaje'],
        propiedad_id=data.get('propiedad_id')
    )
    db.session.add(consulta)
    db.session.commit()
    return jsonify({"message": "Consulta enviada correctamente"}), 201

# ── Admin API: Propiedades ────────────────────────────────────────────────────

@app.route('/api/propiedades', methods=['GET'])
@api_login_required
def get_propiedades():
    tipo       = request.args.get('tipo', '')
    propietario = request.args.get('propietario', '')
    interesado  = request.args.get('interesado', '')

    query = Propiedad.query.filter(Propiedad.deleted_at.is_(None))
    if tipo:
        query = query.filter(Propiedad.tipo.ilike(f'%{tipo}%'))
    if propietario:
        parts   = propietario.split()
        nombre  = parts[0]
        apellido = ' '.join(parts[1:]) if len(parts) > 1 else ''
        query = query.join(Cliente, Propiedad.propietario).filter(
            Cliente.nombre.ilike(f'%{nombre}%'),
            Cliente.apellido.ilike(f'%{apellido}%') if apellido else True
        )
    if interesado:
        parts   = interesado.split()
        nombre  = parts[0]
        apellido = ' '.join(parts[1:]) if len(parts) > 1 else ''
        query = query.join(Propiedad.interesados).filter(
            Cliente.nombre.ilike(f'%{nombre}%'),
            Cliente.apellido.ilike(f'%{apellido}%') if apellido else True
        )

    return jsonify([p.as_dict() for p in query.all()])

@app.route('/api/propiedades', methods=['POST'])
@api_login_required
def add_propiedad():
    data = request.get_json()
    nueva = Propiedad(
        direccion=data['direccion'],
        barrio=data.get('barrio'),
        rango_min=data.get('rango_min'),
        rango_max=data.get('rango_max'),
        es_usd=data.get('es_usd', True),
        precio_a_consultar=data.get('precio_a_consultar', False),
        ambientes=data.get('ambientes'),
        tipo=data['tipo'],
        operacion=data.get('operacion'),
        estado=data['estado'],
        publicada=data.get('publicada', False),
        propietario_id=data.get('propietario_id')
    )
    if 'interesados_ids' in data:
        nueva.interesados = Cliente.query.filter(Cliente.id.in_(data['interesados_ids'])).all()
    db.session.add(nueva)
    db.session.commit()
    return jsonify(nueva.as_dict()), 201

@app.route('/api/propiedades/<int:id>', methods=['GET'])
@api_login_required
def get_propiedad(id):
    p = db.session.get(Propiedad, id)
    if p:
        return jsonify(p.as_dict())
    return jsonify({"message": "Propiedad no encontrada"}), 404

@app.route('/api/propiedades/<int:id>', methods=['PUT'])
@api_login_required
def update_propiedad(id):
    p = db.session.get(Propiedad, id)
    if not p:
        return jsonify({"message": "Propiedad no encontrada"}), 404
    data = request.get_json()
    p.direccion        = data.get('direccion', p.direccion)
    p.barrio           = data.get('barrio', p.barrio)
    p.rango_min        = data.get('rango_min', p.rango_min)
    p.rango_max        = data.get('rango_max', p.rango_max)
    p.es_usd           = data.get('es_usd', p.es_usd)
    p.precio_a_consultar = data.get('precio_a_consultar', p.precio_a_consultar)
    p.ambientes        = data.get('ambientes', p.ambientes)
    p.tipo             = data.get('tipo', p.tipo)
    p.operacion        = data.get('operacion', p.operacion)
    p.publicada        = data.get('publicada', p.publicada)
    p.descripcion      = data.get('descripcion', p.descripcion)
    nuevo_estado = data.get('estado', p.estado)
    if nuevo_estado != p.estado:
        p.fecha_estado = datetime.utcnow()
    p.estado           = nuevo_estado
    p.propietario_id   = data.get('propietario_id', p.propietario_id)
    if 'interesados_ids' in data:
        p.interesados = Cliente.query.filter(Cliente.id.in_(data['interesados_ids'])).all()
    db.session.commit()
    return jsonify({"message": "Propiedad actualizada"})

@app.route('/api/propiedades/<int:id>', methods=['DELETE'])
@api_login_required
def delete_propiedad(id):
    p = db.session.get(Propiedad, id)
    if p:
        p.deleted_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"message": "Propiedad eliminada"})
    return jsonify({"message": "Propiedad no encontrada"}), 404

@app.route('/api/propiedades/<int:id>/restore', methods=['PUT'])
@api_login_required
def restore_propiedad(id):
    p = db.session.get(Propiedad, id)
    if p:
        p.deleted_at = None
        db.session.commit()
        return jsonify({"message": "Propiedad restaurada"})
    return jsonify({"message": "Propiedad no encontrada"}), 404

@app.route('/api/propiedades/<int:id>/upload', methods=['POST'])
@api_login_required
def upload_foto_propiedad(id):
    p = db.session.get(Propiedad, id)
    if not p:
        return jsonify({"message": "Propiedad no encontrada"}), 404
    if 'file' not in request.files:
        return jsonify({"message": "No se envió archivo"}), 400
    file = request.files['file']
    if not allowed_file(file):
        return jsonify({"message": "Formato no permitido"}), 400
    filename = _unique_filename(f"prop_{id}", file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    _save_image(file, filepath)
    p.fotos = (p.fotos + ',' + filepath) if p.fotos else filepath
    db.session.commit()
    return jsonify(p.as_dict()), 200

@app.route('/api/propiedades/<int:id>/fotos/<path:filename>', methods=['DELETE'])
@api_login_required
def delete_foto_propiedad(id, filename):
    p = db.session.get(Propiedad, id)
    if not p:
        return jsonify({"message": "Propiedad no encontrada"}), 404
    fotos = p.fotos.split(',') if p.fotos else []
    fotos = [f for f in fotos if f != filename]
    p.fotos = ','.join(fotos) if fotos else None
    db.session.commit()
    try:
        if os.path.exists(filename):
            os.remove(filename)
    except OSError:
        pass
    return jsonify(p.as_dict())

@app.route('/api/propiedades/<int:id>/fotos/orden', methods=['PUT'])
@api_login_required
def reordenar_fotos(id):
    p = db.session.get(Propiedad, id)
    if not p:
        return jsonify({"message": "Propiedad no encontrada"}), 404
    data = request.get_json()
    fotos = data.get('fotos', [])
    current = set(p.fotos.split(',')) if p.fotos else set()
    if fotos and not all(f in current for f in fotos):
        return jsonify({"message": "Fotos inválidas"}), 400
    p.fotos = ','.join(fotos) if fotos else None
    db.session.commit()
    return jsonify(p.as_dict())

@app.route('/api/propiedades/<int:id>/matches', methods=['GET'])
@api_login_required
def get_matches(id):
    p = db.session.get(Propiedad, id)
    if not p:
        return jsonify({"message": "Propiedad no encontrada"}), 404
    query = Cliente.query.filter(Cliente.tipo == 'interesado', Cliente.deleted_at.is_(None))
    if p.rango_min is not None and p.rango_max is not None:
        query = query.filter(
            db.or_(Cliente.rango_max == None, Cliente.rango_max >= p.rango_min),
            db.or_(Cliente.rango_min == None, Cliente.rango_min <= p.rango_max)
        )
    if p.ambientes:
        query = query.filter(db.or_(Cliente.ambientes == None, Cliente.ambientes == p.ambientes))
    return jsonify([c.as_dict() for c in query.all()])

# ── Admin API: Clientes ───────────────────────────────────────────────────────

@app.route('/api/clientes', methods=['GET'])
@api_login_required
def get_clientes():
    return jsonify([c.as_dict() for c in Cliente.query.filter(Cliente.deleted_at.is_(None)).all()])

@app.route('/api/clientes', methods=['POST'])
@api_login_required
def add_cliente():
    data = request.get_json()
    nuevo = Cliente(
        nombre=data['nombre'],
        apellido=data['apellido'],
        telefono=data['telefono'],
        email=data.get('email'),
        tipo=data['tipo'],
        rango_min=data.get('rango_min'),
        rango_max=data.get('rango_max'),
        es_usd=data.get('es_usd', False),
        ambientes=data.get('ambientes'),
        operacion=data.get('operacion'),
        descripcion=data.get('descripcion', '')
    )
    db.session.add(nuevo)
    db.session.commit()
    return jsonify(nuevo.as_dict()), 201

@app.route('/api/clientes/<int:id>', methods=['GET'])
@api_login_required
def get_cliente(id):
    c = db.session.get(Cliente, id)
    if c:
        return jsonify(c.as_dict())
    return jsonify({"message": "Cliente no encontrado"}), 404

@app.route('/api/clientes/<int:id>', methods=['PUT'])
@api_login_required
def update_cliente(id):
    c = db.session.get(Cliente, id)
    if not c:
        return jsonify({"message": "Cliente no encontrado"}), 404
    data = request.get_json()
    c.nombre     = data.get('nombre', c.nombre)
    c.apellido   = data.get('apellido', c.apellido)
    c.telefono   = data.get('telefono', c.telefono)
    c.email      = data.get('email', c.email)
    c.tipo       = data.get('tipo', c.tipo)
    c.rango_min  = data.get('rango_min', c.rango_min)
    c.rango_max  = data.get('rango_max', c.rango_max)
    c.es_usd     = data.get('es_usd', c.es_usd)
    c.ambientes  = data.get('ambientes', c.ambientes)
    c.operacion  = data.get('operacion', c.operacion)
    c.descripcion = data.get('descripcion', c.descripcion)
    db.session.commit()
    return jsonify({"message": "Cliente actualizado"})

@app.route('/api/clientes/<int:id>', methods=['DELETE'])
@api_login_required
def delete_cliente(id):
    c = db.session.get(Cliente, id)
    if c:
        c.deleted_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"message": "Cliente eliminado"})
    return jsonify({"message": "Cliente no encontrado"}), 404

@app.route('/api/clientes/<int:id>/restore', methods=['PUT'])
@api_login_required
def restore_cliente(id):
    c = db.session.get(Cliente, id)
    if c:
        c.deleted_at = None
        db.session.commit()
        return jsonify({"message": "Cliente restaurado"})
    return jsonify({"message": "Cliente no encontrado"}), 404

@app.route('/api/clientes/<int:id>/upload', methods=['POST'])
@api_login_required
def upload_foto_cliente(id):
    c = db.session.get(Cliente, id)
    if not c:
        return jsonify({"message": "Cliente no encontrado"}), 404
    if 'file' not in request.files:
        return jsonify({"message": "No se envió archivo"}), 400
    file = request.files['file']
    if not allowed_file(file):
        return jsonify({"message": "Formato no permitido"}), 400
    filename = _unique_filename(f"cli_{id}", file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    _save_image(file, filepath)
    c.fotos = (c.fotos + ',' + filepath) if c.fotos else filepath
    db.session.commit()
    return jsonify(c.as_dict()), 200

# ── Admin API: Consultas ──────────────────────────────────────────────────────

@app.route('/api/consultas', methods=['GET'])
@api_login_required
def get_consultas():
    consultas = Consulta.query.order_by(Consulta.fecha.desc()).all()
    return jsonify([c.as_dict() for c in consultas])

@app.route('/api/consultas/no_leidas', methods=['GET'])
@api_login_required
def consultas_no_leidas():
    count = Consulta.query.filter_by(leida=False).count()
    return jsonify({"count": count})

@app.route('/api/consultas/<int:id>/leer', methods=['PUT'])
@api_login_required
def marcar_leida(id):
    c = db.session.get(Consulta, id)
    if not c:
        return jsonify({"error": "No encontrada"}), 404
    c.leida = True
    db.session.commit()
    return jsonify({"message": "Marcada como leída"})

@app.route('/api/consultas/<int:id>', methods=['DELETE'])
@api_login_required
def delete_consulta(id):
    c = db.session.get(Consulta, id)
    if not c:
        return jsonify({"error": "No encontrada"}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "Eliminada"})

# ── Init ──────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()
    with db.engine.connect() as _conn:
        for _ddl in [
            "ALTER TABLE propiedades ADD COLUMN deleted_at DATETIME",
            "ALTER TABLE clientes ADD COLUMN deleted_at DATETIME",
        ]:
            try:
                _conn.execute(db.text(_ddl))
                _conn.commit()
            except Exception:
                pass

if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', False))
