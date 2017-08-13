#! /usr/bin/env python3

import os.path

import sqlalchemy as sa
import pytest

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

# ignore "SAWarning: Predicate of partial index page_main_title ignored during reflection" etc.
@pytest.mark.filterwarnings("ignore:Predicate of partial index")
def test_mw_db(mediawiki):
    db_engine = mediawiki.db_engine
    metadata = sa.MetaData(bind=db_engine, reflect=True)
    conn = db_engine.connect()

    assert "mwuser" in metadata.tables
    t_user = metadata.tables["mwuser"]
    s = sa.select([t_user.c.user_id, t_user.c.user_name])
    result = conn.execute(s)
    users = set()
    for u in result:
        users.add(tuple(u))

    # get the user connected to the API
    my_id = mediawiki.api.user.id
    my_name = mediawiki.api.user.name

    assert users == {(0, "Anonymous"),
                     (my_id, my_name)}
