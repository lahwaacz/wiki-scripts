#! /usr/bin/env python3

from copy import copy

import pytest

import ws.db.grabbers as grabbers
import ws.db.grabbers.namespace
import ws.db.grabbers.tags
import ws.db.grabbers.recentchanges

import ws.db.selects as selects
import ws.db.selects.recentchanges

# TODO: monkeypatch api.site.namespaces to avoid API queries

@pytest.mark.skip(reason="useless test, needs to be migrated to python-bdd")
def test_namespace(api, db):
    ns = copy(api.site.namespaces)
#    del ns[-1]
#    del ns[-2]

    g = grabbers.namespace.GrabberNamespaces(api, db)
    g.update()
    assert grabbers.namespace.select(db) == ns

    # void update for coverage
    g = grabbers.namespace.GrabberNamespaces(api, db)
    g.update()
    assert grabbers.namespace.select(db) == ns

@pytest.mark.skip(reason="useless test, needs to be migrated to python-bdd")
def test_recentchanges(api, db):
    g = grabbers.namespace.GrabberNamespaces(api, db)
    g.update()
    g = grabbers.tags.GrabberTags(api, db)
    g.update()
    g = grabbers.recentchanges.GrabberRecentChanges(api, db)
    g.update()

    # all supported except "patrolled", which is not public
    prop = {"title", "ids", "user", "userid", "flags", "timestamp", "comment", "sizes", "loginfo", "sha1"}
    api_params = {
        "list": "recentchanges",
        "rcprop": "|".join(prop),
        "rclimit": "max",
    }

    api_list = list(api.list(api_params))
    db_list = list(selects.recentchanges.list(db, prop=prop))

    # hack to get past "userhidden" etc. with anonymous connection to the API
    skip_deleted = "deleterevision" not in api.user.rights

    # don't assert the whole lists, otherwise the diff engine won't finish in finite time
    assert len(db_list) == len(api_list)
    for i, entries in enumerate(zip(db_list, api_list)):
        db_entry, api_entry = entries
        # sha1 is needed to include the "sha1hidden" flag on deleted revisions,
        # but we haven't synced the revision table yet
        if "sha1" in api_entry:
            del api_entry["sha1"]

        if skip_deleted:
            # TODO: skip also "userid" and "user" when needed
            if "commenthidden" in db_entry:
                del db_entry["comment"]

        assert db_entry == api_entry
