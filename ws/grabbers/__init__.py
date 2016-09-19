#!/usr/bin/env python3

import datetime
import logging

from sqlalchemy import select

from ws.client.api import ShortRecentChangesError

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

        # a mapping of ``(action, table)`` tuples to prepared SQL constructs
        # (see self.gen_insert and self.gen_update for ``(action, table)`` tuples)
        self.sql_constructs = {}

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

        The yielded entries should have this format:

        - ``(action, table, entry)`` tuple, where ``action == "insert"``,
          ``table`` is the target table and ``entry`` is a dict corresponding
          to one row in ``table``. The SQL statement is constructed from
          :py:attr:`self.sql_constructs` using the ``(action, table)``
          tuple, entries are aggregated for the _executemany_ execution
          strategy.
        """
        raise NotImplementedError

    def gen_update(self, since):
        """
        A generator for database entries which assumes incremental updates.

        To be implemented in subclasses.

        If :py:exc:`ws.client.api.ShortRecentChangesError` is raised while
        executing this generator, :py:meth:`self.update` starts from scratch
        with :py:meth:`self.insert`. The exception should be raised as soon as
        possible to save unnecessary work.

        The yielded entries should have this format:

        - ``(action, table, entry)`` tuple, where ``action`` is e.g. "insert",
          ``table`` is the target table and ``entry`` is a dict corresponding
          to one row in ``table``. The SQL statement is constructed from
          :py:attr:`self.sql_constructs` using the ``(action, table)``
          tuple, entries are aggregated for the _executemany_ execution
          strategy.
        - Or it can yield SQL statements directly, if the _executemany_
          execution strategy is not applicable (e.g. for DELETE statements).
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
        queues = {}

        # execute all queues, ordered by TARGET_TABLES to avoid errors due to
        # failing foreign keys constraints
        def exec_all():
            for table in self.TARGET_TABLES:
                for action, table_ in queues.keys():
                    if table == table_:
                        queues[action, table].execute()

        for item in gen:
            if isinstance(item, tuple):
                action, table, entry = item
                queues.setdefault( (action, table), DbExecutionQueue(self.db, self.sql_constructs[action, table]) )
                q = queues[action, table]
                need_exec = q.add_entry(entry)
                if need_exec:
                    # execute all queues, even if some are (very) short - otherwise
                    # they may get out-of-sync and cause constraint errors
                    exec_all()
            else:
                with self.db.engine.begin() as conn:
                    conn.execute(item)

        # finalize queues
        exec_all()


class DbExecutionQueue:
    def __init__(self, db, stmt):
        self.db = db
        self.stmt = stmt
        self.entries = []

    def add_entry(self, entry):
        """
        :returns: if the queue should be executed
        """
        self.entries.append(entry)
        if len(self.entries) >= self.db.chunk_size:
            return True
        return False

    def execute(self):
        if self.entries:
            with self.db.engine.begin() as conn:
                conn.execute(self.stmt, self.entries)
            self.entries = []
