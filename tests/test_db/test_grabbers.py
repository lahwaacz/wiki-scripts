#! /usr/bin/env python3

from copy import copy
import datetime

import ws.db.grabbers as grabbers
import ws.db.grabbers.namespace
import ws.db.grabbers.recentchanges
import ws.db.grabbers.user
import ws.db.grabbers.logging
import ws.db.grabbers.page

import ws.db.selects as selects
import ws.db.selects.recentchanges
import ws.db.selects.logevents
import ws.db.selects.allpages

# TODO: monkeypatch api.site.namespaces to avoid API queries

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

def test_recentchanges(api, db):
    g = grabbers.namespace.GrabberNamespaces(api, db)
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

def test_logging(api, db):
    # fixed timestamps for reproducible and fast tests
    now = datetime.datetime.utcnow()
    since = now - datetime.timedelta(days=100)

    g = grabbers.namespace.GrabberNamespaces(api, db)
    g.update()
    g = grabbers.user.GrabberUsers(api, db)
    g.update()
    g = grabbers.logging.GrabberLogging(api, db)
    # fixed timestamp skips init with g.insert(), which is fine for logging
    g.update(since=since)
    g = grabbers.page.GrabberPages(api, db)
    g.update()

    prop = {"user", "userid", "comment", "timestamp", "title", "ids", "type", "details"}
    api_params = {
        "list": "logevents",
        "leprop": "|".join(prop),
        "lelimit": "max",
        "ledir": "newer",
        "lestart": since,
        "leend": now,
    }

    api_list = list(api.list(api_params))
    db_list = list(selects.logevents.list(db, prop=prop, dir="newer", start=since, end=now))

    # don't assert the whole lists, otherwise the diff engine won't finish in finite time
    assert len(db_list) == len(api_list)
    for i, entries in enumerate(zip(db_list, api_list)):
        db_entry, api_entry = entries
        assert db_entry == api_entry

def test_allpages(api, db):
    g = grabbers.namespace.GrabberNamespaces(api, db)
    g.update()
    g = grabbers.page.GrabberPages(api, db)
    g.update()

    api_params = {
        "list": "allpages",
        "aplimit": "max",
    }

    api_list = list(api.list(api_params))
    db_list = list(selects.allpages.list(db))

    # FIXME: hack around the unknown remote collation
    api_list.sort(key=lambda item: item["pageid"])
    db_list.sort(key=lambda item: item["pageid"])

    print("Checking the page table...")
    assert len(db_list) == len(api_list)
    for i, entries in enumerate(zip(db_list, api_list)):
        db_entry, api_entry = entries
        assert db_entry == api_entry
