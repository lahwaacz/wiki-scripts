from pprint import pprint

from ws.client import API
from ws.interactive import require_login
from ws.db.database import Database

import ws.db.grabbers as grabbers
import ws.db.grabbers.namespace
import ws.db.grabbers.recentchanges
import ws.db.grabbers.user
import ws.db.grabbers.ipblocks
import ws.db.grabbers.page
import ws.db.grabbers.protected_titles
import ws.db.grabbers.revision
import ws.db.grabbers.logging

import ws.db.selects as selects
import ws.db.selects.recentchanges
import ws.db.selects.logevents
import ws.db.selects.allpages


def main(api, db):
    g = grabbers.namespace.GrabberNamespaces(api, db)
    g.update()
    pprint(grabbers.namespace.select(db))

    # TODO: if no recent change has been added, it's safe to assume that the other tables are up to date as well
    g = grabbers.recentchanges.GrabberRecentChanges(api, db)
    g.update()

    g = grabbers.user.GrabberUsers(api, db)
    g.update()

    g = grabbers.logging.GrabberLogging(api, db)
    g.update()

    g = grabbers.ipblocks.GrabberIPBlocks(api, db)
    g.update()

    g = grabbers.page.GrabberPages(api, db)
    g.update()

    g = grabbers.protected_titles.GrabberProtectedTitles(api, db)
    g.update()

    g = grabbers.revision.GrabberRevisions(api, db)
    g.update()


def select_recentchanges(api, db):
    prop = {"title", "ids", "user", "userid", "flags", "timestamp", "comment", "sizes", "loginfo", "patrolled", "sha1", "redirect"}
    api_params = {
        "list": "recentchanges",
        "rcprop": "|".join(prop),
        "rclimit": "max",
    }

    api_list = list(api.list(api_params))
    db_list = list(selects.recentchanges.list(db, prop=prop))

    print("Checking the recentchanges table...")
    assert len(db_list) == len(api_list)
    for i, entries in enumerate(zip(db_list, api_list)):
        db_entry, api_entry = entries
        # TODO: I don't know what this means
        if "unpatrolled" in api_entry:
            del api_entry["unpatrolled"]

        # FIXME: rolled-back edits are automatically patrolled, but there does not seem to be any way to detect this
        # skipping all patrol checks for now...
        if "patrolled" in api_entry:
            del api_entry["patrolled"]
        if "patrolled" in db_entry:
            del db_entry["patrolled"]

        try:
            assert db_entry == api_entry
        except AssertionError:
            print("db_entry:")
            pprint(db_entry)
            print("api_entry:")
            pprint(api_entry)
            raise


def select_logging(api, db):
    prop = {"user", "userid", "comment", "timestamp", "title", "ids", "type", "details"}
    api_params = {
        "list": "logevents",
        "leprop": "|".join(prop),
        "lelimit": "max",
    }

    api_list = list(api.list(api_params))
    db_list = list(selects.logevents.list(db, prop=prop))

    print("Checking the logging table...")
    assert len(db_list) == len(api_list)
    for i, entries in enumerate(zip(db_list, api_list)):
        db_entry, api_entry = entries
        try:
            assert db_entry == api_entry
        except AssertionError:
            print("db_entry:")
            pprint(db_entry)
            print("api_entry:")
            pprint(api_entry)
            raise


def select_allpages(api, db):
    api_params = {
        "list": "allpages",
        "aplimit": "max",
    }

    api_list = list(api.list(api_params))
    db_list = list(selects.allpages.list(db))

    # FIXME: apparently the ArchWiki's MySQL backend does not use the C locale...
    # difference between C and MySQL's binary collation: "2bwm (简体中文)" should come before "2bwm(简体中文)"
    # TODO: if we connect to MediaWiki running on PostgreSQL, its locale might be anything...
    api_list.sort(key=lambda item: item["pageid"])
    db_list.sort(key=lambda item: item["pageid"])

    print("Checking the page table...")
    assert len(db_list) == len(api_list)
    for i, entries in enumerate(zip(db_list, api_list)):
        db_entry, api_entry = entries
        try:
            assert db_entry == api_entry
        except AssertionError:
            print("db_entry:")
            pprint(db_entry)
            print("api_entry:")
            pprint(api_entry)
            raise


if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser(description="Test grabbers")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    require_login(api)

    # twice to force a void update
    main(api, db)
    main(api, db)

    select_recentchanges(api, db)
    select_logging(api, db)
    select_allpages(api, db)
