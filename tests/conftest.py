#! /usr/bin/env python3

from fixtures.containers import *
from fixtures.database import *
from fixtures.mediawiki import *
from fixtures.title_context import *


# disable rate-limiting for tests
def pytest_configure(config):
    import ws
    ws._tests_are_running = True

def pytest_unconfigure(config):
    import ws
    del ws._tests_are_running
