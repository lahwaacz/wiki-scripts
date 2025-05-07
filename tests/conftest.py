import pytest

import ws
from tests.fixtures.containers import *
from tests.fixtures.database import *
from tests.fixtures.mediawiki import *
from tests.fixtures.title_context import *


# disable rate-limiting for tests
def pytest_configure(config: pytest.Config) -> None:
    ws._tests_are_running = True

def pytest_unconfigure(config: pytest.Config) -> None:
    del ws._tests_are_running
