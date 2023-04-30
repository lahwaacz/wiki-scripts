"""change ipb_deleted to boolean

Revision ID: b22ed21a9d64
Revises: 1124ae67cc01
Create Date: 2023-04-30 22:20:52.855526

"""
from alembic import op
import sqlalchemy as sa

# add our project root into the path so that we can import the "ws" module
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../.."))

import ws.db.sql_types



# revision identifiers, used by Alembic.
revision = 'b22ed21a9d64'
down_revision = '1124ae67cc01'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('ipblocks', 'ipb_deleted',
               existing_type=sa.SMALLINT(),
               existing_server_default=sa.text("'0'::smallint"),
               server_default=None,
               existing_nullable=False,
               nullable=True)
    op.alter_column('ipblocks', 'ipb_deleted',
               existing_type=sa.SMALLINT(),
               type_=sa.Boolean(),
               existing_nullable=False,
               existing_server_default=None,
               postgresql_using="ipb_deleted::int::boolean")
    op.alter_column('ipblocks', 'ipb_deleted',
               existing_type=sa.Boolean(),
               existing_server_default=None,
               server_default=sa.text("'0'::boolean"),
               existing_nullable=True,
               nullable=False)


def downgrade():
    op.alter_column('ipblocks', 'ipb_deleted',
               existing_type=sa.Boolean(),
               existing_server_default=sa.text("'0'::boolean"),
               server_default=None,
               existing_nullable=False,
               nullable=True)
    op.alter_column('ipblocks', 'ipb_deleted',
               existing_type=sa.Boolean(),
               type_=sa.SMALLINT(),
               existing_nullable=False,
               existing_server_default=sa.text("'0'::boolean"),
               postgresql_using="ipb_deleted::boolean::int")
    op.alter_column('ipblocks', 'ipb_deleted',
               existing_type=sa.SMALLINT(),
               existing_server_default=None,
               server_default=sa.text("'0'::smallint"),
               existing_nullable=True,
               nullable=False)
