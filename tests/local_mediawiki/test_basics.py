#! /usr/bin/env python3

import os.path

def test_server_root(mw_server_root):
#    print("MediaWiki server root is {}".format(mw_server_root))
    assert os.path.isdir(mw_server_root)
    assert os.path.isfile(os.path.join(mw_server_root, "api.php"))
    assert os.path.isfile(os.path.join(mw_server_root, "index.php"))
    assert os.path.isfile(os.path.join(mw_server_root, "load.php"))

def test_mediawiki(mediawiki):
    api = mediawiki.api
    db_engine = mediawiki.db_engine
    assert api.user.is_loggedin
    assert "sysop" in api.user.groups
