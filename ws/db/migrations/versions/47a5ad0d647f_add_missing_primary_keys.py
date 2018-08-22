"""add missing primary keys

Revision ID: 47a5ad0d647f
Revises: 47b1aedb5215
Create Date: 2018-08-22 22:29:04.334344

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '47a5ad0d647f'
down_revision = '47b1aedb5215'
branch_labels = None
depends_on = None


def upgrade():
    op.create_primary_key('imagelinks_pkey', 'imagelinks', ['il_from', 'il_to'])
    op.create_primary_key('categorylinks_pkey', 'categorylinks', ['cl_from', 'cl_to'])


def downgrade():
    op.drop_constraint('imagelinks_pkey', table_name='imagelinks')
    op.drop_constraint('categorylinks_pkey', table_name='categorylinks')
