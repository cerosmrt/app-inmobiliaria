"""add adjuntos privados

Revision ID: a1f4c8d92b07
Revises: e014c9f339fd
Create Date: 2026-07-23 12:35:00.000000

Escrita a mano: el `db.create_all()` del arranque de app.py ya crea la tabla
al importar la app, así que autogenerate no ve ninguna diferencia. La
migración existe igual para que producción tenga su revisión y no dependa
de ese create_all (ver ROADMAP — sacar ese bloque es deuda pendiente).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1f4c8d92b07'
down_revision = 'e014c9f339fd'
branch_labels = None
depends_on = None


def upgrade():
    # `checkfirst` no existe en create_table, así que se consulta el inspector:
    # en dev la tabla ya puede estar creada por el create_all del arranque.
    bind = op.get_bind()
    if 'adjuntos' in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        'adjuntos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('propiedad_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('nombre_original', sa.String(), nullable=False),
        sa.Column('mime', sa.String(), nullable=True),
        sa.Column('tamano', sa.Integer(), nullable=True),
        sa.Column('subido_en', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['propiedad_id'], ['propiedades.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('adjuntos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_adjuntos_propiedad_id'),
                              ['propiedad_id'], unique=False)


def downgrade():
    with op.batch_alter_table('adjuntos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_adjuntos_propiedad_id'))
    op.drop_table('adjuntos')
