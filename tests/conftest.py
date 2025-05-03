#! /usr/bin/env python3

import pytest
import sqlalchemy as sa
from fixtures.containers import *
from fixtures.mediawiki import *
from fixtures.postgresql import *
from fixtures.title_context import *

import ws.db.schema as schema
from ws.client.api import API
from ws.db.database import Database


# disable rate-limiting for tests
def pytest_configure(config):
    import ws
    ws._tests_are_running = True

def pytest_unconfigure(config):
    import ws
    del ws._tests_are_running

@pytest.fixture(scope="session")
def api_archwiki():
    """
    Return an API instance with anonymous connection to wiki.archlinux.org
    """
    # NOTE: anonymous, will be very slow for big data!
    api_url = "https://wiki.archlinux.org/api.php"
    index_url = "https://wiki.archlinux.org/index.php"
    session = API.make_session()
    return API(api_url, index_url, session)

class TestingDatabase(Database):
    def clear(self):
        # drop all existing tables
        metadata = sa.MetaData(bind=self.engine)
        metadata.reflect()
        metadata.drop_all()

        # recreate the tables
        self.metadata = sa.MetaData(bind=self.engine)
        schema.create_tables(self.metadata)

    def dump(self, table=None):
        if table is None:
            raise NotImplementedError
        else:
            print("\nTable {} contains:".format(table.name))
            result = self.engine.execute(table.select())
            from pprint import pprint
            for row in result:
                pprint(row)
        print()

@pytest.fixture(scope="function")
def db(pg_engine):
    """
    Return a Database instance bound to the engine fixture.
    """
    return TestingDatabase(pg_engine)
