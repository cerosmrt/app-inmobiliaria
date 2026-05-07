"""
Carga datos demo: 1 admin + propiedades publicadas con datos realistas de CABA.
Uso: venv\Scripts\python load_demo.py
"""
from app import app, db
from models import Admin, Propiedad, Cliente

with app.app_context():
    # ── Admin ──────────────────────────────────────────────────────────────────
    if Admin.query.count() == 0:
        admin = Admin(username='roberto')
        admin.set_password('moret2024')
        db.session.add(admin)
        print("Admin creado: roberto / moret2024")
    else:
        print("Admin ya existe, se omite.")

    # ── Propiedades demo ───────────────────────────────────────────────────────
    demos = [
        dict(
            direccion='Av. Santa Fe 2850 Piso 4 A',
            barrio='Palermo',
            tipo='departamento',
            operacion='venta',
            estado='disponible',
            ambientes=3,
            rango_min=135000,
            rango_max=145000,
            es_usd=True,
            precio_a_consultar=False,
            publicada=True,
            descripcion='Departamento luminoso de 3 ambientes con balcón a la calle. Piso de madera, cocina renovada, placard en dormitorios. Edificio con portero y amenities. A metros del subte D.',
        ),
        dict(
            direccion='Gurruchaga 1540 PB',
            barrio='Villa Crespo',
            tipo='departamento',
            operacion='alquiler',
            estado='disponible',
            ambientes=2,
            rango_min=850000,
            rango_max=None,
            es_usd=False,
            precio_a_consultar=False,
            publicada=True,
            descripcion='Monoambiente amplio en planta baja con patio privado. Ideal pareja o profesional. Cocina americana, baño renovado, muy silencioso. A una cuadra de Av. Corrientes.',
        ),
        dict(
            direccion='Av. Cabildo 3120 7° B',
            barrio='Belgrano',
            tipo='departamento',
            operacion='venta',
            estado='disponible',
            ambientes=4,
            rango_min=220000,
            rango_max=230000,
            es_usd=True,
            precio_a_consultar=False,
            publicada=True,
            descripcion='Amplio departamento de 4 ambientes con dependencia. Vista abierta al río desde el 7° piso. Living-comedor con balcón corrido, dormitorio en suite, cocina de granito. Cochera fija incluida. Edificio con piscina y gimnasio.',
        ),
        dict(
            direccion='Serrano 456',
            barrio='Palermo Soho',
            tipo='casa',
            operacion='venta',
            estado='disponible',
            ambientes=5,
            rango_min=380000,
            rango_max=None,
            es_usd=True,
            precio_a_consultar=False,
            publicada=True,
            descripcion='Casa de estilo reciclada a nuevo. Planta baja: living amplio con doble altura, cocina integrada, comedor y patio con parrilla. Primera planta: 3 dormitorios, 2 baños y terraza. Ideal familia o inversión.',
        ),
        dict(
            direccion='Av. Corrientes 4500 Piso 2',
            barrio='Almagro',
            tipo='local',
            operacion='alquiler',
            estado='disponible',
            ambientes=None,
            rango_min=1200000,
            rango_max=None,
            es_usd=False,
            precio_a_consultar=False,
            publicada=True,
            descripcion='Local comercial en planta baja sobre Corrientes. 60 m² con frente vidriado, baño, depósito y aire acondicionado. Excelente ubicación con alto tránsito peatonal. Apto para gastronomía, comercio o oficina.',
        ),
        dict(
            direccion='Uriarte 2210 Piso 1 A',
            barrio='Palermo Hollywood',
            tipo='departamento',
            operacion='alquiler',
            estado='disponible',
            ambientes=2,
            rango_min=1100000,
            rango_max=None,
            es_usd=False,
            precio_a_consultar=False,
            publicada=True,
            descripcion='Departamento de 2 ambientes reciclado, muy luminoso. Cocina abierta con isla, piso de cemento alisado, baño con ducha de lluvia. En el corazón de Palermo Hollywood a pasos de restaurantes y vida nocturna.',
        ),
        dict(
            direccion='Virrey del Pino 2860',
            barrio='Belgrano R',
            tipo='casa',
            operacion='venta',
            estado='disponible',
            ambientes=6,
            rango_min=None,
            rango_max=None,
            es_usd=True,
            precio_a_consultar=True,
            publicada=True,
            descripcion='Señorial casa de categoría en el corazón de Belgrano R. 400 m² cubiertos distribuidos en 3 plantas. 4 dormitorios en suite, escritorio, salón de usos múltiples, piscina y jardín. Cochera para 3 autos. Oportunidad única.',
        ),
        dict(
            direccion='Lavalle 835 Piso 8 C',
            barrio='Microcentro',
            tipo='departamento',
            operacion='venta',
            estado='disponible',
            ambientes=1,
            rango_min=65000,
            rango_max=70000,
            es_usd=True,
            precio_a_consultar=False,
            publicada=True,
            descripcion='Monoambiente ideal inversión en el Microcentro porteño. 32 m², muy buena ubicación, a metros de Florida y Av. Corrientes. Renta actualmente $850.000/mes. Alta demanda alquiler temporal.',
        ),
    ]

    creadas = 0
    for d in demos:
        p = Propiedad(**d)
        db.session.add(p)
        creadas += 1

    db.session.commit()
    print(f"{creadas} propiedades demo cargadas y publicadas.")
    print("\nListo! Abrí http://localhost:5000 para ver el sitio.")
    print("Admin panel: http://localhost:5000/admin")
    print("  usuario: roberto")
    print("  contraseña: moret2024")
