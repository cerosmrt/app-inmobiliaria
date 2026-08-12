"""Pre-deploy: deja el esquema de la base al dia ANTES de que arranque la app.

Railway lo corre como `preDeployCommand` (ver railway.json), o sea entre el build
y el arranque de gunicorn. Si falla, Railway aborta el deploy y deja viva la
version anterior: nunca queda la app nueva contra un esquema viejo.

Por que hace falta:
  La base de produccion se creo con `db.create_all()` sin pasar por Alembic, asi
  que no tiene tabla `alembic_version`. Un `upgrade` a secas intentaria correr
  todas las migraciones desde cero contra tablas que ya existen y explotaria.
  Este script detecta ese caso y "stampea" la base en la revision que refleja el
  esquema que `create_all()` habia dejado, y recien ahi aplica lo que falte.

Es idempotente: correrlo en cada deploy no hace nada si no hay nada que aplicar.
"""
import logging
import sys

from flask import Flask
from flask_migrate import Migrate, stamp, upgrade
from sqlalchemy import inspect

from config import config
from models import db

# Revision que describe el esquema que `create_all()` producia con los modelos de
# master: es el punto de partida correcto para una base que nunca vio Alembic.
BASELINE = 'f498a2a5780f'

# Si alguna de estas tablas existe, la base tiene datos reales (no esta vacia).
TABLAS_NUCLEO = ('admins', 'propiedades', 'clientes')

log = logging.getLogger('release')


def crear_app():
    """App minima: solo db + Migrate.

    A proposito NO importa app.py, porque ese modulo corre `create_all()` al
    importarse y crearia tablas antes de que podamos stampear la base.
    """
    import os
    app = Flask(__name__)
    app.config.from_object(config.get(os.getenv('FLASK_ENV', 'production'), config['default']))
    db.init_app(app)
    Migrate(app, db)
    return app


def main():
    logging.basicConfig(level=logging.INFO, format='[release] %(message)s')
    app = crear_app()

    with app.app_context():
        insp = inspect(db.engine)
        tablas = set(insp.get_table_names())

        tiene_datos = any(t in tablas for t in TABLAS_NUCLEO)
        stampeada = 'alembic_version' in tablas and bool(
            db.session.execute(db.text('SELECT 1 FROM alembic_version LIMIT 1')).first()
        )

        if not tablas:
            # Base vacia (entorno nuevo): las migraciones la construyen entera.
            log.info('base vacia -> upgrade desde cero')
        elif not stampeada and tiene_datos:
            # El caso de produccion: esquema hecho por create_all(), sin historial.
            log.info('base sin historial de Alembic -> stamp %s', BASELINE)
            stamp(revision=BASELINE)
        else:
            log.info('base ya versionada -> solo upgrade')

        upgrade()
        rev = db.session.execute(db.text('SELECT version_num FROM alembic_version')).scalar()
        log.info('esquema al dia en la revision %s', rev)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        log.exception('la migracion fallo: se aborta el deploy')
        sys.exit(1)
