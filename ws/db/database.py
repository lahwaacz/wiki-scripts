#! /usr/bin/env python3

"""
Prerequisites:

1. A pre-configured MySQL or PostgreSQL database backend with separate database
   and account.
2. One of the many drivers supported by sqlalchemy, e.g. pymysql or psycopg2.
"""

from sqlalchemy import create_engine, MetaData, select
from sqlalchemy.engine import Engine

from . import schema

class Database:
    """
    :param engine_or_url:
        either an existing :py:class:`sqlalchemy.engine.Engine` instance or a
        :py:class:`str` representing the URL created by :py:meth:`make_url`
    """

    # it doesn't make sense to even test anything else
    charset = "utf8"

    # TODO: take parameters
    def __init__(self, engine_or_url):
        # limit for continuation
        self.chunk_size = 5000

        if isinstance(engine_or_url, Engine):
            self.engine = engine_or_url
        else:
            self.engine = create_engine(engine_or_url, echo=True, implicit_returning=False)

        # TODO: only for testing
        metadata = MetaData(bind=self.engine)
        metadata.reflect()
        metadata.drop_all()

        self.metadata = MetaData(bind=self.engine)
        schema.create_tables(self.metadata)

    @staticmethod
    def make_url(dialect, driver, username, password, host, database, **kwargs):
        """
        :param str dialect: an SQL dialect, e.g. ``mysql`` or ``postgresql``
        :param str driver: a driver for given SQL dialect supported by
            :py:mod:`sqlalchemy`, e.g. ``pymysql`` or ``psycopg2``
        :param str username: username for database connection
        :param str password: password for database connection
        :param str host: hostname of the database server
        :param str database: database name
        :param dict kwargs: additional parameters added to the query string part
        """
        if dialect == "mysql":
            kwargs["charset"] = Database.charset
        params = "&".join("{0}={1}".format(k, v) for k, v in kwargs.items())
        return "{dialect}+{driver}://{username}:{password}@{host}/{database}?{params}" \
               .format(dialect=dialect,
                       driver=driver,
                       username=username,
                       password=password,
                       host=host,
                       database=database,
                       params=params)

    @staticmethod
    def set_argparser(argparser):
        """
        Add arguments for constructing a :py:class:`Database` object to an
        instance of :py:class:`argparse.ArgumentParser`.

        See also the :py:mod:`ws.config` module.

        :param argparser: an instance of :py:class:`argparse.ArgumentParser`
        """
        import ws.config
        group = argparser.add_argument_group(title="Database parameters")
        group.add_argument("--db-dialect", metavar="DIALECT", choices=["mysql", "postgresql"],
                help="an SQL dialect (default: %(default)s)")
        group.add_argument("--db-driver", metavar="DRIVER",
                help="a driver for given SQL dialect supported by sqlalchemy (default: %(default)s)")
        group.add_argument("--db-user", metavar="USER",
                help="username for database connection (default: %(default)s)")
        group.add_argument("--db-password", metavar="PASSWORD",
                help="password for database connection (default: %(default)s)")
        group.add_argument("--db-host", metavar="HOST",
                help="hostname of the database server (default: %(default)s)")
        group.add_argument("--db-name", metavar="DATABASE",
                help="name of the database (default: %(default)s)")

    @classmethod
    def from_argparser(klass, args):
        """
        Construct a :py:class:`Database` object from arguments parsed by
        :py:class:`argparse.ArgumentParser`.

        :param args:
            an instance of :py:class:`argparse.Namespace`. It is assumed that it
            contains the arguments set by :py:meth:`Connection.set_argparser`.
        :returns: an instance of :py:class:`Connection`
        """
        url = klass.make_url(args.db_dialect, args.db_driver, args.db_user, args.db_password, args.db_host, args.db_name)
        return klass(url)

    def __getattr__(self, table_name):
        """
        Access an existing table in the database.

        :param str table_name: a (lowercase) name of the table
        :returns: a :py:class:`sqlalchemy.schema.Table` instance
        """
        if table_name not in self.metadata.tables:
            raise AttributeError("Table '{}' does not exist in the database.".format(table_name))
        return self.metadata.tables[table_name]


# Fix for DEFERRABLE foreign keys on MySQL,
# see http://docs.sqlalchemy.org/en/latest/dialects/mysql.html#foreign-key-arguments-to-avoid
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.schema import ForeignKeyConstraint

@compiles(ForeignKeyConstraint, "mysql")
def process(element, compiler, **kw):
    element.deferrable = element.initially = None
    return compiler.visit_foreign_key_constraint(element, **kw)


from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import Insert

@compiles(Insert, "mysql")
def on_conflict_update(insert, compiler, **kw):
    """
    An :py:mod:`sqlalchemy` compiler extension for the MySQL-specific
    ``INSERT ... ON DUPLICATE KEY UPDATE`` clause.

    This is our best chance at combining ``INSERT`` and ``UPDATE`` statements.
    The standard `MERGE statement`_ is not supported with the standard syntax in
    MySQL, SQLite and others.

    Note that statements involving ``REPLACE`` are also nonstandard and invoke
    referential actions on child rows (e.g. ``FOREIGN KEY ... ON DELETE CASCADE``).

    .. _`MERGE statement`: https://en.wikipedia.org/wiki/Merge_(SQL)
    """
    s = compiler.visit_insert(insert, **kw)
    if "on_conflict_update" in insert.kwargs:
        columns = [c.name for c in insert.kwargs["on_conflict_update"]]
        values = ", ".join("{0}=VALUES({0})".format(c) for c in columns)
        return s + " ON DUPLICATE KEY UPDATE " + values
    return s
Insert.argument_for("mysql", "on_conflict_update", None)

# FIXME: this always appends to the sqlalchemy's query, but we should insert the clause before the RETURNING clause:
# https://www.postgresql.org/docs/current/static/sql-insert.html
# (as a workaround we pass implicit_returning=False to create_engine to avoid the RETURNING clauses)
@compiles(Insert, "postgresql")
def on_conflict_update(insert, compiler, **kw):
    """
    https://www.postgresql.org/docs/current/static/sql-insert.html#SQL-ON-CONFLICT
    """
    s = compiler.visit_insert(insert, **kw)
    if "on_conflict_update" in insert.kwargs:
        # unlike MySQL, PostgreSQL 9.6 does not support "any" constraint
        # http://stackoverflow.com/questions/35786354/postgres-upsert-on-any-constraint
        assert "on_conflict_constraint" in insert.kwargs
        constraint = ",".join(c.name for c in insert.kwargs["on_conflict_constraint"])
        columns = [c.name for c in insert.kwargs["on_conflict_update"]]
        values = ", ".join("{0}=excluded.{0}".format(c) for c in columns)
        return s + " ON CONFLICT ({0}) DO UPDATE SET ".format(constraint) + values
    return s
Insert.argument_for("postgresql", "on_conflict_update", None)
