#! /usr/bin/env python3

import pytest

from ws.client.api import API
from ws.db.database import Database

from fixtures.mysql import mysql_proc, sqlalchemy_connect_url, engine

@pytest.fixture(scope="session")
def api():
    """
    Return an API instance with anonymous connection to wiki.archlinux.org
    """
    # NOTE: anonymous, will be very slow for big data!
    api_url = "https://wiki.archlinux.org/api.php"
    index_url = "https://wiki.archlinux.org/index.php"
    ssl_verify = True
    session = API.make_session(ssl_verify=ssl_verify)
    return API(api_url, index_url, session)

@pytest.fixture(scope="module")
def db(engine):
    """
    Return a Database instance bound to the engine fixture.
    """
    return Database(engine)
