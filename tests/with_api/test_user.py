#! /usr/bin/env python3

from nose.tools import assert_equals, assert_false, raises
from nose.plugins.attrib import attr

from . import fixtures

from ws.core.api import LoginFailed

@attr(speed="slow")
class test_user:
    """
    Tests intended mostly for detecting changes in the ArchWiki configuration.
    """

    props_data = {
        # TODO
#        "name": "", # IP address for anonymous
        "id": 0,  # 0 for anonymous
        "blockinfo": None,
        "hasmsg": None,
        "groups": ["*"],
        "implicitgroups": ["*"],
        "rights": [
            "createaccount",
            "read",
            "createpage",
            "createtalk",
            "editmyusercss",
            "editmyuserjs",
            "viewmywatchlist",
            "editmywatchlist",
            "viewmyprivateinfo",
            "editmyprivateinfo",
            "editmyoptions",
            "abusefilter-log-detail",
            "abusefilter-view",
            "abusefilter-log"
        ],
        "changeablegroups": {
            "add": [],
            "remove": [],
            "add-self": [],
            "remove-self": []
        },
        "editcount": 0,
        "ratelimits": {},
        "email": "",
        "realname": "",
        "registrationdate": None,
        "unreadcount": 0,
    }

    def test_coverage(self):
        paraminfo = fixtures.api.call_api(action="paraminfo", modules="query+userinfo")
        properties = set(paraminfo["modules"][0]["parameters"][0]["type"])
        assert_equals(properties - {"preferencestoken"}, fixtures.api.user.properties - {"name", "id"})

    def test_props(self):
        fixtures.api.user.fetch(list(self.props_data))
        def tester(propname, expected):
            assert_equals(getattr(fixtures.api.user, propname), expected)
        for propname, expected in self.props_data.items():
            yield tester, propname, expected

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

