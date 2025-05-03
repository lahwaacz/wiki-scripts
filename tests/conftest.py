#! /usr/bin/env python3

import pytest
from fixtures.containers import *
from fixtures.database import *
from fixtures.mediawiki import *
from fixtures.title_context import *

from ws.client.api import API


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
