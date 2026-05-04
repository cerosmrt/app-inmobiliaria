from flask import Flask, request, jsonify, render_template
from flask_migrate import Migrate
from models import db, Propiedad, Cliente
import os
from datetime import datetime
from werkzeug.utils import secure_filename

# Inicializa la aplicación Flask
app = Flask(__name__)

# Configuración de la base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inmobiliaria.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración para subir fotos
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Inicializa SQLAlchemy con la app
db.init_app(app)

# Inicia la extensión Flask-Migrate
migrate = Migrate(app, db)

# Crear directorio templates si no existe
if not os.path.exists('templates'):
    os.makedirs('templates')

# Crear directorio static si no existe
if not os.path.exists('static'):
    os.makedirs('static')

# Ruta principal con la nueva interfaz simplificada
@app.route('/')
def index():
    return render_template('index.html')

# Rutas API para propiedades
@app.route('/api/propiedades', methods=['GET'])
def get_propiedades():
    tipo = request.args.get('tipo', '')
    propietario = request.args.get('propietario', '')
    interesado = request.args.get('interesado', '')

    query = Propiedad.query
    if tipo:
        query = query.filter(Propiedad.tipo.ilike(f'%{tipo}%'))
    if propietario:
        # Separar nombre y apellido del parámetro propietario
        propietario_parts = propietario.split()
        nombre = propietario_parts[0]
        apellido = ' '.join(propietario_parts[1:]) if len(propietario_parts) > 1 else ''
        query = query.join(Cliente, Propiedad.propietario).filter(
            Cliente.nombre.ilike(f'%{nombre}%'),
            Cliente.apellido.ilike(f'%{apellido}%') if apellido else True
        )
    if interesado:
        # Similar para interesados
        interesado_parts = interesado.split()
        nombre = interesado_parts[0]
        apellido = ' '.join(interesado_parts[1:]) if len(interesado_parts) > 1 else ''
        query = query.join(Propiedad.interesados).filter(
            Cliente.nombre.ilike(f'%{nombre}%'),
            Cliente.apellido.ilike(f'%{apellido}%') if apellido else True
        )
    
    propiedades = query.all()
    return jsonify([prop.as_dict() for prop in propiedades])

@app.route('/api/propiedades', methods=['POST'])
def add_propiedad():
    data = request.get_json()
    nueva_propiedad = Propiedad(
        direccion=data['direccion'],
        rango_min=data['rango_min'],
        rango_max=data['rango_max'],
        es_usd=data.get('es_usd', False),
        ambientes=data.get('ambientes'),
        tipo=data['tipo'],
        estado=data['estado'],
        propietario_id=data.get('propietario_id')
    )
    if 'interesados_ids' in data:
        interesados = Cliente.query.filter(Cliente.id.in_(data['interesados_ids'])).all()
        nueva_propiedad.interesados = interesados
    db.session.add(nueva_propiedad)
    db.session.commit()
    return jsonify(nueva_propiedad.as_dict()), 201

@app.route('/api/propiedades/<int:id>', methods=['GET'])
def get_propiedad(id):
    propiedad = Propiedad.query.get(id)
    if propiedad:
        return jsonify(propiedad.as_dict())
    return jsonify({"message": "Propiedad no encontrada"}), 404

@app.route('/api/propiedades/<int:id>', methods=['PUT'])
def update_propiedad(id):
    propiedad = Propiedad.query.get(id)
    if propiedad:
        data = request.get_json()
        propiedad.direccion = data.get('direccion', propiedad.direccion)
        propiedad.rango_min = data.get('rango_min', propiedad.rango_min)
        propiedad.rango_max = data.get('rango_max', propiedad.rango_max)
        propiedad.es_usd = data.get('es_usd', propiedad.es_usd)
        propiedad.ambientes = data.get('ambientes', propiedad.ambientes)
        propiedad.tipo = data.get('tipo', propiedad.tipo)
        nuevo_estado = data.get('estado', propiedad.estado)
        if nuevo_estado != propiedad.estado:
            propiedad.fecha_estado = datetime.utcnow()
        propiedad.estado = nuevo_estado
        propiedad.propietario_id = data.get('propietario_id', propiedad.propietario_id)
        if 'interesados_ids' in data:
            interesados = Cliente.query.filter(Cliente.id.in_(data['interesados_ids'])).all()
            propiedad.interesados = interesados
        db.session.commit()
        return jsonify({"message": "Propiedad actualizada"})
    return jsonify({"message": "Propiedad no encontrada"}), 404

@app.route('/api/propiedades/<int:id>/matches', methods=['GET'])
def get_matches(id):
    propiedad = Propiedad.query.get(id)
    if not propiedad:
        return jsonify({"message": "Propiedad no encontrada"}), 404

    query = Cliente.query.filter(Cliente.tipo == 'interesado')

    if propiedad.rango_min is not None and propiedad.rango_max is not None:
        query = query.filter(
            db.or_(Cliente.rango_max == None, Cliente.rango_max >= propiedad.rango_min),
            db.or_(Cliente.rango_min == None, Cliente.rango_min <= propiedad.rango_max)
        )

    if propiedad.ambientes:
        query = query.filter(
            db.or_(Cliente.ambientes == None, Cliente.ambientes == propiedad.ambientes)
        )

    return jsonify([c.as_dict() for c in query.all()])

@app.route('/api/propiedades/<int:id>', methods=['DELETE'])
def delete_propiedad(id):
    propiedad = Propiedad.query.get(id)
    if propiedad:
        db.session.delete(propiedad)
        db.session.commit()
        return jsonify({"message": "Propiedad eliminada"})
    return jsonify({"message": "Propiedad no encontrada"}), 404

@app.route('/api/propiedades/<int:id>/upload', methods=['POST'])
def upload_foto_propiedad(id):
    propiedad = Propiedad.query.get(id)
    if not propiedad:
        return jsonify({"message": "Propiedad no encontrada"}), 404
    
    if 'file' not in request.files:
        return jsonify({"message": "No se envió archivo"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "Archivo vacío"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"prop_{id}_{filename}")
        file.save(filepath)
        
        if propiedad.fotos:
            propiedad.fotos += f",{filepath}"
        else:
            propiedad.fotos = filepath
        db.session.commit()
        return jsonify(propiedad.as_dict()), 200
    
    return jsonify({"message": "Formato no permitido"}), 400

# Rutas API para clientes
@app.route('/api/clientes', methods=['GET'])
def get_clientes():
    clientes = Cliente.query.all()
    return jsonify([cliente.as_dict() for cliente in clientes])

@app.route('/api/clientes', methods=['POST'])
def add_cliente():
    data = request.get_json()
    nuevo_cliente = Cliente(
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
    db.session.add(nuevo_cliente)
    db.session.commit()
    return jsonify(nuevo_cliente.as_dict()), 201

@app.route('/api/clientes/<int:id>', methods=['GET'])
def get_cliente(id):
    cliente = Cliente.query.get(id)
    if cliente:
        return jsonify(cliente.as_dict())
    return jsonify({"message": "Cliente no encontrado"}), 404

@app.route('/api/clientes/<int:id>', methods=['PUT'])
def update_cliente(id):
    cliente = Cliente.query.get(id)
    if cliente:
        data = request.get_json()
        cliente.nombre = data.get('nombre', cliente.nombre)
        cliente.apellido = data.get('apellido', cliente.apellido)
        cliente.telefono = data.get('telefono', cliente.telefono)
        cliente.email = data.get('email', cliente.email)
        cliente.tipo = data.get('tipo', cliente.tipo)
        cliente.rango_min = data.get('rango_min', cliente.rango_min)
        cliente.rango_max = data.get('rango_max', cliente.rango_max)
        cliente.es_usd = data.get('es_usd', cliente.es_usd)
        cliente.ambientes = data.get('ambientes', cliente.ambientes)
        cliente.operacion = data.get('operacion', cliente.operacion)
        cliente.descripcion = data.get('descripcion', cliente.descripcion)
        db.session.commit()
        return jsonify({"message": "Cliente actualizado"})
    return jsonify({"message": "Cliente no encontrado"}), 404

@app.route('/api/clientes/<int:id>', methods=['DELETE'])
def delete_cliente(id):
    cliente = Cliente.query.get(id)
    if cliente:
        db.session.delete(cliente)
        db.session.commit()
        return jsonify({"message": "Cliente eliminado"})
    return jsonify({"message": "Cliente no encontrado"}), 404

@app.route('/api/clientes/<int:id>/upload', methods=['POST'])
def upload_foto(id):
    cliente = Cliente.query.get(id)
    if not cliente:
        return jsonify({"message": "Cliente no encontrado"}), 404
    
    if 'file' not in request.files:
        return jsonify({"message": "No se envió archivo"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "Archivo vacío"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{id}_{filename}")
        file.save(filepath)
        
        if cliente.fotos:
            cliente.fotos += f",{filepath}"
        else:
            cliente.fotos = filepath
        db.session.commit()
        return jsonify(cliente.as_dict()), 200
    
    return jsonify({"message": "Formato no permitido"}), 400

@app.route('/cliente/<int:id>')
def cliente_perfil(id):
    return render_template('perfil.html', cliente_id=id)

# Crea las tablas en la base de datos si no existen
with app.app_context():
    db.create_all()

# Ejecuta el servidor Flask en modo depuración
if __name__ == '__main__':
    app.run(debug=True)