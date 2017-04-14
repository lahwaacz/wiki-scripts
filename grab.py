from pprint import pprint

from ws.client import API
from ws.interactive import require_login
from ws.db.database import Database
from ws.db.grabbers import namespace, recentchanges, user, ipblocks, page, protected_titles, revision
import ws.db.grabbers.logging as log  # 'logging' would conflict with the stdlib module
import ws.db.selects.recentchanges as rc
from ws.db.selects import logevents


def main(api, db):
    g = namespace.GrabberNamespaces(api, db)
    g.update()
    pprint(namespace.select(db))

    # TODO: if no recent change has been added, it's safe to assume that the other tables are up to date as well
    g = recentchanges.GrabberRecentChanges(api, db)
    g.update()

    g = user.GrabberUsers(api, db)
    g.update()

    g = log.GrabberLogging(api, db)
    g.update()

    g = ipblocks.GrabberIPBlocks(api, db)
    g.update()

    g = page.GrabberPages(api, db)
    g.update()

    g = protected_titles.GrabberProtectedTitles(api, db)
    g.update()

    g = revision.GrabberRevisions(api, db)
    g.update()


def select_recentchanges(api, db):
    prop = {"title", "ids", "user", "userid", "flags", "timestamp", "comment", "sizes", "loginfo", "patrolled", "sha1", "redirect"}
    api_params = {
        "list": "recentchanges",
        "rcprop": "|".join(prop),
        "rclimit": "max",
    }

    api_list = list(api.list(api_params))
    db_list = list(rc.list(db, prop=prop))

    assert len(db_list) == len(api_list)
    for i, entries in enumerate(zip(db_list, api_list)):
        db_entry, api_entry = entries
        # TODO: I don't know what this means
        if "unpatrolled" in api_entry:
            del api_entry["unpatrolled"]
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
    db_list = list(logevents.list(db, prop=prop))

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
