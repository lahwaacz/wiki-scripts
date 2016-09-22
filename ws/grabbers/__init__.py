#!/usr/bin/env python3

import datetime
import logging

from sqlalchemy import select

from ws.client.api import ShortRecentChangesError
from ws.db.execution import DeferrableExecutionQueue

logger = logging.getLogger(__name__)

class Grabber:

    # class attributes that should be overridden in subclasses

    # Names of tables that are managed by this grabber. Should be ordered such
    # that INSERT statements in this order don't cause constraint errors.
    TARGET_TABLES = []

    def __init__(self, api, db):
        self.api = api
        self.db = db

        if not self.TARGET_TABLES:
            raise Exception("The {} class does not have TARGET_TABLES class attribute.".format(self.__class__.__name__))

    def _set_sync_timestamp(self, timestamp):
        """
        Set a last-sync timestamp for the grabber. Writes into the custom
        ``ws_sync`` tyble.

        :param datetime.datetime timestamp: the new timestamp
        """
        ws_sync = self.db.metadata.tables["ws_sync"]
        ins = ws_sync.insert(mysql_on_duplicate_key_update=[ws_sync.c.wss_timestamp])
        entry = {
            "wss_key": self.__class__.__name__,
            "wss_timestamp": timestamp,
        }

        with self.db.engine.begin() as conn:
            conn.execute(ins, entry)

    def _get_sync_timestamp(self):
        """
        Set a last-sync timestamp for the grabber. Reads from the custom
        ``ws_sync`` tyble.
        """
        ws_sync = self.db.metadata.tables["ws_sync"]
        sel = select([ws_sync.c.wss_timestamp]) \
              .where(ws_sync.c.wss_key == self.__class__.__name__)

        conn = self.db.engine.connect()
        row = conn.execute(sel).fetchone()
        if row:
            return row[0]
        return None

    def gen_insert(self):
        """
        A generator for database entries which assumes that the tables are
        empty.

        To be implemented in subclasses.

        The yielded values are passed to :py:meth:`sqlalchemy.engine.Connection.execute`,
        so the accepted formats for the values are:

        - ``(stmt, entry)`` tuple, where ``stmt`` is an object accepted by
          sqlalchemy's execute method (e.g. plain string or an executable SQL
          statement construct) and ``entry`` is a dict holding the bound
          parameter values to be used in the execution. The execution is
          deferred with :py:class:`ws.db.execution.DeferrableExecutionQueue`
          to exploit the *executemany* execution strategy.
        - Or it can yield ``stmt`` objects directly, if the *executemany*
          execution strategy is not applicable.
        """
        raise NotImplementedError

    def gen_update(self, since):
        """
        A generator for database entries which assumes incremental updates.

        To be implemented in subclasses.

        If :py:exc:`ws.client.api.ShortRecentChangesError` is raised while
        executing this generator, :py:meth:`update` starts from scratch
        with :py:meth:`insert`. The exception should be raised as soon as
        possible to save unnecessary work.

        The yielded values should follow the same rules as the
        :py:meth:`gen_insert` method.
        """
        raise NotImplementedError

    def insert(self):
        # delete everything and start over, otherwise the invalid rows would
        # stay in the tables
        with self.db.engine.begin() as conn:
            for table in self.TARGET_TABLES:
                conn.execute(self.db.metadata.tables[table].delete())

        sync_timestamp = datetime.datetime.utcnow()

        gen = self.gen_insert()
        self.db_execute(gen)

        self._set_sync_timestamp(sync_timestamp)

    def update(self):
        sync_timestamp = datetime.datetime.utcnow()
        since = self._get_sync_timestamp()
        if since is None:
            self.insert()
            return

        try:
            gen = self.gen_update(since)
            self.db_execute(gen)

            self._set_sync_timestamp(sync_timestamp)
        except ShortRecentChangesError:
            logger.warning("The recent changes table on the wiki has been recently purged, starting from scratch.")
            self.insert()
            return

    def db_execute(self, gen):
        with self.db.engine.begin() as conn:
            dfe = DeferrableExecutionQueue(conn, self.db.chunk_size)

            for item in gen:
                if isinstance(item, tuple):
                    # unpack the tuple
                    dfe.execute(*item)
                else:
                    # probably a single value
                    dfe.execute(item)

            dfe.execute_deferred()
