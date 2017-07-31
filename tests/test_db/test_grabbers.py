#! /usr/bin/env python3

from copy import copy

from ws.db.grabbers import namespace, recentchanges
import ws.db.selects.recentchanges as rcsel

# TODO: monkeypatch api.site.namespaces to avoid API queries

def test_namespace(api, db):
    ns = copy(api.site.namespaces)
#    del ns[-1]
#    del ns[-2]

    g = namespace.GrabberNamespaces(api, db)
    g.update()
    assert namespace.select(db) == ns

    # void update for coverage
    g = namespace.GrabberNamespaces(api, db)
    g.update()
    assert namespace.select(db) == ns

# FIXME: requires authentication to the API, otherwise we don't get past "userhidden" etc.
def test_recentchanges(api, db):
    g = namespace.GrabberNamespaces(api, db)
    g.update()
    g = recentchanges.GrabberRecentChanges(api, db)
    g.update()

    # all supported except "patrolled", which is not public
    prop = {"title", "ids", "user", "userid", "flags", "timestamp", "comment", "sizes", "loginfo", "sha1"}
    api_params = {
        "list": "recentchanges",
        "rcprop": "|".join(prop),
        "rclimit": "max",
    }

    api_list = list(api.list(api_params))
    db_list = list(rcsel.list(db, prop=prop))

    # don't assert the whole lists, otherwise the diff engine won't finish in finite time
    assert len(db_list) == len(api_list)
    for i, entries in enumerate(zip(db_list, api_list)):
        db_entry, api_entry = entries
        # sha1 is needed to unclude the "sha1hidden" flag on deleted revisions,
        # but we haven't synced the revision table yet
        if "sha1" in api_entry:
            del api_entry["sha1"]
        assert db_entry == api_entry
