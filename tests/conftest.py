import pytest

import ws
from tests.fixtures.containers import *
from tests.fixtures.database import *
from tests.fixtures.mediawiki import *
from tests.fixtures.title_context import *


@pytest.fixture(autouse=True)
def disable_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ws, "_tests_are_running", True, raising=False)
