"""propiedades: archivada (no se puede publicar)

Revision ID: b3c7d9e41a52
Revises: e7ac4aca1821
Create Date: 2026-11-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c7d9e41a52'
down_revision = 'e7ac4aca1821'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('propiedades', schema=None) as batch_op:
        batch_op.add_column(sa.Column('archivada', sa.Boolean(), nullable=True))
    op.execute("UPDATE propiedades SET archivada = false WHERE archivada IS NULL")


def downgrade():
    with op.batch_alter_table('propiedades', schema=None) as batch_op:
        batch_op.drop_column('archivada')
