#! /usr/bin/env python3

import pytest

from ws.client.api import LoginFailed

# TODO: pytest attribute
#@attr(speed="slow")
class test_redirects:

    # TODO: mock the API object with custom data, we're testing the algorithms, not queries

    # TODO: tests for resolving double redirects over sections
    # e.g.  [[A]] -> [[B#section]], [[B]] -> [[C]] should be resolved as [[A]] -> [[C#section]]

    redirects = {
        "Main page": None,
        "Main Page": "Main page",
        "ABS": "Arch Build System",
    }

    @pytest.mark.parametrize("source, expected_target", redirects.items())
    def test_resolve_redirects(self, api, source, expected_target):
        assert api.redirects.resolve(source) == expected_target
        # test suite does not contain any double redirect
        assert api.redirects.map.get(source) == expected_target
        assert api.redirects.resolve(expected_target) is None
