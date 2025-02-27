from flask import Flask, request, jsonify, render_template
from flask_migrate import Migrate
from models import db, Propiedad, Cliente
import os

# Inicializa la aplicación Flask
app = Flask(__name__)

# Configuración de la base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inmobiliaria.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
        precio=data['precio'],
        tipo=data['tipo'],
        estado=data['estado'],
        descripcion=data.get('descripcion', '')  # Usa .get() para evitar KeyError si no está
    )
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
        propiedad.precio = data['precio']
        propiedad.tipo = data['tipo']
        propiedad.estado = data['estado']
        propiedad.descripcion = data.get('descripcion', '')
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
        contacto=data['contacto'],
        tipo=data['tipo']
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
        cliente.contacto = data['contacto']
        cliente.tipo = data['tipo']
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

# Crea las tablas en la base de datos si no existen
with app.app_context():
    db.create_all()

# Ejecuta el servidor Flask en modo depuración
if __name__ == '__main__':
    app.run(debug=True)