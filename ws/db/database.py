#! /usr/bin/env python3

"""
Prerequisites:

1. A pre-configured MySQL database backend with separate database and account.
2. One of the many drivers supported by sqlalchemy, e.g. pymysql.
"""

from sqlalchemy import create_engine, MetaData, select
from sqlalchemy.engine import Engine

from . import schema

class Database:

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
        metadata = MetaData(bind=self.engine)
        metadata.reflect()
        metadata.drop_all()

        self.metadata = MetaData(bind=self.engine)
        schema.create_tables(self.metadata, self.charset)

        # custom tables
        self.namespace = self.metadata.tables["namespace"]
        self.namespace_name = self.metadata.tables["namespace_name"]

        # supported tables
        self.recentchanges = self.metadata.tables["recentchanges"]
        self.user = self.metadata.tables["user"]
        self.user_groups = self.metadata.tables["user_groups"]
        self.ipblocks = self.metadata.tables["ipblocks"]
        self.protected_titles = self.metadata.tables["protected_titles"]
        self.page_props = self.metadata.tables["page_props"]
        self.page_restrictions = self.metadata.tables["page_restrictions"]
        self.page = self.metadata.tables["page"]
        self.archive = self.metadata.tables["archive"]
        self.revision = self.metadata.tables["revision"]
        self.text = self.metadata.tables["text"]

    @staticmethod
    def make_url(username, password, host, database, **kwargs):
        """
        :param str username: username for database connection
        :param str password: password for database connection
        :param str host: hostname of the database server
        :param str database: database name
        :param dict kwargs: additional parameters added to the query string part
        """
        kwargs["charset"] = Database.charset
        params = "&".join("{0}={1}".format(k, v) for k, v in kwargs.items())
        return "mysql+pymysql://{username}:{password}@{host}/{database}?{params}" \
               .format(username=username,
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
        url = klass.make_url(args.db_user, args.db_password, args.db_host, args.db_name)
        return klass(url)


# The standard MERGE statement is not supported with the standard syntax in
# MySQL, SQLite and others.
# https://en.wikipedia.org/wiki/Merge_(SQL)
#
# Note that statements involving REPLACE are nonstandard and invoke referential
# actions on child rows (e.g. FOREIGN KEY ... ON DELETE CASCADE).

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import Insert

@compiles(Insert, "mysql")
def on_duplicate_key_update(insert, compiler, **kw):
    s = compiler.visit_insert(insert, **kw)
    if insert.kwargs["mysql_on_duplicate_key_update"]:
        columns = [c.name for c in insert.kwargs["mysql_on_duplicate_key_update"]]
        values = ", ".join("{0}=VALUES({0})".format(c) for c in columns)
        return s + " ON DUPLICATE KEY UPDATE " + values
    return s
Insert.argument_for("mysql", "on_duplicate_key_update", None)
