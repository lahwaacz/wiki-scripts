#! /usr/bin/env python3

import pytest

@pytest.mark.skip(reason="The api fixture was removed.")
class test_redirects:

    # data for monkeypatching
    redirects_data = {
        "Main Page": "Main page",
        "ABS": "Arch Build System",
        "foo": "bar#baz",
        "A1": "B1",
        "B1": "C1",
        "A2": "B2#section",
        "B2": "C2",
        "A3": "B3#section",
        "B3": "C3#section2",
        "x": "y",
        "y": "x",
    }

    # how they should be resolved
    redirects_resolved = {
        "Main page": None,
        "Main Page": "Main page",
        "ABS": "Arch Build System",
        "foo": "bar#baz",
        "A1": "C1",
        "A2": "C2#section",
        "A3": "C3#section2",
        "x": None,
        "y": None,
    }

    # monkeypatch fixture mocking the API object with custom data to avoid expensive
    # queries. After all, we're testing the algorithms, not queries.
    @classmethod
    @pytest.fixture
    def api(klass, api, monkeypatch):
        monkeypatch.setattr(api.redirects, "fetch", lambda *args: klass.redirects_data)
        yield api
        del api.redirects.map

    @pytest.mark.parametrize("source, expected_target", redirects_resolved.items())
    def test_resolve_redirects(self, api, source, expected_target):
        assert api.redirects.resolve(source) == expected_target
