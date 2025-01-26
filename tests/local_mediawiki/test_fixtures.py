#! /usr/bin/env python3

import os.path
import warnings

import pytest
import sqlalchemy as sa


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
        "applychangetags",
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

def test_mw_db(mediawiki):
    db_engine = mediawiki.db_engine
    metadata = sa.MetaData(bind=db_engine)
    # ignore "SAWarning: Predicate of partial index foo ignored during reflection"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=sa.exc.SAWarning)
        metadata.reflect()
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
