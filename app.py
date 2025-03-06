from flask import Flask, request, jsonify, render_template
from flask_migrate import Migrate
from models import db, Propiedad, Cliente
import os
from werkzeug.utils import secure_filename

# Inicializa la aplicación Flask
app = Flask(__name__)

# Configuración de la base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inmobiliaria.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración para subir fotos
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
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
        query = query.join(Cliente, Propiedad.propietario).filter(Cliente.nombre.ilike(f'%{propietario}%'))
    if interesado:
        query = query.join(Propiedad.interesados).filter(Cliente.nombre.ilike(f'%{interesado}%'))
    
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
        propiedad.direccion = data['direccion']
        propiedad.rango_min = data['rango_min']
        propiedad.rango_max = data['rango_max']
        propiedad.es_usd = data.get('es_usd', False)
        propiedad.ambientes = data.get('ambientes')
        propiedad.tipo = data['tipo']
        propiedad.estado = data['estado']
        propiedad.propietario_id = data.get('propietario_id')
        if 'interesados_ids' in data:
            interesados = Cliente.query.filter(Cliente.id.in_(data['interesados_ids'])).all()
            propiedad.interesados = interesados
        db.session.commit()
        return jsonify({"message": "Propiedad actualizada"})
    return jsonify({"message": "Propiedad no encontrada"}), 404

@app.route('/api/propiedades/<int:id>', methods=['DELETE'])
def delete_propiedad(id):
    propiedad = Propiedad.query.get(id)
    if propiedad:
        db.session.delete(propiedad)
        db.session.commit()
        return jsonify({"message": "Propiedad eliminada"})
    return jsonify({"message": "Propiedad no encontrada"}), 404

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
        cliente.nombre = data['nombre']
        cliente.apellido = data['apellido']
        cliente.telefono = data['telefono']
        cliente.email = data.get('email')
        cliente.tipo = data['tipo']
        cliente.rango_min = data.get('rango_min')
        cliente.rango_max = data.get('rango_max')
        cliente.es_usd = data.get('es_usd', False)
        cliente.ambientes = data.get('ambientes')
        cliente.operacion = data.get('operacion')
        cliente.descripcion = data.get('descripcion')
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