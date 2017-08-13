#! /usr/bin/env python3

import os.path

def test_server_root(mw_server_root):
#    print("MediaWiki server root is {}".format(mw_server_root))
    assert os.path.isdir(mw_server_root)
    assert os.path.isfile(os.path.join(mw_server_root, "api.php"))
    assert os.path.isfile(os.path.join(mw_server_root, "index.php"))
    assert os.path.isfile(os.path.join(mw_server_root, "load.php"))

def test_mw_api(mediawiki):
    api = mediawiki.api
    assert api.user.is_loggedin
    assert "sysop" in api.user.groups

    expected_rights = {
        "createpage",
        "createtalk",
        "writeapi",
        "apihighlimits",
        "noratelimit",
        "interwiki",
        "delete",
        "bigdelete",
        "deleterevision",
        "deletelogentry",
        "deletedhistory",
        "deletedtext",
        "browsearchive",
        "mergehistory",
        "autopatrol",
        "patrol",
    }
    # pytest's assertion does not show diff for subset checks...
    for right in expected_rights:
        assert right in api.user.rights
