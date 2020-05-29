"""rename dummy user to Anonymous

Revision ID: 1124ae67cc01
Revises: c82c483221d6
Create Date: 2020-05-29 12:38:46.536433

"""
from alembic import op
import sqlalchemy as sa

# add our project root into the path so that we can import the "ws" module
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../.."))

import ws.db.sql_types



# revision identifiers, used by Alembic.
revision = '1124ae67cc01'
down_revision = 'c82c483221d6'
branch_labels = None
depends_on = None


def upgrade():
    # create ad-hoc table for data migration
    user = sa.sql.table("user",
                    sa.Column("user_id", sa.types.Integer),
                    sa.Column("user_name", sa.types.UnicodeText)
                    # other columns not needed for the data migration
                )

    # migrate __wiki_scripts_dummy_user__ to Anonymous
    op.execute(
        user.update().where(user.c.user_id == 0).values({"user_name": "Anonymous"})
    )

def downgrade():
    # create ad-hoc table for data migration
    user = sa.sql.table("user",
                    sa.Column("user_id", sa.types.Integer),
                    sa.Column("user_name", sa.types.UnicodeText)
                    # other columns not needed for the data migration
                )

    # migrate Anonymous to __wiki_scripts_dummy_user__
    op.execute(
        user.update().where(user.c.user_id == 0).values({"user_name": "__wiki_scripts_dummy_user__"})
    )
