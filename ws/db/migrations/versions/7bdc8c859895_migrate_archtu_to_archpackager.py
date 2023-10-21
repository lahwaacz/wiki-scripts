"""migrate archtu to archpackager

Revision ID: 7bdc8c859895
Revises: c2ce51682d04
Create Date: 2023-10-21 14:01:13.602120

"""
from alembic import op
import sqlalchemy as sa

# add our project root into the path so that we can import the "ws" module
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../.."))

import ws.db.sql_types



# revision identifiers, used by Alembic.
revision = '7bdc8c859895'
down_revision = 'c2ce51682d04'
branch_labels = None
depends_on = None


def upgrade():
    user_groups = sa.sql.table(
        "user_groups",
        sa.Column("ug_group", sa.UnicodeText, nullable=False),
        # Other columns not needed for the data migration
    )

    op.execute(
        user_groups
            .update()
            .where(user_groups.c.ug_group == "archtu")
            .values({"ug_group": "archpackager"})
    )


def downgrade():
    user_groups = sa.sql.table(
        "user_groups",
        sa.Column("ug_group", sa.UnicodeText, nullable=False),
        # Other columns not needed for the data migration
    )

    op.execute(
        user_groups
            .update()
            .where(user_groups.c.ug_group == "archpackager")
            .values({"ug_group": "archtu"})
    )
