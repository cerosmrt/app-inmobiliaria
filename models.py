# models.py
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
    precio = db.Column(db.Float)
    tipo = db.Column(db.String)
    estado = db.Column(db.String)
    descripcion = db.Column(db.String)
    # Relación con el propietario (un Cliente)
    # En models.py, modificá la línea de propietario_id
    propietario_id = db.Column(db.Integer, db.ForeignKey('clientes.id', name='fk_propiedades_propietario_id'), nullable=True)
    propietario = db.relationship('Cliente', backref='propiedades', foreign_keys=[propietario_id])
    # Relación con los interesados (muchos Clientes)
    interesados = db.relationship('Cliente', secondary=interesados_propiedades, backref='intereses')

    def as_dict(self):
        return {
            'id': self.id,
            'direccion': self.direccion,
            'precio': self.precio,
            'tipo': self.tipo,
            'estado': self.estado,
            'descripcion': self.descripcion,
            'propietario': self.propietario.nombre if self.propietario else None,
            'interesados': [cliente.nombre for cliente in self.interesados]
        }

# Modelo para los clientes
class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True, index=True)
    nombre = db.Column(db.String, index=True)
    contacto = db.Column(db.String)
    tipo = db.Column(db.String)

    def as_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'contacto': self.contacto,
            'tipo': self.tipo
        }