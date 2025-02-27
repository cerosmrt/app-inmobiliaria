# models.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Modelo para las propiedades
class Propiedad(db.Model):
    __tablename__ = 'propiedades'
    id = db.Column(db.Integer, primary_key=True, index=True)
    direccion = db.Column(db.String, index=True)
    precio = db.Column(db.Float)
    tipo = db.Column(db.String)
    estado = db.Column(db.String)
    descripcion = db.Column(db.String)

    def as_dict(self):
        return {
            'id': self.id,
            'direccion': self.direccion,
            'precio': self.precio,
            'tipo': self.tipo,
            'estado': self.estado,
            'descripcion': self.descripcion
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