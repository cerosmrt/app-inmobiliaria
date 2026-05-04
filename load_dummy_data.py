from app import app, db
from models import Cliente, Propiedad

# Lista de clientes dummy
dummy_clientes = [
    # Propietarios
    {
        "nombre": "Juan",
        "apellido": "Pérez",
        "telefono": "123456789",
        "email": "juan.perez@gmail.com",
        "tipo": "propietario",
        "rango_min": 50000,
        "rango_max": 70000,
        "es_usd": True,
        "ambientes": 3,
        "operacion": "venta",
        "descripcion": "Propietario con casa en venta"
    },
    {
        "nombre": "Lucía",
        "apellido": "Rodríguez",
        "telefono": "654321987",
        "email": "lucia.rodriguez@outlook.com",
        "tipo": "propietario",
        "rango_min": 60000,
        "rango_max": 85000,
        "es_usd": True,
        "ambientes": 3,
        "operacion": "renta",
        "descripcion": "Propietario con departamento en alquiler"
    },
    {
        "nombre": "Carlos",
        "apellido": "López",
        "telefono": "456789123",
        "email": "carlos.lopez@yahoo.com",
        "tipo": "propietario",
        "rango_min": 80000,
        "rango_max": 100000,
        "es_usd": True,
        "ambientes": 4,
        "operacion": "venta",
        "descripcion": "Propietario con propiedad grande"
    },
    {
        "nombre": "Sofía",
        "apellido": "Fernández",
        "telefono": "789123456",
        "email": "sofia.fernandez@gmail.com",
        "tipo": "propietario",
        "rango_min": 45000,
        "rango_max": 60000,
        "es_usd": False,
        "ambientes": 2,
        "operacion": "renta",
        "descripcion": "Propietario con departamento chico"
    },
    {
        "nombre": "Pedro",
        "apellido": "García",
        "telefono": "147258369",
        "email": "pedro.garcia@hotmail.com",
        "tipo": "propietario",
        "rango_min": 90000,
        "rango_max": 120000,
        "es_usd": True,
        "ambientes": 5,
        "operacion": "venta",
        "descripcion": "Propietario con casa premium"
    },
    # Interesados
    {
        "nombre": "María",
        "apellido": "Gómez",
        "telefono": "987654321",
        "email": "maria.gomez@hotmail.com",
        "tipo": "interesado",
        "rango_min": 30000,
        "rango_max": 45000,
        "es_usd": False,
        "ambientes": 2,
        "operacion": "renta",
        "descripcion": "Busca departamento para alquilar"
    },
    {
        "nombre": "Ana",
        "apellido": "Martínez",
        "telefono": "321654987",
        "email": "ana.martinez@gmail.com",
        "tipo": "interesado",
        "rango_min": 20000,
        "rango_max": 35000,
        "es_usd": False,
        "ambientes": 1,
        "operacion": "ambas",
        "descripcion": "Busca algo chico para comprar o alquilar"
    },
    {
        "nombre": "Diego",
        "apellido": "Sánchez",
        "telefono": "258369147",
        "email": "diego.sanchez@yahoo.com",
        "tipo": "interesado",
        "rango_min": 50000,
        "rango_max": 75000,
        "es_usd": True,
        "ambientes": 3,
        "operacion": "venta",
        "descripcion": "Busca casa en venta"
    },
    {
        "nombre": "Elena",
        "apellido": "Díaz",
        "telefono": "369147258",
        "email": "elena.diaz@outlook.com",
        "tipo": "interesado",
        "rango_min": 25000,
        "rango_max": 40000,
        "es_usd": False,
        "ambientes": 2,
        "operacion": "renta",
        "descripcion": "Busca alquiler económico"
    },
    {
        "nombre": "Martín",
        "apellido": "Ruiz",
        "telefono": "741852963",
        "email": "martin.ruiz@gmail.com",
        "tipo": "interesado",
        "rango_min": 60000,
        "rango_max": 90000,
        "es_usd": True,
        "ambientes": 4,
        "operacion": "venta",
        "descripcion": "Busca propiedad grande para comprar"
    }
]

# Lista de propiedades dummy (asociadas a propietarios)
dummy_propiedades = [
    {
        "direccion": "Av. Libertad 123",
        "rango_min": 50000,
        "rango_max": 70000,
        "es_usd": True,
        "ambientes": 3,
        "tipo": "casa",
        "estado": "disponible",
        "propietario_nombre": "Juan Pérez",
        "interesados": ["Diego Sánchez"]
    },
    {
        "direccion": "Calle 9 de Julio 456",
        "rango_min": 60000,
        "rango_max": 85000,
        "es_usd": True,
        "ambientes": 3,
        "tipo": "departamento",
        "estado": "disponible",
        "propietario_nombre": "Lucía Rodríguez",
        "interesados": ["Elena Díaz"]
    },
    {
        "direccion": "Ruta 20 Km 5",
        "rango_min": 80000,
        "rango_max": 100000,
        "es_usd": True,
        "ambientes": 4,
        "tipo": "casa",
        "estado": "vendida",
        "propietario_nombre": "Carlos López",
        "interesados": ["Martín Ruiz"]
    },
    {
        "direccion": "San Martín 789",
        "rango_min": 45000,
        "rango_max": 60000,
        "es_usd": False,
        "ambientes": 2,
        "tipo": "departamento",
        "estado": "disponible",
        "propietario_nombre": "Sofía Fernández",
        "interesados": ["María Gómez"]
    },
    {
        "direccion": "Av. Colón 1011",
        "rango_min": 90000,
        "rango_max": 120000,
        "es_usd": True,
        "ambientes": 5,
        "tipo": "casa",
        "estado": "disponible",
        "propietario_nombre": "Pedro García",
        "interesados": ["Diego Sánchez", "Martín Ruiz"]
    }
]

# Función para cargar los datos
def load_dummy_data():
    with app.app_context():
        # Borrar datos existentes y recrear tablas
        db.drop_all()
        db.create_all()

        # Agregar clientes
        clientes_dict = {}
        for cliente_data in dummy_clientes:
            cliente = Cliente(
                nombre=cliente_data["nombre"],
                apellido=cliente_data["apellido"],
                telefono=cliente_data["telefono"],
                email=cliente_data["email"],
                tipo=cliente_data["tipo"],
                rango_min=cliente_data["rango_min"],
                rango_max=cliente_data["rango_max"],
                es_usd=cliente_data["es_usd"],
                ambientes=cliente_data["ambientes"],
                operacion=cliente_data["operacion"],
                descripcion=cliente_data["descripcion"]
            )
            db.session.add(cliente)
            clientes_dict[f"{cliente.nombre} {cliente.apellido}"] = cliente

        # Commit clientes para obtener sus IDs
        db.session.commit()

        # Agregar propiedades
        for prop_data in dummy_propiedades:
            propietario = clientes_dict[prop_data["propietario_nombre"]]
            propiedad = Propiedad(
                direccion=prop_data["direccion"],
                rango_min=prop_data["rango_min"],
                rango_max=prop_data["rango_max"],
                es_usd=prop_data["es_usd"],
                ambientes=prop_data["ambientes"],
                tipo=prop_data["tipo"],
                estado=prop_data["estado"],
                propietario_id=propietario.id
            )
            # Asociar interesados
            interesados = [clientes_dict[name] for name in prop_data["interesados"]]
            propiedad.interesados = interesados
            db.session.add(propiedad)

        db.session.commit()
        print("Datos dummy cargados exitosamente: 10 clientes y 5 propiedades!")

if __name__ == "__main__":
    load_dummy_data()