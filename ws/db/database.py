#! /usr/bin/env python3

"""
Prerequisites:

1. A pre-configured PostgreSQL database backend with separate database and user
   account. The database should be created with the "C" collation, e.g. create
   the database with
   `createdb -E UNICODE -l C -T template0 -O username dbname`
2. One of the many drivers supported by sqlalchemy, e.g. psycopg2.
"""

import os.path

import sqlalchemy as sa
import alembic.config

from . import schema, selects, grabbers, parser_cache
from ..parser_helpers.title import Context, Title

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

        if isinstance(engine_or_url, sa.engine.Engine):
            self.engine = engine_or_url
        else:
            self.engine = sa.create_engine(engine_or_url, echo=False)

        assert self.engine.name == "postgresql"

        self.metadata = sa.MetaData(bind=self.engine)
        schema.create_tables(self.metadata)

        insp = sa.engine.reflection.Inspector.from_engine(self.engine)
        if not insp.get_table_names():
            # Empty database - create all tables from scratch and stamp the
            # most recent alembic revision as "head". From now on the database
            # will have to be migrated by alembic. From the cookbook:
            # http://alembic.zzzcomputing.com/en/latest/cookbook.html#building-an-up-to-date-database-from-scratch
            self.metadata.create_all()
            cfg_path = os.path.join(os.path.dirname(__file__), "../..", "alembic.ini")
            alembic_cfg = alembic.config.Config(cfg_path)
            alembic.command.stamp(alembic_cfg, "head")

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
        group.add_argument("--db-port", metavar="PORT",
                help="port on which the database server listens (default: %(default)s)")
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
        # PostgreSQL defaults to dbname equal to the username, which may not be intended
        if args.db_name is None:
            raise ValueError("Cannot create database connection: db_name cannot be None")

        # The format is basically "{dialect}+{driver}://{username}:{password}@{host}:{port}/{database}?{params}",
        # but the URL class is suitable for omitting empty defaults.
        url = sa.engine.url.URL("{}+{}".format(args.db_dialect, args.db_driver),
                                username=args.db_user,
                                password=args.db_password,
                                host=args.db_host,
                                port=args.db_port,
                                database=args.db_name)
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

    def sync_with_api(self, api, *, with_content=False):
        """
        Sync the local data with a remote MediaWiki instance.

        :param ws.client.api.API api: interface to the remote MediaWiki instance
        :param bool with_content: whether to synchronize the content of all revisions
        """
        grabbers.synchronize(self, api, with_content=with_content)

    def sync_latest_revisions_content(self, api):
        """
        Sync the content of the latest revisions of all pages on the wiki.

        Note that the method :py:meth:`.sync_with_api` should be called prior to
        calling this method.

        :param ws.client.api.API api: interface to the remote MediaWiki instance
        """
        grabbers.GrabberRevisions(api, self).sync_latest_revisions_content()

    def query(self, *args, **kwargs):
        """
        Main interface for the MediaWiki-like database queries.

        TODO: documentation of the parameters (or at least the differences from MediaWiki)
        """
        return selects.query(self, *args, **kwargs)

    def Title(self, title):
        """
        Parse a MediaWiki title.

        :param str title: page title to be parsed
        :returns: a :py:class:`ws.parser_helpers.title.Title` object
        """
        iwmap = selects.get_interwikimap(self)
        namespacenames = selects.get_namespacenames(self)
        namespaces = selects.get_namespaces(self)
        # legaltitlechars are not stored in the database, it will hardly ever
        # change so let's just hardcode it
        legaltitlechars = " %!\"$&'()*,\\-.\\/0-9:;=?@A-Z\\\\^_`a-z~\\x80-\\xFF+"
        context = Context(iwmap, namespacenames, namespaces, legaltitlechars)
        return Title(context, title)

    def update_parser_cache(self):
        """
        Update the parser cache tables.

        Note that the methods :py:meth:`.sync_with_api` and
        :py:meth:`.sync_latest_revisions_content` should be called prior to
        calling this method.
        """
        cache = parser_cache.ParserCache(self)
        cache.update()


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
