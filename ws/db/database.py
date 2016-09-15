#! /usr/bin/env python3

"""
Prerequisites:

1. A pre-configured database backend (e.g. MySQL or PostgreSQL) with separate database and account.
2. Database populated with MediaWiki's scheme: in the MediaWiki tree, this can be found at
    - maintenance/tables.sql for MySQL
    - maintenance/mssql/tables.sql
    - maintenance/oracle/tables.sql
    - maintenance/postgres/tables.sql
3. One of the many drivers supported by sqlalchemy, e.g. pymysql.
"""

from sqlalchemy import create_engine, Table, MetaData

from . import schema

class Database:

    # it doesn't make sense to even test anything else
    charset = "utf8"

    # TODO: take parameters
    def __init__(self):
        # limit for continuation
        self.chunk_size = 5000

        self.engine = create_engine("mysql+pymysql://wiki-scripts:wiki-scripts@localhost/wiki-scripts?charset={charset}".format(charset=self.charset), echo=True)

        # TODO: only for testing
        metadata = MetaData(bind=self.engine)
        metadata.reflect()
        metadata.drop_all()

        self.metadata = MetaData(bind=self.engine)
        schema.create_tables(self.metadata, self.charset)

        # supported tables
        self.protected_titles = self.metadata.tables["protected_titles"]
        self.page_props = self.metadata.tables["page_props"]
        self.page_restrictions = self.metadata.tables["page_restrictions"]
        self.page = self.metadata.tables["page"]
        self.archive = self.metadata.tables["archive"]
        self.revision = self.metadata.tables["revision"]
        self.text = self.metadata.tables["text"]



# TODO:
#   figure out proper updating of the existing entries (UPDATE does not insert new entries, REPLACE is specific to mysql and not easily available in sqlalchemy)

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import Insert

@compiles(Insert)
def update_key(insert, compiler, **kw):
    s = compiler.visit_insert(insert, **kw)
    if "update_key" in insert.kwargs:
        return s + " ON DUPLICATE KEY UPDATE {0}=VALUES({0})".format(insert.kwargs["update_key"])
    return s
