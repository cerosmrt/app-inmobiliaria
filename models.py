from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

interesados_propiedades = db.Table('interesados_propiedades',
    db.Column('propiedad_id', db.Integer, db.ForeignKey('propiedades.id'), primary_key=True),
    db.Column('cliente_id', db.Integer, db.ForeignKey('clientes.id'), primary_key=True)
)

propietarios_propiedades = db.Table('propietarios_propiedades',
    db.Column('propiedad_id', db.Integer, db.ForeignKey('propiedades.id'), primary_key=True),
    db.Column('cliente_id', db.Integer, db.ForeignKey('clientes.id'), primary_key=True)
)

class Propiedad(db.Model):
    __tablename__ = 'propiedades'
    id = db.Column(db.Integer, primary_key=True, index=True)
    codigo = db.Column(db.String, nullable=True, index=True)
    direccion = db.Column(db.String, index=True)
    barrio = db.Column(db.String, nullable=True)
    rango_min = db.Column(db.Float, nullable=True)
    rango_max = db.Column(db.Float, nullable=True)
    es_usd = db.Column(db.Boolean, default=True)
    precio_a_consultar = db.Column(db.Boolean, default=False)
    ambientes = db.Column(db.Integer, nullable=True)
    superficie_terreno  = db.Column(db.Float, nullable=True)
    superficie_cubierta = db.Column(db.Float, nullable=True)
    tipo = db.Column(db.String)         # casa, departamento, local, terreno, otro
    operacion = db.Column(db.String, nullable=True)  # venta, alquiler
    estado = db.Column(db.String)       # disponible, reservada, vendida, rentada, cerrada
    publicada = db.Column(db.Boolean, default=False)
    destacada = db.Column(db.Boolean, default=False)
    fotos = db.Column(db.String, nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    fecha_estado = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    propietario_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    propietario = db.relationship('Cliente', backref='propiedades_legacy', foreign_keys=[propietario_id])
    propietarios = db.relationship('Cliente', secondary=propietarios_propiedades, backref='propiedades_como_propietario')
    interesados = db.relationship('Cliente', secondary=interesados_propiedades, backref='intereses')

    def _fotos_list(self):
        if not self.fotos:
            return []
        return [f.replace('\\', '/') for f in self.fotos.split(',') if f.strip()]

    def as_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo or '',
            'direccion': self.direccion,
            'barrio': self.barrio or '',
            'rango_min': self.rango_min,
            'rango_max': self.rango_max,
            'es_usd': self.es_usd,
            'precio_a_consultar': self.precio_a_consultar,
            'ambientes': self.ambientes,
            'superficie_terreno': self.superficie_terreno,
            'superficie_cubierta': self.superficie_cubierta,
            'tipo': self.tipo,
            'operacion': self.operacion or '',
            'estado': self.estado,
            'publicada': self.publicada,
            'destacada': self.destacada,
            'fotos': self._fotos_list(),
            'descripcion': self.descripcion or '',
            'fecha_estado': self.fecha_estado.strftime('%d/%m/%Y') if self.fecha_estado else None,
            'propietario_id': self.propietario_id,
            'propietario': self.propietario.nombre + ' ' + self.propietario.apellido if self.propietario else None,
            'propietarios': [{'id': c.id, 'nombre': c.nombre, 'apellido': c.apellido, 'telefono': c.telefono} for c in self.propietarios],
            'propietarios_ids': [c.id for c in self.propietarios],
            'interesados': [{'id': c.id, 'nombre': c.nombre, 'apellido': c.apellido, 'telefono': c.telefono} for c in self.interesados],
            'interesados_ids': [c.id for c in self.interesados],
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
        propiedades_propietario = [
            {'id': p.id, 'direccion': p.direccion, 'codigo': p.codigo or '', 'estado': p.estado}
            for p in self.propiedades_como_propietario
            if p.deleted_at is None
        ]
        propiedades_interesado = [
            {'id': p.id, 'direccion': p.direccion, 'codigo': p.codigo or '', 'estado': p.estado}
            for p in self.intereses
            if p.deleted_at is None
        ]
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
            'fotos': [f.replace('\\', '/') for f in self.fotos.split(',') if f.strip()] if self.fotos else [],
            'propiedades_propietario': propiedades_propietario,
            'propiedades_interesado': propiedades_interesado,
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

class CaptacionLead(db.Model):
    __tablename__ = 'captacion_leads'
    id                  = db.Column(db.Integer, primary_key=True)
    direccion           = db.Column(db.String, nullable=False)
    barrio              = db.Column(db.String, nullable=True)
    ciudad              = db.Column(db.String, nullable=True)
    tipo_propiedad      = db.Column(db.String, nullable=True)
    operacion           = db.Column(db.String, nullable=True)
    estado              = db.Column(db.String, default='detectada', index=True)
    prioridad           = db.Column(db.String, default='media')
    potencial           = db.Column(db.Integer, default=3)
    fuente              = db.Column(db.String, nullable=True)
    descripcion         = db.Column(db.Text, nullable=True)
    notas               = db.Column(db.Text, nullable=True)
    fecha_creacion      = db.Column(db.DateTime, default=datetime.utcnow)
    ultima_interaccion  = db.Column(db.DateTime, nullable=True)
    proximo_seguimiento = db.Column(db.DateTime, nullable=True)
    created_by          = db.Column(db.String, nullable=True)
    deleted_at          = db.Column(db.DateTime, nullable=True)

    propietario  = db.relationship('PropietarioLead', backref='lead', uselist=False, cascade='all, delete-orphan')
    actividades  = db.relationship('CaptacionActividad', backref='lead', cascade='all, delete-orphan',
                                   order_by='CaptacionActividad.fecha.desc()')

    def as_dict(self):
        return {
            'id': self.id,
            'direccion': self.direccion,
            'barrio': self.barrio or '',
            'ciudad': self.ciudad or '',
            'tipo_propiedad': self.tipo_propiedad or '',
            'operacion': self.operacion or '',
            'estado': self.estado,
            'prioridad': self.prioridad or 'media',
            'potencial': self.potencial or 3,
            'fuente': self.fuente or '',
            'descripcion': self.descripcion or '',
            'notas': self.notas or '',
            'fecha_creacion': self.fecha_creacion.strftime('%d/%m/%Y') if self.fecha_creacion else '',
            'ultima_interaccion': self.ultima_interaccion.strftime('%d/%m/%Y %H:%M') if self.ultima_interaccion else None,
            'proximo_seguimiento': self.proximo_seguimiento.strftime('%Y-%m-%d') if self.proximo_seguimiento else None,
            'created_by': self.created_by or '',
            'propietario': self.propietario.as_dict() if self.propietario else None,
            'actividades': [a.as_dict() for a in self.actividades],
        }


class PropietarioLead(db.Model):
    __tablename__ = 'propietario_leads'
    id             = db.Column(db.Integer, primary_key=True)
    lead_id        = db.Column(db.Integer, db.ForeignKey('captacion_leads.id'), nullable=False)
    nombre         = db.Column(db.String, nullable=True)
    telefono       = db.Column(db.String, nullable=True)
    email          = db.Column(db.String, nullable=True)
    whatsapp       = db.Column(db.String, nullable=True)
    observaciones  = db.Column(db.Text, nullable=True)

    def as_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre or '',
            'telefono': self.telefono or '',
            'email': self.email or '',
            'whatsapp': self.whatsapp or '',
            'observaciones': self.observaciones or '',
        }


class CaptacionActividad(db.Model):
    __tablename__ = 'captacion_actividades'
    id          = db.Column(db.Integer, primary_key=True)
    lead_id     = db.Column(db.Integer, db.ForeignKey('captacion_leads.id'), nullable=False)
    tipo        = db.Column(db.String, nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    fecha       = db.Column(db.DateTime, default=datetime.utcnow)
    created_by  = db.Column(db.String, nullable=True)

    def as_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'tipo': self.tipo,
            'descripcion': self.descripcion or '',
            'fecha': self.fecha.strftime('%d/%m/%Y %H:%M') if self.fecha else '',
            'created_by': self.created_by or '',
        }


class ParcelaCatastral(db.Model):
    __tablename__ = 'parcelas_catastrales'
    id                 = db.Column(db.Integer, primary_key=True)
    parcel_id          = db.Column(db.String, nullable=True, index=True)
    geojson_geometry   = db.Column(db.Text, nullable=True)
    surface_area       = db.Column(db.Float, nullable=True)
    zone               = db.Column(db.String, nullable=True)
    municipality       = db.Column(db.String, nullable=True)
    province           = db.Column(db.String, nullable=True)
    coordinates_center = db.Column(db.String, nullable=True)   # "lat,lng"
    land_use           = db.Column(db.String, nullable=True)
    notes              = db.Column(db.Text, nullable=True)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    deleted_at         = db.Column(db.DateTime, nullable=True)

    oportunidad     = db.relationship('OportunidadTerreno', backref='parcela', uselist=False, cascade='all, delete-orphan')
    investigaciones = db.relationship('InvestigacionPropietario', backref='parcela', cascade='all, delete-orphan',
                                      order_by='InvestigacionPropietario.fecha.desc()')

    def as_dict(self):
        coords = None
        if self.coordinates_center:
            try:
                parts = self.coordinates_center.split(',')
                coords = {'lat': float(parts[0]), 'lng': float(parts[1])}
            except Exception:
                pass
        return {
            'id': self.id,
            'parcel_id': self.parcel_id or '',
            'geojson_geometry': self.geojson_geometry,
            'surface_area': self.surface_area,
            'zone': self.zone or '',
            'municipality': self.municipality or '',
            'province': self.province or '',
            'coordinates_center': coords,
            'land_use': self.land_use or '',
            'notes': self.notes or '',
            'created_at': self.created_at.strftime('%d/%m/%Y') if self.created_at else '',
            'oportunidad': self.oportunidad.as_dict() if self.oportunidad else None,
            'investigaciones': [i.as_dict() for i in self.investigaciones],
        }


class OportunidadTerreno(db.Model):
    __tablename__ = 'oportunidades_terreno'
    id                  = db.Column(db.Integer, primary_key=True)
    parcela_id          = db.Column(db.Integer, db.ForeignKey('parcelas_catastrales.id'), nullable=False)
    estado              = db.Column(db.String, default='sin_evaluar')
    prioridad           = db.Column(db.String, default='media')
    potencial           = db.Column(db.Integer, default=3)
    descripcion         = db.Column(db.Text, nullable=True)
    observaciones       = db.Column(db.Text, nullable=True)
    ultima_interaccion  = db.Column(db.DateTime, nullable=True)
    proximo_seguimiento = db.Column(db.DateTime, nullable=True)
    created_by          = db.Column(db.String, nullable=True)

    def as_dict(self):
        return {
            'id': self.id,
            'parcela_id': self.parcela_id,
            'estado': self.estado,
            'prioridad': self.prioridad or 'media',
            'potencial': self.potencial or 3,
            'descripcion': self.descripcion or '',
            'observaciones': self.observaciones or '',
            'ultima_interaccion': self.ultima_interaccion.strftime('%d/%m/%Y') if self.ultima_interaccion else None,
            'proximo_seguimiento': self.proximo_seguimiento.strftime('%Y-%m-%d') if self.proximo_seguimiento else None,
            'created_by': self.created_by or '',
        }


class InvestigacionPropietario(db.Model):
    __tablename__ = 'investigaciones_propietario'
    id                 = db.Column(db.Integer, primary_key=True)
    parcela_id         = db.Column(db.Integer, db.ForeignKey('parcelas_catastrales.id'), nullable=False)
    nombre             = db.Column(db.String, nullable=True)
    telefono           = db.Column(db.String, nullable=True)
    email              = db.Column(db.String, nullable=True)
    fuente_informacion = db.Column(db.String, nullable=True)
    notas              = db.Column(db.Text, nullable=True)
    fecha              = db.Column(db.DateTime, default=datetime.utcnow)

    def as_dict(self):
        return {
            'id': self.id,
            'parcela_id': self.parcela_id,
            'nombre': self.nombre or '',
            'telefono': self.telefono or '',
            'email': self.email or '',
            'fuente_informacion': self.fuente_informacion or '',
            'notas': self.notas or '',
            'fecha': self.fecha.strftime('%d/%m/%Y %H:%M') if self.fecha else '',
        }


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
