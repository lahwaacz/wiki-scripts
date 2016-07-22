#! /usr/bin/env python3

from nose.tools import assert_equals, assert_false, raises
from nose.plugins.attrib import attr

from . import fixtures

from ws.client.api import LoginFailed

@attr(speed="slow")
class test_redirects:

    redirects = {
        "Main page": None,
        "Main Page": "Main page",
        "ABS": "Arch Build System",
        }

    @staticmethod
    def _do_test(source, expected_target):
        assert_equals(fixtures.api.redirects.resolve(source), expected_target)
        # test suite does not contain any double redirect
        assert_equals(fixtures.api.redirects.map.get(source), expected_target)
        assert_equals(fixtures.api.redirects.resolve(expected_target), None)

    def test_resolve_redirects(self):
        for source, target in self.redirects.items():
            yield self._do_test, source, target
