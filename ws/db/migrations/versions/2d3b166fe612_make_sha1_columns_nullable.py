"""make SHA1 columns nullable

Revision ID: 2d3b166fe612
Revises: b77efd0e9f64
Create Date: 2019-12-24 23:21:46.603662

"""
from alembic import op
import sqlalchemy as sa

# add our project root into the path so that we can import the "ws" module
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../.."))

import ws.db.sql_types

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2d3b166fe612'
down_revision = 'b77efd0e9f64'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('archive', 'ar_sha1',
               existing_type=postgresql.BYTEA(),
               nullable=True,
               server_default=None,
               existing_server_default=sa.text("'\\x'::bytea"))
    op.alter_column('revision', 'rev_sha1',
               existing_type=postgresql.BYTEA(),
               nullable=True,
               server_default=None,
               existing_server_default=sa.text("'\\x'::bytea"))

    # create ad-hoc tables for data migration
    archive = sa.sql.table("archive",
                    sa.Column("ar_sha1", postgresql.BYTEA())
                    # other columns not needed for the data migration
                )
    revision = sa.sql.table("revision",
                    sa.Column("rev_sha1", postgresql.BYTEA())
                    # other columns not needed for the data migration
                )

    # migrate empty data to NULL
    op.execute(
        archive.update().where(archive.c.ar_sha1 == b"").values({"ar_sha1": None})
    )
    op.execute(
        revision.update().where(revision.c.rev_sha1 == b"").values({"rev_sha1": None})
    )


def downgrade():
    # create ad-hoc tables for data migration
    archive = sa.sql.table("archive",
                    sa.Column("ar_sha1", postgresql.BYTEA())
                    # other columns not needed for the data migration
                )
    revision = sa.sql.table("revision",
                    sa.Column("rev_sha1", postgresql.BYTEA())
                    # other columns not needed for the data migration
                )

    # migrate NULL values to empty data
    op.execute(
        archive.update().where(archive.c.ar_sha1 == None).values({"ar_sha1": b""})
    )
    op.execute(
        revision.update().where(revision.c.rev_sha1 == None).values({"rev_sha1": b""})
    )

    op.alter_column('revision', 'rev_sha1',
               existing_type=postgresql.BYTEA(),
               nullable=False,
               server_default=sa.text("'\\x'::bytea"),
               existing_server_default=None)
    op.alter_column('archive', 'ar_sha1',
               existing_type=postgresql.BYTEA(),
               nullable=False,
               server_default=sa.text("'\\x'::bytea"),
               existing_server_default=None)
