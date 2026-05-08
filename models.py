from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

interesados_propiedades = db.Table('interesados_propiedades',
    db.Column('propiedad_id', db.Integer, db.ForeignKey('propiedades.id'), primary_key=True),
    db.Column('cliente_id', db.Integer, db.ForeignKey('clientes.id'), primary_key=True)
)

class Propiedad(db.Model):
    __tablename__ = 'propiedades'
    id = db.Column(db.Integer, primary_key=True, index=True)
    direccion = db.Column(db.String, index=True)
    barrio = db.Column(db.String, nullable=True)
    rango_min = db.Column(db.Float, nullable=True)
    rango_max = db.Column(db.Float, nullable=True)
    es_usd = db.Column(db.Boolean, default=True)
    precio_a_consultar = db.Column(db.Boolean, default=False)
    ambientes = db.Column(db.Integer, nullable=True)
    tipo = db.Column(db.String)         # casa, departamento, local, terreno, otro
    operacion = db.Column(db.String, nullable=True)  # venta, alquiler
    estado = db.Column(db.String)       # disponible, vendida, rentada
    publicada = db.Column(db.Boolean, default=False)
    fotos = db.Column(db.String, nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    fecha_estado = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    propietario_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    propietario = db.relationship('Cliente', backref='propiedades', foreign_keys=[propietario_id])
    interesados = db.relationship('Cliente', secondary=interesados_propiedades, backref='intereses')

    def as_dict(self):
        return {
            'id': self.id,
            'direccion': self.direccion,
            'barrio': self.barrio or '',
            'rango_min': self.rango_min,
            'rango_max': self.rango_max,
            'es_usd': self.es_usd,
            'precio_a_consultar': self.precio_a_consultar,
            'ambientes': self.ambientes,
            'tipo': self.tipo,
            'operacion': self.operacion or '',
            'estado': self.estado,
            'publicada': self.publicada,
            'fotos': self.fotos.split(',') if self.fotos else [],
            'descripcion': self.descripcion or '',
            'fecha_estado': self.fecha_estado.strftime('%d/%m/%Y') if self.fecha_estado else None,
            'propietario_id': self.propietario_id,
            'propietario': self.propietario.nombre + ' ' + self.propietario.apellido if self.propietario else None,
            'interesados': [c.nombre + ' ' + c.apellido for c in self.interesados]
        }

class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True, index=True)
    nombre = db.Column(db.String, nullable=False)
    apellido = db.Column(db.String, nullable=False)
    telefono = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=True)
    tipo = db.Column(db.String, nullable=False)
    rango_min = db.Column(db.Float, nullable=True)
    rango_max = db.Column(db.Float, nullable=True)
    es_usd = db.Column(db.Boolean, default=False)
    ambientes = db.Column(db.Integer, nullable=True)
    operacion = db.Column(db.String, nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    fotos = db.Column(db.String, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def as_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'telefono': self.telefono,
            'email': self.email,
            'tipo': self.tipo,
            'rango_min': self.rango_min,
            'rango_max': self.rango_max,
            'es_usd': self.es_usd,
            'ambientes': self.ambientes,
            'operacion': self.operacion,
            'descripcion': self.descripcion,
            'fotos': self.fotos.split(',') if self.fotos else []
        }

class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Consulta(db.Model):
    __tablename__ = 'consultas'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String, nullable=False)
    telefono = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=True)
    mensaje = db.Column(db.Text, nullable=False)
    propiedad_id = db.Column(db.Integer, db.ForeignKey('propiedades.id'), nullable=True)
    propiedad = db.relationship('Propiedad', backref='consultas')
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    leida = db.Column(db.Boolean, default=False)

    def as_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'telefono': self.telefono or '',
            'email': self.email or '',
            'mensaje': self.mensaje,
            'propiedad_id': self.propiedad_id,
            'propiedad_direccion': self.propiedad.direccion if self.propiedad else None,
            'fecha': self.fecha.strftime('%d/%m/%Y %H:%M') if self.fecha else '',
            'leida': self.leida
        }
