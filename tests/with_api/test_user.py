#! /usr/bin/env python3

import pytest

from ws.client.api import LoginFailed

# TODO: pytest attribute
#@attr(speed="slow")
@pytest.mark.skip(reason="The api fixture was removed.")
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
        "ratelimits": {
            # rate limits for anonymous users
            'changetag': {'ip': {'hits': 8, 'seconds': 60}},
            'edit': {'ip': {'hits': 8, 'seconds': 60}},
            'emailuser': {'ip': {'hits': 5, 'seconds': 86400}},
            'linkpurge': {'ip': {'hits': 30, 'seconds': 60}},
            'mailpassword': {'ip': {'hits': 5, 'seconds': 3600}},
            'purge': {'ip': {'hits': 30, 'seconds': 60}},
            'renderfile': {'ip': {'hits': 700, 'seconds': 30}},
            'renderfile-nonstandard': {'ip': {'hits': 70, 'seconds': 30}},
            'stashedit': {'ip': {'hits': 30, 'seconds': 60}},
            'upload': {'ip': {'hits': 8, 'seconds': 60}},
        },
        "email": "",
        "realname": "",
        "registrationdate": None,
        "unreadcount": 0,
        "centralids": {"local": 0},
    }

    def test_coverage(self, api):
        paraminfo = api.call_api(action="paraminfo", modules="query+userinfo")
        properties = set(paraminfo["modules"][0]["parameters"][0]["type"])
        assert properties - {"preferencestoken"} == api.user.properties - {"name", "id"}

    @pytest.fixture(scope="class")
    def api(self, api):
        api.user.fetch(list(self.props_data))
        return api

    @pytest.mark.parametrize("propname, expected", props_data.items())
    def test_props(self, api, propname, expected):
        assert getattr(api.user, propname) == expected

    # this is anonymous test
    def test_is_loggedin(self, api):
        assert api.user.is_loggedin is False

    # check user rights for anonymous users
    def test_user_rights(self, api):
        expected = ["createaccount", "read", "createpage", "createtalk",
                    "editmyusercss", "editmyuserjs", "viewmywatchlist",
                    "editmywatchlist", "viewmyprivateinfo", "editmyprivateinfo",
                    "editmyoptions", "abusefilter-log-detail", "abusefilter-view",
                    "abusefilter-log"]
        assert api.user.rights == expected

