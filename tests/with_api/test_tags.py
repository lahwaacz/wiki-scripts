import pytest

from ws.client.api import API


@pytest.mark.skip(reason="The api fixture was removed.")
class test_tags:

    # data for monkeypatching
    tag_data = [
        {"name": "a", "source": ["manual"], "active": ""},
        {"name": "b", "source": ["extension", "manual"], "active": ""},
        {"name": "c", "source": ["extension"], "active": ""},
        {"name": "d", "source": ["manual"]},
    ]

    tag_names = {
        "all": {"a", "b", "c", "d"},
        "active": {"a", "b", "c"},
        "manual": {"a", "b", "d"},
        "extension": {"b", "c"},
        "applicable": {"a", "b"},
    }

    # monkeypatch fixture mocking the API object with custom data to avoid queries
    @classmethod
    @pytest.fixture
    def api(klass, api: API, monkeypatch: pytest.MonkeyPatch) -> API:
        monkeypatch.setattr(api.tags, "_tags", klass.tag_data)
        return api

    @pytest.mark.parametrize("attr, expected", tag_names.items())
    def test_resolve_redirects(self, api: API, attr: str, expected: set[str]) -> None:
        assert getattr(api.tags, attr) == expected
