"""allow redirects to special namespaces

Revision ID: 53c1e2e65d94
Revises: c4c0733acb37
Create Date: 2018-08-27 20:59:27.167582

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '53c1e2e65d94'
down_revision = 'c4c0733acb37'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('check_namespace', 'redirect')


def downgrade():
    op.create_check_constraint('check_namespace', 'redirect', 'rd_namespace >= 0')
