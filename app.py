from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_migrate import Migrate
from models import db, Propiedad, Cliente, Admin, Consulta, CaptacionLead, PropietarioLead, CaptacionActividad, ParcelaCatastral, OportunidadTerreno, InvestigacionPropietario, PropietarioCatastral, ActividadParcela
from config import config as app_config
from functools import wraps
from dotenv import load_dotenv
load_dotenv()
import os
import io
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

for folder in [app.config['UPLOAD_FOLDER'], 'static/uploads/properties', 'static/uploads/properties/thumbs', 'templates', 'static']:
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
_WEBP_MAGIC = b'RIFF'          # WebP: bytes 0-3 == RIFF, bytes 8-11 == WEBP

_PROPS_FOLDER  = 'static/uploads/properties'
_THUMBS_FOLDER = 'static/uploads/properties/thumbs'
_WEBP_QUALITY  = 82
_MAX_DIMENSION = 1920
_THUMB_WIDTH   = 480

def allowed_file(file) -> bool:
    if not file or not file.filename:
        return False
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in app.config['ALLOWED_EXTENSIONS']:
        return False
    header = file.read(12)
    file.seek(0)
    return (header[:3] == _JPEG_MAGIC or
            header[:4] == _PNG_MAGIC or
            (header[:4] == _WEBP_MAGIC and header[8:12] == b'WEBP'))

def _unique_filename(prefix: str, original: str) -> str:
    ext = secure_filename(original).rsplit('.', 1)[-1].lower()
    return f"{prefix}_{uuid.uuid4().hex[:10]}.{ext}"

def _save_image(file, filepath: str) -> None:
    """Legacy save used by client photo uploads."""
    if not _PILLOW:
        file.save(filepath)
        return
    try:
        img = _PillowImage.open(file)
        if img.width > _MAX_DIMENSION or img.height > _MAX_DIMENSION:
            img.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), _PillowImage.LANCZOS)
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

def _thumb_path_for(full_path: str):
    """Return the thumbnail path for a property image, or None for legacy paths."""
    norm = _normalize_foto(full_path)
    prefix = _PROPS_FOLDER + '/'
    if norm.startswith(prefix):
        return _THUMBS_FOLDER + '/' + norm[len(prefix):]
    return None

def _optimize_and_save(file, full_path: str, thumb_path: str) -> None:
    """Convert upload to WebP at two sizes. Falls back to raw save on error."""
    # Read all bytes up front — decouples PIL from the werkzeug stream entirely
    raw = file.read()
    file.seek(0)
    if not _PILLOW:
        with open(full_path.replace('/', os.sep), 'wb') as f:
            f.write(raw)
        return
    try:
        from PIL import ImageOps
        img = _PillowImage.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)  # auto-orient from EXIF
        if img.mode != 'RGB':
            img = img.convert('RGB')
        if img.width > _MAX_DIMENSION or img.height > _MAX_DIMENSION:
            img.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), _PillowImage.LANCZOS)
        buf_full = io.BytesIO()
        img.save(buf_full, 'WEBP', quality=_WEBP_QUALITY, method=6)
        with open(full_path.replace('/', os.sep), 'wb') as f:
            f.write(buf_full.getvalue())
        thumb = img.copy()
        if thumb.width > _THUMB_WIDTH:
            new_h = int(thumb.height * _THUMB_WIDTH / thumb.width)
            thumb = thumb.resize((_THUMB_WIDTH, new_h), _PillowImage.LANCZOS)
        buf_thumb = io.BytesIO()
        thumb.save(buf_thumb, 'WEBP', quality=_WEBP_QUALITY, method=6)
        with open(thumb_path.replace('/', os.sep), 'wb') as f:
            f.write(buf_thumb.getvalue())
    except Exception as e:
        app.logger.warning('Image optimization failed, saving original: %s', e)
        with open(full_path.replace('/', os.sep), 'wb') as f:
            f.write(raw)

def _save_photo(file, prefix: str) -> str:
    """Save a property photo optimized as WebP. Returns the forward-slash full path."""
    uid        = uuid.uuid4().hex[:10]
    filename   = f"{prefix}_{uid}.webp"
    full_path  = f"{_PROPS_FOLDER}/{filename}"
    thumb_path = f"{_THUMBS_FOLDER}/{filename}"
    _optimize_and_save(file, full_path, thumb_path)
    return full_path

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
        superficie_terreno=data.get('superficie_terreno'),
        superficie_cubierta=data.get('superficie_cubierta'),
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

@app.route('/api/propiedades/geojson', methods=['GET'])
@api_login_required
def get_propiedades_geojson():
    import json as _json
    props = Propiedad.query.filter(
        Propiedad.deleted_at.is_(None),
        db.or_(Propiedad.lat.isnot(None), Propiedad.geojson_geometry.isnot(None))
    ).all()
    features = []
    for p in props:
        if p.geojson_geometry:
            try:
                geometry = _json.loads(p.geojson_geometry)
                tipo_geometria = 'poligono'
            except Exception:
                continue
        elif p.lat is not None and p.lng is not None:
            geometry = {'type': 'Point', 'coordinates': [p.lng, p.lat]}
            tipo_geometria = 'punto'
        else:
            continue
        precio = p.rango_max or p.rango_min
        features.append({
            'type': 'Feature',
            'geometry': geometry,
            'properties': {
                'id': p.id,
                'titulo': p.direccion or f'Propiedad #{p.id}',
                'tipo': p.tipo or '',
                'operacion': p.operacion or '',
                'precio': precio,
                'es_usd': p.es_usd,
                'precio_a_consultar': p.precio_a_consultar,
                'estado': p.estado or '',
                'direccion': p.direccion or '',
                'tipo_geometria': tipo_geometria,
            }
        })
    return jsonify({'type': 'FeatureCollection', 'features': features})

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
    p.ambientes            = data.get('ambientes', p.ambientes)
    p.superficie_terreno   = data.get('superficie_terreno', p.superficie_terreno)
    p.superficie_cubierta  = data.get('superficie_cubierta', p.superficie_cubierta)
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
    full_path = _save_photo(file, f"prop_{id}")
    existing = _fotos_from_str(p.fotos)
    existing.append(full_path)
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
        except OSError as e:
            app.logger.warning('Could not delete photo file %s: %s', candidate, e)
    # Delete thumbnail if present (new-style photos only)
    thumb = _thumb_path_for(target)
    if thumb:
        for candidate in [thumb, thumb.replace('/', os.sep)]:
            try:
                if os.path.exists(candidate):
                    os.remove(candidate)
                    break
            except OSError as e:
                app.logger.warning('Could not delete thumb file %s: %s', candidate, e)
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

# ── Geometry ─────────────────────────────────────────────────────────────────

@app.route('/api/propiedades/<int:id>/geometry', methods=['POST'])
@api_login_required
def set_propiedad_geometry(id):
    import json as _json
    p = db.session.get(Propiedad, id)
    if not p:
        return jsonify({"message": "Propiedad no encontrada"}), 404
    data = request.get_json() or {}

    if data.get('clear'):
        p.lat = None
        p.lng = None
        p.geojson_geometry = None
    elif 'geojson_geometry' in data:
        geom_str = data['geojson_geometry']
        if not isinstance(geom_str, str):
            return jsonify({"message": "geojson_geometry debe ser string JSON"}), 400
        try:
            _json.loads(geom_str)
        except Exception:
            return jsonify({"message": "geojson_geometry inválido"}), 400
        p.geojson_geometry = geom_str
        p.lat = None
        p.lng = None
    elif 'lat' in data and 'lng' in data:
        try:
            lat = float(data['lat'])
            lng = float(data['lng'])
        except (TypeError, ValueError):
            return jsonify({"message": "lat y lng deben ser números"}), 400
        p.lat = lat
        p.lng = lng
        p.geojson_geometry = None
    else:
        return jsonify({"message": "Requerido: lat+lng, geojson_geometry, o clear:true"}), 400

    db.session.commit()
    return jsonify(p.as_dict())

@app.route('/api/propiedades/<int:id>/geocode', methods=['POST'])
@api_login_required
def geocode_propiedad(id):
    import urllib.request as _ureq2
    import urllib.parse   as _uparse2
    import json           as _json2
    p = db.session.get(Propiedad, id)
    if not p:
        return jsonify({'success': False, 'reason': 'Propiedad no encontrada'}), 404
    if not p.direccion:
        return jsonify({'success': False, 'reason': 'Sin dirección'})
    if p.lat is not None or p.geojson_geometry:
        return jsonify({'success': False, 'reason': 'Ya tiene geometría'})
    q = p.direccion
    if p.barrio:
        q += ', ' + p.barrio
    q += ', Argentina'
    url = 'https://nominatim.openstreetmap.org/search?' + _uparse2.urlencode(
        {'q': q, 'format': 'json', 'limit': 1}
    )
    try:
        req = _ureq2.Request(url, headers={'User-Agent': 'MoretInmobiliaria/1.0'})
        with _ureq2.urlopen(req, timeout=8) as r:
            results = _json2.loads(r.read().decode('utf-8'))
    except Exception as e:
        return jsonify({'success': False, 'reason': str(e)})
    if not results:
        return jsonify({'success': False, 'reason': 'Sin resultados'})
    p.lat = float(results[0]['lat'])
    p.lng = float(results[0]['lon'])
    db.session.commit()
    return jsonify({'success': True, 'lat': p.lat, 'lng': p.lng})

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

# ── Captacion admin page ─────────────────────────────────────────────────────

@app.route('/admin/captacion')
@login_required
def admin_captacion():
    return render_template('admin/captacion.html')

# ── Captacion API: Leads ──────────────────────────────────────────────────────

@app.route('/api/captacion/leads', methods=['GET'])
@api_login_required
def get_leads():
    q         = request.args.get('q', '').strip()
    estado    = request.args.get('estado', '')
    prioridad = request.args.get('prioridad', '')
    query = CaptacionLead.query.filter(CaptacionLead.deleted_at.is_(None))
    if estado:
        query = query.filter_by(estado=estado)
    if prioridad:
        query = query.filter_by(prioridad=prioridad)
    if q:
        query = query.filter(db.or_(
            CaptacionLead.direccion.ilike(f'%{q}%'),
            CaptacionLead.barrio.ilike(f'%{q}%'),
            CaptacionLead.ciudad.ilike(f'%{q}%'),
        ))
    leads = query.order_by(CaptacionLead.fecha_creacion.desc()).all()
    return jsonify([l.as_dict() for l in leads])

@app.route('/api/captacion/leads', methods=['POST'])
@api_login_required
def create_lead():
    data = request.get_json()
    if not data.get('direccion'):
        return jsonify({"error": "Dirección requerida"}), 400
    lead = CaptacionLead(
        direccion=data['direccion'].strip(),
        barrio=data.get('barrio') or None,
        ciudad=data.get('ciudad') or None,
        tipo_propiedad=data.get('tipo_propiedad') or None,
        operacion=data.get('operacion') or None,
        estado=data.get('estado', 'detectada'),
        prioridad=data.get('prioridad', 'media'),
        potencial=int(data.get('potencial', 3)),
        fuente=data.get('fuente') or None,
        descripcion=data.get('descripcion') or None,
        notas=data.get('notas') or None,
        created_by=session.get('admin_username'),
        ultima_interaccion=datetime.utcnow(),
        proximo_seguimiento=datetime.fromisoformat(data['proximo_seguimiento']) if data.get('proximo_seguimiento') else None,
    )
    db.session.add(lead)
    db.session.flush()
    prop = data.get('propietario') or {}
    if prop.get('nombre') or prop.get('telefono'):
        db.session.add(PropietarioLead(
            lead_id=lead.id,
            nombre=prop.get('nombre') or None,
            telefono=prop.get('telefono') or None,
            email=prop.get('email') or None,
            whatsapp=prop.get('whatsapp') or None,
            observaciones=prop.get('observaciones') or None,
        ))
    db.session.commit()
    return jsonify(lead.as_dict()), 201

@app.route('/api/captacion/leads/<int:id>', methods=['GET'])
@api_login_required
def get_lead(id):
    lead = db.session.get(CaptacionLead, id)
    if not lead or lead.deleted_at:
        return jsonify({"error": "No encontrado"}), 404
    return jsonify(lead.as_dict())

@app.route('/api/captacion/leads/<int:id>', methods=['PATCH'])
@api_login_required
def update_lead(id):
    lead = db.session.get(CaptacionLead, id)
    if not lead or lead.deleted_at:
        return jsonify({"error": "No encontrado"}), 404
    data = request.get_json()
    for f in ['direccion', 'barrio', 'ciudad', 'tipo_propiedad', 'operacion',
              'estado', 'prioridad', 'potencial', 'fuente', 'descripcion', 'notas']:
        if f in data:
            setattr(lead, f, data[f])
    if 'proximo_seguimiento' in data:
        lead.proximo_seguimiento = datetime.fromisoformat(data['proximo_seguimiento']) if data['proximo_seguimiento'] else None
    lead.ultima_interaccion = datetime.utcnow()
    prop = data.get('propietario')
    if prop is not None:
        if lead.propietario:
            for f in ['nombre', 'telefono', 'email', 'whatsapp', 'observaciones']:
                if f in prop:
                    setattr(lead.propietario, f, prop[f] or None)
        else:
            db.session.add(PropietarioLead(lead_id=lead.id, **{
                f: prop.get(f) or None for f in ['nombre', 'telefono', 'email', 'whatsapp', 'observaciones']
            }))
    db.session.commit()
    return jsonify(lead.as_dict())

@app.route('/api/captacion/leads/<int:id>', methods=['DELETE'])
@api_login_required
def delete_lead(id):
    lead = db.session.get(CaptacionLead, id)
    if not lead:
        return jsonify({"error": "No encontrado"}), 404
    lead.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Lead eliminado"})

# ── Captacion API: Actividades ────────────────────────────────────────────────

@app.route('/api/captacion/leads/<int:id>/actividades', methods=['POST'])
@api_login_required
def add_actividad(id):
    lead = db.session.get(CaptacionLead, id)
    if not lead or lead.deleted_at:
        return jsonify({"error": "No encontrado"}), 404
    data = request.get_json()
    if not data.get('tipo'):
        return jsonify({"error": "Tipo requerido"}), 400
    act = CaptacionActividad(
        lead_id=id,
        tipo=data['tipo'],
        descripcion=data.get('descripcion', '') or '',
        fecha=datetime.utcnow(),
        created_by=session.get('admin_username'),
    )
    db.session.add(act)
    lead.ultima_interaccion = datetime.utcnow()
    db.session.commit()
    return jsonify(act.as_dict()), 201

@app.route('/api/captacion/leads/<int:id>/actividades/<int:act_id>', methods=['DELETE'])
@api_login_required
def delete_actividad(id, act_id):
    act = db.session.get(CaptacionActividad, act_id)
    if not act or act.lead_id != id:
        return jsonify({"error": "No encontrado"}), 404
    db.session.delete(act)
    db.session.commit()
    return jsonify({"message": "Actividad eliminada"})

# ── Captacion API: Conversión ─────────────────────────────────────────────────

@app.route('/api/captacion/leads/<int:id>/convertir', methods=['POST'])
@api_login_required
def convertir_lead(id):
    lead = db.session.get(CaptacionLead, id)
    if not lead or lead.deleted_at:
        return jsonify({"error": "No encontrado"}), 404
    prop = Propiedad(
        direccion=lead.direccion,
        barrio=lead.barrio,
        tipo=lead.tipo_propiedad or 'otro',
        operacion=lead.operacion,
        estado='disponible',
        descripcion=lead.descripcion,
    )
    db.session.add(prop)
    if lead.propietario and lead.propietario.nombre:
        parts = lead.propietario.nombre.strip().split(' ', 1)
        cliente = Cliente(
            nombre=parts[0],
            apellido=parts[1] if len(parts) > 1 else '',
            telefono=lead.propietario.telefono or '',
            email=lead.propietario.email,
            tipo='propietario',
        )
        db.session.add(cliente)
        db.session.flush()
        prop.propietarios.append(cliente)
    db.session.flush()
    lead.estado = 'captada'
    lead.ultima_interaccion = datetime.utcnow()
    db.session.add(CaptacionActividad(
        lead_id=id,
        tipo='conversion',
        descripcion=f'Convertido a propiedad #{prop.id}',
        created_by=session.get('admin_username'),
    ))
    db.session.commit()
    return jsonify({'message': 'Convertido', 'propiedad_id': prop.id})

# ── Captacion API: Seguimientos ───────────────────────────────────────────────

@app.route('/api/captacion/seguimientos', methods=['GET'])
@api_login_required
def get_seguimientos():
    leads = CaptacionLead.query.filter(
        CaptacionLead.deleted_at.is_(None),
        CaptacionLead.proximo_seguimiento.isnot(None),
        CaptacionLead.estado.notin_(['captada', 'descartada']),
    ).order_by(CaptacionLead.proximo_seguimiento).all()
    return jsonify([l.as_dict() for l in leads])

# ── Captacion API: Import CSV ─────────────────────────────────────────────────

@app.route('/api/captacion/import', methods=['POST'])
@api_login_required
def import_leads():
    if 'file' not in request.files:
        return jsonify({"error": "No se envió archivo"}), 400
    import csv as _csv, io as _io2
    content = request.files['file'].read().decode('utf-8-sig')
    reader  = _csv.DictReader(_io2.StringIO(content))
    created, errors = 0, []
    for i, row in enumerate(reader):
        try:
            lead = CaptacionLead(
                direccion=row.get('direccion', '').strip() or 'Sin dirección',
                barrio=row.get('barrio', '').strip() or None,
                ciudad=row.get('ciudad', '').strip() or None,
                tipo_propiedad=row.get('tipo_propiedad', '').strip() or None,
                operacion=row.get('operacion', '').strip() or None,
                estado=row.get('estado', 'detectada').strip() or 'detectada',
                prioridad=row.get('prioridad', 'media').strip() or 'media',
                fuente=row.get('fuente', '').strip() or None,
                descripcion=row.get('descripcion', '').strip() or None,
                created_by=session.get('admin_username'),
                ultima_interaccion=datetime.utcnow(),
            )
            db.session.add(lead)
            db.session.flush()
            nombre = row.get('propietario_nombre', '').strip()
            if nombre:
                db.session.add(PropietarioLead(
                    lead_id=lead.id,
                    nombre=nombre,
                    telefono=row.get('propietario_telefono', '').strip() or None,
                    email=row.get('propietario_email', '').strip() or None,
                    whatsapp=row.get('propietario_whatsapp', '').strip() or None,
                ))
            created += 1
        except Exception as e:
            errors.append(f"Fila {i+2}: {e}")
    db.session.commit()
    return jsonify({"created": created, "errors": errors})

# ── Catastro admin page ──────────────────────────────────────────────────────

@app.route('/admin/catastro')
@login_required
def admin_catastro():
    return render_template('admin/catastro.html')

# ── Catastro API: Parcelas ────────────────────────────────────────────────────

@app.route('/api/catastro/parcelas', methods=['GET'])
@api_login_required
def get_parcelas():
    q = request.args.get('q', '').strip()
    query = ParcelaCatastral.query.filter(ParcelaCatastral.deleted_at.is_(None))
    if q:
        query = query.filter(db.or_(
            ParcelaCatastral.municipality.ilike(f'%{q}%'),
            ParcelaCatastral.province.ilike(f'%{q}%'),
            ParcelaCatastral.zone.ilike(f'%{q}%'),
            ParcelaCatastral.parcel_id.ilike(f'%{q}%'),
        ))
    return jsonify([p.as_dict() for p in query.order_by(ParcelaCatastral.created_at.desc()).all()])

@app.route('/api/catastro/parcelas', methods=['POST'])
@api_login_required
def create_parcela():
    data = request.get_json()
    lat  = data.get('lat')
    lng  = data.get('lng')
    p = ParcelaCatastral(
        parcel_id=data.get('parcel_id') or None,
        geojson_geometry=data.get('geojson_geometry') or None,
        surface_area=float(data['surface_area']) if data.get('surface_area') else None,
        zone=data.get('zone') or None,
        municipality=data.get('municipality') or None,
        province=data.get('province') or None,
        coordinates_center=f"{lat},{lng}" if lat is not None and lng is not None else None,
        land_use=data.get('land_use') or None,
        notes=data.get('notes') or None,
        source_provider=data.get('source_provider', 'manual'),
        propietario_id=data.get('propietario_id') or None,
    )
    db.session.add(p)
    db.session.flush()
    if data.get('create_oportunidad'):
        db.session.add(OportunidadTerreno(
            parcela_id=p.id,
            estado=data.get('estado', 'sin_evaluar'),
            prioridad=data.get('prioridad', 'media'),
            potencial=int(data.get('potencial', 3)),
            descripcion=data.get('descripcion') or None,
            created_by=session.get('admin_username'),
            ultima_interaccion=datetime.utcnow(),
        ))
    db.session.commit()
    return jsonify(p.as_dict()), 201

@app.route('/api/catastro/parcelas/<int:id>', methods=['GET'])
@api_login_required
def get_parcela(id):
    p = db.session.get(ParcelaCatastral, id)
    if not p or p.deleted_at:
        return jsonify({"error": "No encontrada"}), 404
    return jsonify(p.as_dict())

@app.route('/api/catastro/parcelas/<int:id>', methods=['PATCH'])
@api_login_required
def update_parcela(id):
    p = db.session.get(ParcelaCatastral, id)
    if not p or p.deleted_at:
        return jsonify({"error": "No encontrada"}), 404
    data = request.get_json()
    if 'propietario_id' in data:
        p.propietario_id = data['propietario_id'] or None
    for f in ['parcel_id', 'zone', 'municipality', 'province', 'land_use', 'notes', 'geojson_geometry', 'source_provider', 'bbox', 'neighbor_cache']:
        if f in data:
            setattr(p, f, data[f] or None)
    if 'surface_area' in data:
        p.surface_area = float(data['surface_area']) if data['surface_area'] else None
    if 'lat' in data and 'lng' in data:
        p.coordinates_center = f"{data['lat']},{data['lng']}"
    op = data.get('oportunidad')
    if op is not None:
        if p.oportunidad:
            for f in ['estado', 'prioridad', 'descripcion', 'observaciones']:
                if f in op:
                    setattr(p.oportunidad, f, op[f] or None)
            if 'potencial' in op:
                p.oportunidad.potencial = int(op['potencial'])
            if 'proximo_seguimiento' in op:
                p.oportunidad.proximo_seguimiento = (
                    datetime.fromisoformat(op['proximo_seguimiento']) if op['proximo_seguimiento'] else None
                )
            p.oportunidad.ultima_interaccion = datetime.utcnow()
        else:
            db.session.add(OportunidadTerreno(
                parcela_id=p.id,
                estado=op.get('estado', 'sin_evaluar'),
                prioridad=op.get('prioridad', 'media'),
                potencial=int(op.get('potencial', 3)),
                descripcion=op.get('descripcion') or None,
                created_by=session.get('admin_username'),
                ultima_interaccion=datetime.utcnow(),
            ))
    db.session.commit()
    return jsonify(p.as_dict())

@app.route('/api/catastro/parcelas/<int:id>', methods=['DELETE'])
@api_login_required
def delete_parcela(id):
    p = db.session.get(ParcelaCatastral, id)
    if not p:
        return jsonify({"error": "No encontrada"}), 404
    p.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"message": "Parcela eliminada"})

# ── Catastro API: Investigaciones ─────────────────────────────────────────────

@app.route('/api/catastro/parcelas/<int:id>/investigaciones', methods=['POST'])
@api_login_required
def add_investigacion(id):
    p = db.session.get(ParcelaCatastral, id)
    if not p or p.deleted_at:
        return jsonify({"error": "No encontrada"}), 404
    data = request.get_json()
    inv = InvestigacionPropietario(
        parcela_id=id,
        nombre=data.get('nombre') or None,
        telefono=data.get('telefono') or None,
        email=data.get('email') or None,
        fuente_informacion=data.get('fuente_informacion') or None,
        notas=data.get('notas') or None,
        fecha=datetime.utcnow(),
    )
    db.session.add(inv)
    db.session.commit()
    return jsonify(inv.as_dict()), 201

@app.route('/api/catastro/investigaciones/<int:inv_id>', methods=['DELETE'])
@api_login_required
def delete_investigacion(inv_id):
    inv = db.session.get(InvestigacionPropietario, inv_id)
    if not inv:
        return jsonify({"error": "No encontrada"}), 404
    db.session.delete(inv)
    db.session.commit()
    return jsonify({"message": "Eliminada"})

# ── Catastro API: Convert to Captacion lead ───────────────────────────────────

@app.route('/api/catastro/parcelas/<int:id>/convertir-lead', methods=['POST'])
@api_login_required
def convertir_parcela_lead(id):
    p = db.session.get(ParcelaCatastral, id)
    if not p or p.deleted_at:
        return jsonify({"error": "No encontrada"}), 404
    parts = [p.municipality, p.province]
    direccion = ' — '.join(filter(None, parts)) or f'Parcela #{p.parcel_id or p.id}'
    notes_extra = f'Superficie: {p.surface_area} ha\n' if p.surface_area else ''
    lead = CaptacionLead(
        direccion=direccion,
        barrio=p.zone,
        ciudad=p.municipality,
        tipo_propiedad='terreno',
        operacion='venta',
        estado='detectada',
        prioridad=p.oportunidad.prioridad if p.oportunidad else 'media',
        potencial=p.oportunidad.potencial if p.oportunidad else 3,
        descripcion=notes_extra + (p.notes or ''),
        fuente='Catastro',
        created_by=session.get('admin_username'),
        ultima_interaccion=datetime.utcnow(),
    )
    db.session.add(lead)
    db.session.flush()
    if p.investigaciones:
        inv = p.investigaciones[0]
        db.session.add(PropietarioLead(
            lead_id=lead.id,
            nombre=inv.nombre,
            telefono=inv.telefono,
            email=inv.email,
        ))
    db.session.commit()
    return jsonify({'message': 'Lead creado', 'lead_id': lead.id})

# ── Catastro API: GeoJSON export ──────────────────────────────────────────────

@app.route('/api/catastro/geojson', methods=['GET'])
@api_login_required
def export_geojson():
    import json as _json
    parcelas = ParcelaCatastral.query.filter(ParcelaCatastral.deleted_at.is_(None)).all()
    features = []
    for p in parcelas:
        geom = None
        if p.geojson_geometry:
            try:
                geom = _json.loads(p.geojson_geometry)
            except Exception:
                pass
        if not geom and p.coordinates_center:
            try:
                lat, lng = p.coordinates_center.split(',')
                geom = {'type': 'Point', 'coordinates': [float(lng), float(lat)]}
            except Exception:
                pass
        if geom:
            op = p.oportunidad
            features.append({
                'type': 'Feature',
                'geometry': geom,
                'properties': {
                    'id': p.id, 'parcel_id': p.parcel_id,
                    'municipality': p.municipality, 'surface_area': p.surface_area,
                    'estado': op.estado if op else None,
                    'potencial': op.potencial if op else None,
                }
            })
    return jsonify({'type': 'FeatureCollection', 'features': features})

# ── Catastro API: GeoJSON import ──────────────────────────────────────────────

@app.route('/api/catastro/import-geojson', methods=['POST'])
@api_login_required
def import_geojson():
    import json as _json
    if 'file' not in request.files:
        return jsonify({"error": "No se envió archivo"}), 400
    try:
        data = _json.loads(request.files['file'].read().decode('utf-8'))
    except Exception as e:
        return jsonify({"error": f"JSON inválido: {e}"}), 400
    features = data.get('features', []) if data.get('type') == 'FeatureCollection' else [data]
    created, errors = 0, []
    for i, feat in enumerate(features):
        try:
            geom  = feat.get('geometry') or {}
            props = feat.get('properties') or {}
            coords_center = None
            if geom.get('type') == 'Point':
                c = geom['coordinates']
                coords_center = f"{c[1]},{c[0]}"
            elif geom.get('type') in ('Polygon', 'MultiPolygon'):
                all_c = (geom['coordinates'][0] if geom['type'] == 'Polygon'
                         else [c for ring in geom['coordinates'] for c in ring[0]])
                if all_c:
                    coords_center = f"{sum(c[1] for c in all_c)/len(all_c)},{sum(c[0] for c in all_c)/len(all_c)}"
            db.session.add(ParcelaCatastral(
                parcel_id=str(props.get('id') or props.get('parcel_id') or '') or None,
                geojson_geometry=_json.dumps(geom) if geom else None,
                surface_area=float(props['surface_area']) if props.get('surface_area') else None,
                zone=str(props.get('zone') or props.get('zona') or '') or None,
                municipality=str(props.get('municipality') or props.get('municipio') or '') or None,
                province=str(props.get('province') or props.get('provincia') or '') or None,
                coordinates_center=coords_center,
                land_use=str(props.get('land_use') or '') or None,
                notes=str(props.get('notes') or props.get('notas') or '') or None,
                source_provider='geojson',
            ))
            created += 1
        except Exception as e:
            errors.append(f"Feature {i+1}: {e}")
    db.session.commit()
    return jsonify({"created": created, "errors": errors})

# ── Catastro API: Navigation & Explore ───────────────────────────────────────

@app.route('/api/catastro/parcelas/next/<int:id>', methods=['GET'])
@api_login_required
def next_parcela(id):
    p = ParcelaCatastral.query.filter(
        ParcelaCatastral.id > id, ParcelaCatastral.deleted_at.is_(None)
    ).order_by(ParcelaCatastral.id.asc()).first()
    if not p:
        p = ParcelaCatastral.query.filter(
            ParcelaCatastral.deleted_at.is_(None)
        ).order_by(ParcelaCatastral.id.asc()).first()
    return jsonify(p.as_dict()) if p else jsonify(None)

@app.route('/api/catastro/parcelas/prev/<int:id>', methods=['GET'])
@api_login_required
def prev_parcela(id):
    p = ParcelaCatastral.query.filter(
        ParcelaCatastral.id < id, ParcelaCatastral.deleted_at.is_(None)
    ).order_by(ParcelaCatastral.id.desc()).first()
    if not p:
        p = ParcelaCatastral.query.filter(
            ParcelaCatastral.deleted_at.is_(None)
        ).order_by(ParcelaCatastral.id.desc()).first()
    return jsonify(p.as_dict()) if p else jsonify(None)

@app.route('/api/catastro/parcelas/nearest/<int:id>', methods=['GET'])
@api_login_required
def nearest_parcelas(id):
    p = db.session.get(ParcelaCatastral, id)
    if not p or not p.coordinates_center:
        return jsonify([])
    try:
        lat0, lng0 = map(float, p.coordinates_center.split(','))
    except Exception:
        return jsonify([])
    others = ParcelaCatastral.query.filter(
        ParcelaCatastral.id != id,
        ParcelaCatastral.deleted_at.is_(None),
        ParcelaCatastral.coordinates_center.isnot(None)
    ).all()
    ranked = []
    for o in others:
        try:
            lat1, lng1 = map(float, o.coordinates_center.split(','))
            dist = ((lat1 - lat0) ** 2 + (lng1 - lng0) ** 2) ** 0.5
            ranked.append((dist, o))
        except Exception:
            pass
    ranked.sort(key=lambda x: x[0])
    return jsonify([o.as_dict() for _, o in ranked[:5]])

@app.route('/api/catastro/layers', methods=['GET'])
@api_login_required
def get_catastro_layers():
    rows = db.session.execute(db.text(
        "SELECT source_provider, COUNT(*) FROM parcelas_catastrales "
        "WHERE deleted_at IS NULL GROUP BY source_provider"
    )).fetchall()
    return jsonify([{'provider': r[0] or 'manual', 'count': r[1]} for r in rows])

@app.route('/api/catastro/layers/register', methods=['POST'])
@api_login_required
def register_catastro_layer():
    data = request.get_json() or {}
    return jsonify({'status': 'ok', 'provider': data.get('provider', 'unknown'),
                    'message': 'Registrado (connector futuro)'})

@app.route('/api/catastro/explore', methods=['GET'])
@api_login_required
def explore_catastro():
    mode = request.args.get('mode', 'sequential')
    parcelas = ParcelaCatastral.query.filter(ParcelaCatastral.deleted_at.is_(None)).all()
    if mode == 'spatial':
        def _key(p):
            if p.coordinates_center:
                try:
                    lat, lng = map(float, p.coordinates_center.split(','))
                    return (lng, -lat)
                except Exception:
                    pass
            return (float('inf'), float('inf'))
        parcelas = sorted(parcelas, key=_key)
    return jsonify([p.as_dict() for p in parcelas])

# ── Catastro v4.0: Geographic boundary proxy (IGN WFS + cache) ───────────────
import urllib.request as _ureq
import urllib.parse   as _uparse
import json           as _jmod
import ssl            as _ssl

_GEO_CACHE: dict = {}
_GEO_SSL = _ssl._create_unverified_context()

@app.route('/api/catastro/geo/provincias', methods=['GET'])
@api_login_required
def get_provincias_geo():
    from flask import Response as _Resp
    if 'provincias' in _GEO_CACHE:
        return _Resp(_jmod.dumps(_GEO_CACHE['provincias']), mimetype='application/json')
    url = ('https://wms.ign.gob.ar/geoserver/ows'
           '?service=WFS&version=1.0.0&request=GetFeature'
           '&typeName=ign:provincia&outputFormat=application/json')
    try:
        req = _ureq.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with _ureq.urlopen(req, timeout=20, context=_GEO_SSL) as r:
            data = _jmod.loads(r.read().decode('utf-8'))
        for f in data.get('features', []):
            props = f.get('properties', {})
            props['nombre'] = props.get('nam') or props.get('nombre') or ''
        _GEO_CACHE['provincias'] = data
        return _Resp(_jmod.dumps(data), mimetype='application/json')
    except Exception as exc:
        return jsonify({'type': 'FeatureCollection', 'features': [], 'error': str(exc)})

@app.route('/api/catastro/geo/departamentos/<province_code>', methods=['GET'])
@api_login_required
def get_departamentos_geo(province_code):
    from flask import Response as _Resp
    cache_key = 'dep_' + province_code
    if cache_key in _GEO_CACHE:
        return _Resp(_jmod.dumps(_GEO_CACHE[cache_key]), mimetype='application/json')
    params = {
        'service': 'WFS', 'version': '1.0.0', 'request': 'GetFeature',
        'typeName': 'ign:departamento', 'outputFormat': 'application/json',
        'CQL_FILTER': "in1 LIKE '" + province_code + "%'",
    }
    url = 'https://wms.ign.gob.ar/geoserver/ows?' + _uparse.urlencode(params)
    try:
        req = _ureq.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with _ureq.urlopen(req, timeout=25, context=_GEO_SSL) as r:
            data = _jmod.loads(r.read().decode('utf-8'))
        for f in data.get('features', []):
            props = f.get('properties', {})
            props['nombre'] = props.get('nam') or props.get('nombre') or ''
        _GEO_CACHE[cache_key] = data
        return _Resp(_jmod.dumps(data), mimetype='application/json')
    except Exception as exc:
        return jsonify({'type': 'FeatureCollection', 'features': [], 'error': str(exc)})

# ── Catastro v3.0: PropietarioCatastral (M2M owners) ─────────────────────────

@app.route('/api/catastro/parcelas/<int:id>/propietarios', methods=['POST'])
@api_login_required
def add_catastro_propietario(id):
    parcela = ParcelaCatastral.query.get_or_404(id)
    data    = request.get_json() or {}
    owner   = PropietarioCatastral(
        full_name        = data.get('full_name') or None,
        phone            = data.get('phone') or None,
        email            = data.get('email') or None,
        notes            = data.get('notes') or None,
        source           = data.get('source') or None,
        confidence_level = data.get('confidence_level', 'unknown'),
    )
    db.session.add(owner)
    db.session.flush()
    parcela.owners.append(owner)
    db.session.commit()
    return jsonify(owner.as_dict()), 201

@app.route('/api/catastro/parcelas/<int:id>/propietarios/<int:oid>', methods=['DELETE'])
@api_login_required
def unlink_catastro_propietario(id, oid):
    parcela = ParcelaCatastral.query.get_or_404(id)
    owner   = PropietarioCatastral.query.get_or_404(oid)
    if owner in parcela.owners:
        parcela.owners.remove(owner)
        db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/api/catastro/propietarios/<int:oid>', methods=['PATCH'])
@api_login_required
def update_catastro_propietario(oid):
    owner = PropietarioCatastral.query.get_or_404(oid)
    data  = request.get_json() or {}
    for field in ('full_name', 'phone', 'email', 'notes', 'source', 'confidence_level'):
        if field in data:
            setattr(owner, field, data[field] or None)
    db.session.commit()
    return jsonify(owner.as_dict())

@app.route('/api/catastro/propietarios/<int:oid>', methods=['DELETE'])
@api_login_required
def delete_catastro_propietario(oid):
    owner = PropietarioCatastral.query.get_or_404(oid)
    db.session.delete(owner)
    db.session.commit()
    return jsonify({'status': 'ok'})

# ── Catastro v3.0: ActividadParcela (activity log) ───────────────────────────

@app.route('/api/catastro/parcelas/<int:id>/actividades', methods=['POST'])
@api_login_required
def add_catastro_actividad(id):
    parcela = ParcelaCatastral.query.get_or_404(id)
    data    = request.get_json() or {}
    texto   = (data.get('texto') or '').strip()
    if not texto:
        return jsonify({'error': 'texto requerido'}), 400
    act = ActividadParcela(
        parcela_id = parcela.id,
        tipo       = data.get('tipo', 'nota'),
        texto      = texto,
        created_by = session.get('admin_username', ''),
    )
    db.session.add(act)
    db.session.commit()
    return jsonify(act.as_dict()), 201

@app.route('/api/catastro/actividades/<int:act_id>', methods=['DELETE'])
@api_login_required
def delete_catastro_actividad(act_id):
    act = ActividadParcela.query.get_or_404(act_id)
    db.session.delete(act)
    db.session.commit()
    return jsonify({'status': 'ok'})

# ── Init ──────────────────────────────────────────────────────────────────────

with app.app_context():
    db.create_all()
    with db.engine.connect() as _conn:
        for _ddl in [
            "ALTER TABLE propiedades ADD COLUMN deleted_at DATETIME",
            "ALTER TABLE clientes ADD COLUMN deleted_at DATETIME",
            "ALTER TABLE propiedades ADD COLUMN codigo VARCHAR",
            "ALTER TABLE propiedades ADD COLUMN superficie_terreno REAL",
            "ALTER TABLE propiedades ADD COLUMN superficie_cubierta REAL",
            "ALTER TABLE parcelas_catastrales ADD COLUMN source_provider VARCHAR DEFAULT 'manual'",
            "ALTER TABLE parcelas_catastrales ADD COLUMN bbox VARCHAR",
            "ALTER TABLE parcelas_catastrales ADD COLUMN neighbor_cache TEXT",
            "ALTER TABLE parcelas_catastrales ADD COLUMN propietario_id INTEGER REFERENCES clientes(id)",
            # v3.0 tables created via db.create_all() but columns guarded here for safety
            "ALTER TABLE propietarios_catastrales ADD COLUMN source VARCHAR",
            "ALTER TABLE propietarios_catastrales ADD COLUMN confidence_level VARCHAR DEFAULT 'unknown'",
            "ALTER TABLE propiedades ADD COLUMN lat REAL",
            "ALTER TABLE propiedades ADD COLUMN lng REAL",
            "ALTER TABLE propiedades ADD COLUMN geojson_geometry TEXT",
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
