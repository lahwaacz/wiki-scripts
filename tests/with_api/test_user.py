#! /usr/bin/env python3

from nose.tools import assert_equals, assert_false, raises
from nose.plugins.attrib import attr

from . import fixtures

from ws.core.api import LoginFailed

@attr(speed="slow")
class test_user:

    def test_coverage(self):
        paraminfo = fixtures.api.call_api(action="paraminfo", modules="query+userinfo")
        properties = set(paraminfo["modules"][0]["parameters"][0]["type"])
        assert_equals(properties - {"preferencestoken"}, fixtures.api.user.properties - {"name", "id"})

    # this is anonymous test
    def test_is_loggedin(self):
        assert_false(fixtures.api.user.is_loggedin)

    # check user rights for anonymous users
    def test_user_rights(self):
        expected = ["createaccount", "read", "createpage", "createtalk",
                    "editmyusercss", "editmyuserjs", "viewmywatchlist",
                    "editmywatchlist", "viewmyprivateinfo", "editmyprivateinfo",
                    "editmyoptions", "abusefilter-log-detail", "abusefilter-view",
                    "abusefilter-log"]
        assert_equals(fixtures.api.user.rights, expected)

