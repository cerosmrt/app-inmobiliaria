from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Tabla intermedia para la relación muchos-a-muchos entre Propiedad e interesados (Clientes)
interesados_propiedades = db.Table('interesados_propiedades',
    db.Column('propiedad_id', db.Integer, db.ForeignKey('propiedades.id'), primary_key=True),
    db.Column('cliente_id', db.Integer, db.ForeignKey('clientes.id'), primary_key=True)
)

# Modelo para las propiedades
class Propiedad(db.Model):
    __tablename__ = 'propiedades'
    id = db.Column(db.Integer, primary_key=True, index=True)
    direccion = db.Column(db.String, index=True)
    rango_min = db.Column(db.Float, nullable=True)
    rango_max = db.Column(db.Float, nullable=True)
    es_usd = db.Column(db.Boolean, default=False)
    ambientes = db.Column(db.Integer, nullable=True)
    tipo = db.Column(db.String)
    estado = db.Column(db.String)
    propietario_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    propietario = db.relationship('Cliente', backref='propiedades', foreign_keys=[propietario_id])
    interesados = db.relationship('Cliente', secondary=interesados_propiedades, backref='intereses')

    def as_dict(self):
        return {
            'id': self.id,
            'direccion': self.direccion,
            'rango_min': self.rango_min,
            'rango_max': self.rango_max,
            'es_usd': self.es_usd,
            'ambientes': self.ambientes,
            'tipo': self.tipo,
            'estado': self.estado,
            'propietario': self.propietario.nombre + ' ' + self.propietario.apellido if self.propietario else None,
            'interesados': [c.nombre + ' ' + c.apellido for c in self.interesados]
        }

# Modelo para los clientes
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