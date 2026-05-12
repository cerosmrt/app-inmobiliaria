from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_migrate import Migrate
from models import db, Propiedad, Cliente, Admin, Consulta
from config import config as app_config
from functools import wraps
from dotenv import load_dotenv
load_dotenv()
import os
import hmac
import secrets
import time
import uuid
import threading
import smtplib
import ssl
from email.mime.text import MIMEText
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

def _foto_path(filename: str) -> str:
    """Return a forward-slash photo path for URL-safe DB storage."""
    return '/'.join([app.config['UPLOAD_FOLDER'], filename])

def _normalize_foto(path: str) -> str:
    """Normalize stored path: forward slashes, no leading slash."""
    return path.replace('\\', '/').lstrip('/')

def _fotos_from_str(raw: str):
    if not raw:
        return []
    return [_normalize_foto(f) for f in raw.split(',') if f.strip()]

def _fotos_to_str(fotos: list) -> str:
    return ','.join(_normalize_foto(f) for f in fotos if f)

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
    tipo       = request.args.get('tipo', '')
    operacion  = request.args.get('operacion', '')
    ambientes  = request.args.get('ambientes', '')
    barrio     = request.args.get('barrio', '')
    precio_max = request.args.get('precio_max', '')

    query = Propiedad.query.filter_by(publicada=True).filter(Propiedad.deleted_at.is_(None))
    if tipo:
        query = query.filter(Propiedad.tipo == tipo)
    if operacion:
        query = query.filter(Propiedad.operacion == operacion)
    if ambientes:
        try:
            if ambientes.endswith('+'):
                query = query.filter(Propiedad.ambientes >= int(ambientes[:-1]))
            else:
                query = query.filter(Propiedad.ambientes == int(ambientes))
        except ValueError:
            pass
    if barrio:
        query = query.filter(db.or_(
            Propiedad.barrio.ilike(f'%{barrio}%'),
            Propiedad.direccion.ilike(f'%{barrio}%')
        ))
    if precio_max:
        try:
            pmax = float(precio_max)
            query = query.filter(db.or_(
                Propiedad.precio_a_consultar == True,
                Propiedad.es_usd == False,
                Propiedad.rango_min <= pmax
            ))
        except ValueError:
            pass

    return jsonify([p.as_dict() for p in query.order_by(
        Propiedad.destacada.desc(), Propiedad.id.desc()
    ).all()])

@app.route('/api/public/propiedades/<int:id>')
def api_public_propiedad(id):
    p = Propiedad.query.filter_by(id=id, publicada=True).filter(Propiedad.deleted_at.is_(None)).first()
    if not p:
        return jsonify({"error": "Propiedad no encontrada"}), 404
    return jsonify(p.as_dict())

def _send_consulta_email(data, prop_info, host_url):
    smtp_host = app.config.get('MAIL_SMTP', '')
    smtp_port = app.config.get('MAIL_PORT', 587)
    smtp_user = app.config.get('MAIL_USER', '')
    smtp_pass = app.config.get('MAIL_PASS', '')
    mail_to   = app.config.get('MAIL_TO', '')
    if not all([smtp_host, smtp_user, smtp_pass, mail_to]):
        return
    prop_line = ''
    if prop_info:
        prop_line = (
            f"\nPropiedad: {prop_info['direccion']}"
            + (f", {prop_info['barrio']}" if prop_info.get('barrio') else '')
            + f"\nVer propiedad: {host_url}propiedad/{prop_info['id']}"
        )
    body = (
        f"Nueva consulta recibida en Moret Inmobiliaria\n"
        f"{'─'*44}\n\n"
        f"Nombre:    {data['nombre']}\n"
        f"Teléfono:  {data.get('telefono') or '—'}\n"
        f"Email:     {data.get('email') or '—'}"
        f"{prop_line}\n\n"
        f"Mensaje:\n{data['mensaje']}\n\n"
        f"{'─'*44}\n"
        f"Ver todas las consultas: {host_url}admin/consultas\n"
    )
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = f"Nueva consulta de {data['nombre']}"
    msg['From']    = smtp_user
    msg['To']      = mail_to
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as srv:
            srv.starttls(context=ctx)
            srv.login(smtp_user, smtp_pass)
            srv.send_message(msg)
    except Exception:
        pass

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

    prop_info = None
    if data.get('propiedad_id'):
        prop = Propiedad.query.get(data['propiedad_id'])
        if prop:
            prop_info = {'id': prop.id, 'direccion': prop.direccion, 'barrio': prop.barrio}
    host_url = request.host_url
    threading.Thread(
        target=_send_consulta_email,
        args=(data, prop_info, host_url),
        daemon=True
    ).start()

    return jsonify({"message": "Consulta enviada correctamente"}), 201

# ── Admin API: Propiedades ────────────────────────────────────────────────────

@app.route('/api/propiedades', methods=['GET'])
@api_login_required
def get_propiedades():
    tipo       = request.args.get('tipo', '')
    propietario = request.args.get('propietario', '')
    interesado  = request.args.get('interesado', '')
    codigo      = request.args.get('codigo', '')

    query = Propiedad.query.filter(Propiedad.deleted_at.is_(None))
    if tipo:
        query = query.filter(Propiedad.tipo.ilike(f'%{tipo}%'))
    if codigo:
        query = query.filter(Propiedad.codigo.ilike(f'%{codigo}%'))
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
        codigo=data.get('codigo'),
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
        destacada=data.get('destacada', False),
        propietario_id=data.get('propietario_id')
    )
    if 'interesados_ids' in data:
        nueva.interesados = Cliente.query.filter(Cliente.id.in_(data['interesados_ids'])).all()
    if 'propietarios_ids' in data:
        nueva.propietarios = Cliente.query.filter(Cliente.id.in_(data['propietarios_ids'])).all()
    db.session.add(nueva)
    db.session.commit()
    return jsonify(nueva.as_dict()), 201

@app.route('/api/propiedades/bulk-estado', methods=['PATCH'])
@api_login_required
def bulk_estado_propiedades():
    data   = request.get_json()
    ids    = data.get('ids', [])
    estado = data.get('estado', '')
    if not ids or not estado:
        return jsonify({'error': 'ids y estado requeridos'}), 400
    if estado not in {'disponible', 'reservada', 'vendida', 'rentada', 'cerrada'}:
        return jsonify({'error': 'estado inválido'}), 400
    now   = datetime.utcnow()
    props = Propiedad.query.filter(
        Propiedad.id.in_(ids), Propiedad.deleted_at.is_(None)
    ).all()
    for p in props:
        if p.estado != estado:
            p.estado       = estado
            p.fecha_estado = now
    db.session.commit()
    return jsonify({'updated': len(props)})

@app.route('/api/propiedades/archivados', methods=['GET'])
@api_login_required
def get_propiedades_archivadas():
    props = Propiedad.query.filter(Propiedad.deleted_at.isnot(None)).all()
    return jsonify([p.as_dict() for p in props])

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
    p.codigo           = data.get('codigo', p.codigo)
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
    p.destacada        = data.get('destacada', p.destacada)
    p.descripcion      = data.get('descripcion', p.descripcion)
    nuevo_estado = data.get('estado', p.estado)
    if nuevo_estado != p.estado:
        p.fecha_estado = datetime.utcnow()
    p.estado           = nuevo_estado
    p.propietario_id   = data.get('propietario_id', p.propietario_id)
    if 'interesados_ids' in data:
        p.interesados = Cliente.query.filter(Cliente.id.in_(data['interesados_ids'])).all()
    if 'propietarios_ids' in data:
        p.propietarios = Cliente.query.filter(Cliente.id.in_(data['propietarios_ids'])).all()
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

@app.route('/api/propiedades/<int:id>/permanente', methods=['DELETE'])
@api_login_required
def delete_propiedad_permanente(id):
    p = db.session.get(Propiedad, id)
    if not p:
        return jsonify({"message": "Propiedad no encontrada"}), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify({"message": "Eliminada permanentemente"})

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
    filepath = _foto_path(filename)                # forward-slash path
    _save_image(file, filepath)
    existing = _fotos_from_str(p.fotos)
    existing.append(_normalize_foto(filepath))
    p.fotos = _fotos_to_str(existing)
    db.session.commit()
    return jsonify(p.as_dict()), 200

@app.route('/api/propiedades/<int:id>/fotos/<path:filename>', methods=['DELETE'])
@api_login_required
def delete_foto_propiedad(id, filename):
    p = db.session.get(Propiedad, id)
    if not p:
        return jsonify({"message": "Propiedad no encontrada"}), 404
    target = _normalize_foto(filename)
    fotos = [f for f in _fotos_from_str(p.fotos) if _normalize_foto(f) != target]
    p.fotos = _fotos_to_str(fotos) if fotos else None
    db.session.commit()
    # Try to delete the physical file (both path variants)
    for candidate in [target, target.replace('/', os.sep)]:
        try:
            if os.path.exists(candidate):
                os.remove(candidate)
                break
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
    new_order = [_normalize_foto(f) for f in data.get('fotos', []) if f]
    current = set(_normalize_foto(f) for f in _fotos_from_str(p.fotos))
    if new_order and not all(f in current for f in new_order):
        return jsonify({"message": "Fotos inválidas"}), 400
    p.fotos = _fotos_to_str(new_order) if new_order else None
    db.session.commit()
    return jsonify(p.as_dict())

# ── Interesados M2M ───────────────────────────────────────────────────────────

@app.route('/api/propiedades/<int:id>/interesados/<int:cliente_id>', methods=['POST'])
@api_login_required
def add_interesado(id, cliente_id):
    p = db.session.get(Propiedad, id)
    c = db.session.get(Cliente, cliente_id)
    if not p or not c:
        return jsonify({"message": "No encontrado"}), 404
    if c not in p.interesados:
        p.interesados.append(c)
        db.session.commit()
    return jsonify(p.as_dict())

@app.route('/api/propiedades/<int:id>/interesados/<int:cliente_id>', methods=['DELETE'])
@api_login_required
def remove_interesado(id, cliente_id):
    p = db.session.get(Propiedad, id)
    c = db.session.get(Cliente, cliente_id)
    if not p or not c:
        return jsonify({"message": "No encontrado"}), 404
    if c in p.interesados:
        p.interesados.remove(c)
        db.session.commit()
    return jsonify(p.as_dict())

# ── Propietarios M2M ──────────────────────────────────────────────────────────

@app.route('/api/propiedades/<int:id>/propietarios/<int:cliente_id>', methods=['POST'])
@api_login_required
def add_propietario(id, cliente_id):
    p = db.session.get(Propiedad, id)
    c = db.session.get(Cliente, cliente_id)
    if not p or not c:
        return jsonify({"message": "No encontrado"}), 404
    if c not in p.propietarios:
        p.propietarios.append(c)
        db.session.commit()
    return jsonify(p.as_dict())

@app.route('/api/propiedades/<int:id>/propietarios/<int:cliente_id>', methods=['DELETE'])
@api_login_required
def remove_propietario(id, cliente_id):
    p = db.session.get(Propiedad, id)
    c = db.session.get(Cliente, cliente_id)
    if not p or not c:
        return jsonify({"message": "No encontrado"}), 404
    if c in p.propietarios:
        p.propietarios.remove(c)
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

@app.route('/api/clientes/archivados', methods=['GET'])
@api_login_required
def get_clientes_archivados():
    clientes = Cliente.query.filter(Cliente.deleted_at.isnot(None)).all()
    return jsonify([c.as_dict() for c in clientes])

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

@app.route('/api/clientes/<int:id>/permanente', methods=['DELETE'])
@api_login_required
def delete_cliente_permanente(id):
    c = db.session.get(Cliente, id)
    if not c:
        return jsonify({"message": "Cliente no encontrado"}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "Eliminado permanentemente"})

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
    filepath = _foto_path(filename)
    _save_image(file, filepath)
    existing = _fotos_from_str(c.fotos)
    existing.append(_normalize_foto(filepath))
    c.fotos = _fotos_to_str(existing)
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

@app.route('/api/consultas/<int:id>/responder', methods=['POST'])
@api_login_required
def responder_consulta(id):
    c = db.session.get(Consulta, id)
    if not c:
        return jsonify({'error': 'Consulta no encontrada'}), 404
    if not c.email:
        return jsonify({'error': 'Esta consulta no tiene email'}), 400
    data   = request.get_json()
    asunto = (data.get('asunto') or '').strip()
    cuerpo = (data.get('cuerpo') or '').strip()
    if not asunto or not cuerpo:
        return jsonify({'error': 'Asunto y mensaje requeridos'}), 400
    smtp_host = app.config.get('MAIL_SMTP', '')
    smtp_port = app.config.get('MAIL_PORT', 587)
    smtp_user = app.config.get('MAIL_USER', '')
    smtp_pass = app.config.get('MAIL_PASS', '')
    if not all([smtp_host, smtp_user, smtp_pass]):
        return jsonify({'error': 'Email no configurado en el servidor'}), 503
    msg            = MIMEText(cuerpo, 'plain', 'utf-8')
    msg['Subject'] = asunto
    msg['From']    = smtp_user
    msg['To']      = c.email
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as srv:
            srv.starttls(context=ctx)
            srv.login(smtp_user, smtp_pass)
            srv.send_message(msg)
        return jsonify({'message': 'Respuesta enviada'})
    except Exception as e:
        return jsonify({'error': f'Error al enviar: {e}'}), 500

@app.route('/api/consultas/<int:id>', methods=['DELETE'])
@api_login_required
def delete_consulta(id):
    c = db.session.get(Consulta, id)
    if not c:
        return jsonify({"error": "No encontrada"}), 404
    db.session.delete(c)
    db.session.commit()
    return jsonify({"message": "Eliminada"})

@app.route('/api/stats', methods=['GET'])
@api_login_required
def get_stats():
    base = Propiedad.query.filter(Propiedad.deleted_at.is_(None))
    return jsonify({
        'disponibles':          base.filter_by(estado='disponible').count(),
        'reservadas':           base.filter_by(estado='reservada').count(),
        'vendidas':             base.filter_by(estado='vendida').count(),
        'rentadas':             base.filter_by(estado='rentada').count(),
        'cerradas':             base.filter_by(estado='cerrada').count(),
        'publicadas':           base.filter_by(publicada=True).count(),
        'clientes':             Cliente.query.filter(Cliente.deleted_at.is_(None)).count(),
        'consultas_no_leidas':  Consulta.query.filter_by(leida=False).count(),
    })

# ── Init ──────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()
    with db.engine.connect() as _conn:
        for _ddl in [
            "ALTER TABLE propiedades ADD COLUMN deleted_at DATETIME",
            "ALTER TABLE clientes ADD COLUMN deleted_at DATETIME",
            "ALTER TABLE propiedades ADD COLUMN codigo VARCHAR",
        ]:
            try:
                _conn.execute(db.text(_ddl))
                _conn.commit()
            except Exception:
                pass
        # Migrate existing propietario_id to propietarios M2M
        try:
            rows = _conn.execute(db.text(
                "SELECT id, propietario_id FROM propiedades WHERE propietario_id IS NOT NULL"
            )).fetchall()
            for row in rows:
                try:
                    _conn.execute(db.text(
                        "INSERT OR IGNORE INTO propietarios_propiedades (propiedad_id, cliente_id) VALUES (:pid, :cid)"
                    ), {"pid": row[0], "cid": row[1]})
                except Exception:
                    pass
            _conn.commit()
        except Exception:
            pass
        # Normalize backslash foto paths in DB
        try:
            rows = _conn.execute(db.text("SELECT id, fotos FROM propiedades WHERE fotos LIKE '%\\\\%'")).fetchall()
            for row in rows:
                fixed = row[1].replace('\\', '/')
                _conn.execute(db.text("UPDATE propiedades SET fotos=:f WHERE id=:i"), {"f": fixed, "i": row[0]})
            rows2 = _conn.execute(db.text("SELECT id, fotos FROM clientes WHERE fotos LIKE '%\\\\%'")).fetchall()
            for row in rows2:
                fixed = row[1].replace('\\', '/')
                _conn.execute(db.text("UPDATE clientes SET fotos=:f WHERE id=:i"), {"f": fixed, "i": row[0]})
            _conn.commit()
        except Exception:
            pass

if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', False))
