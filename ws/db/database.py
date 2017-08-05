#! /usr/bin/env python3

"""
Prerequisites:

1. A pre-configured PostgreSQL database backend with separate database and user
   account. The database should be created with the "C" collation, e.g. create
   the database with
   `createdb -E UNICODE -l C -T template0 -O username dbname`
2. One of the many drivers supported by sqlalchemy, e.g. psycopg2.
"""

from sqlalchemy import create_engine, MetaData, select
from sqlalchemy.engine import Engine
import sqlalchemy.event

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
            self.engine = create_engine(engine_or_url, echo=True)

        # TODO: only for testing
#        metadata = MetaData(bind=self.engine)
#        metadata.reflect()
#        metadata.drop_all()

        self.metadata = MetaData(bind=self.engine)
        schema.create_tables(self.metadata)

    @staticmethod
    def make_url(dialect, driver, username, password, host, database, **kwargs):
        """
        :param str dialect: an SQL dialect (only ``postgresql`` is supported)
        :param str driver: a driver for given SQL dialect supported by
            :py:mod:`sqlalchemy`, e.g. ``psycopg2``
        :param str username: username for database connection
        :param str password: password for database connection
        :param str host: hostname of the database server
        :param str database: database name
        :param dict kwargs: additional parameters added to the query string part
        """
        assert dialect == "postgresql"
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
        group.add_argument("--db-dialect", metavar="DIALECT", choices=["postgresql"],
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


"""
Profiling utilities. Explanation:
https://www.postgresql.org/docs/current/static/using-explain.html

Usage:

>>> from ws.db.database import explain
>>> for row in db.engine.execute(explain(s)):
>>>     print(row[0])
"""

from sqlalchemy import *
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import Executable, ClauseElement, _literal_as_text

class explain(Executable, ClauseElement):
    def __init__(self, stmt, analyze=False):
        self.statement = _literal_as_text(stmt)
        self.analyze = analyze
        # helps with INSERT statements
        self.inline = getattr(stmt, 'inline', None)

@compiles(explain)
def visit_explain(element, compiler, **kw):
    text = "EXPLAIN ANALYZE "
    text += compiler.process(element.statement, **kw)
    return text
