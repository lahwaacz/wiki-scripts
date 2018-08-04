from pprint import pprint
import datetime

import sqlalchemy as sa

from ws.client import API
from ws.interactive import require_login
from ws.db.database import Database


def _check_entries(db_entry, api_entry):
    try:
        assert db_entry == api_entry
    except AssertionError:
        print("db_entry:")
        pprint(db_entry)
        print("api_entry:")
        pprint(api_entry)
        raise

def _check_lists(db_list, api_list):
    assert len(db_list) == len(api_list), "{} vs. {}".format(len(db_list), len(api_list))
    for i, entries in enumerate(zip(db_list, api_list)):
        db_entry, api_entry = entries
        _check_entries(db_entry, api_entry)


def select_recentchanges(api, db):
    print("Checking the recentchanges table...")

    prop = {"title", "ids", "user", "userid", "flags", "timestamp", "comment", "sizes", "loginfo", "patrolled", "sha1", "redirect", "tags"}
    api_params = {
        "list": "recentchanges",
        "rcprop": "|".join(prop),
        "rclimit": "max",
    }

    db_list = list(db.query(list="recentchanges", rcprop=prop))
    api_list = list(api.list(api_params))

    # FIXME: some deleted pages stay in recentchanges, although according to the tests they should be deleted
    s = sa.select([db.page.c.page_id])
    current_pageids = {page["page_id"] for page in db.engine.execute(s)}
    new_api_list = []
    for rc in api_list:
        if "logid" in rc or rc["pageid"] in current_pageids:
            new_api_list.append(rc)
    api_list = new_api_list

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

        _check_entries(db_entry, api_entry)


def select_logging(api, db):
    print("Checking the logging table...")

    prop = {"user", "userid", "comment", "timestamp", "title", "ids", "type", "details", "tags"}
    api_params = {
        "list": "logevents",
        "leprop": "|".join(prop),
        "lelimit": "max",
    }

    db_list = list(db.query(list="logevents", leprop=prop))
    api_list = list(api.list(api_params))

    _check_lists(db_list, api_list)


def select_allpages(api, db):
    print("Checking the page table...")

    api_params = {
        "list": "allpages",
        "aplimit": "max",
    }

    db_list = list(db.query(list="allpages"))
    api_list = list(api.list(api_params))

    # FIXME: apparently the ArchWiki's MySQL backend does not use the C locale...
    # difference between C and MySQL's binary collation: "2bwm (简体中文)" should come before "2bwm(简体中文)"
    # TODO: if we connect to MediaWiki running on PostgreSQL, its locale might be anything...
    api_list.sort(key=lambda item: item["pageid"])
    db_list.sort(key=lambda item: item["pageid"])

    _check_lists(db_list, api_list)


def select_protected_titles(api, db):
    print("Checking the protected_titles table...")

    prop = {"timestamp", "user", "userid", "comment", "expiry", "level"}
    api_params = {
        "list": "protectedtitles",
        "ptlimit": "max",
        "ptprop": "|".join(prop),
    }

    db_list = list(db.query(list="protectedtitles", ptprop=prop))
    api_list = list(api.list(api_params))

    for db_entry, api_entry in zip(db_list, api_list):
        # the timestamps may be off by couple of seconds, because we're looking in the logging table
        if "timestamp" in db_entry and "timestamp" in api_entry:
            if abs(db_entry["timestamp"] - api_entry["timestamp"]) <= datetime.timedelta(seconds=1):
                db_entry["timestamp"] = api_entry["timestamp"]

    _check_lists(db_list, api_list)


def select_revisions(api, db):
    print("Checking the revision table...")

    since = datetime.datetime.utcnow() - datetime.timedelta(days=30)

    prop = {"ids", "flags", "timestamp", "user", "userid", "size", "sha1", "contentmodel", "comment", "tags"}
    api_params = {
        "list": "allrevisions",
        "arvprop": "|".join(prop),
        "arvlimit": "max",
        "arvdir": "newer",
        "arvstart": since,
    }

    db_list = list(db.query(list="allrevisions", arvprop=prop, arvdir="newer", arvstart=since))
    api_list = list(api.list(api_params))

    # FIXME: hack until we have per-page grouping like MediaWiki
    api_revisions = []
    for page in api_list:
        for rev in page["revisions"]:
            rev["pageid"] = page["pageid"]
            rev["ns"] = page["ns"]
            rev["title"] = page["title"]
            api_revisions.append(rev)
    api_revisions.sort(key=lambda item: item["revid"])
    api_list = api_revisions

    # FIXME: WTF, MediaWiki does not restore rev_parent_id when undeleting...
    # https://phabricator.wikimedia.org/T183375
    for rev in db_list:
        del rev["parentid"]
    for rev in api_list:
        del rev["parentid"]

    _check_lists(db_list, api_list)


def select_titles(api, db):
    print("Checking individual titles...")

    titles = {"Main page", "Nonexistent"}
    pageids = {1,2,3,4,5}

    db_list = list(db.query(titles=titles))
    api_list = api.call_api(action="query", titles="|".join(titles))["pages"]

    _check_lists(db_list, api_list)

    api_dict = api.call_api(action="query", pageids="|".join(str(p) for p in pageids))["pages"]
    api_list = list(api_dict.values())
    api_list.sort(key=lambda p: ("missing" not in p, p["pageid"]))
    db_list = list(db.query(pageids=pageids))

    _check_lists(db_list, api_list)


def check_titles(api, db):
    titles = [
        "Main page",
        "en:Main page",
        "wikipedia:Main page",
        "wikipedia:en:Main page",
        "Main page#section",
        "en:Main page#section",
        "wikipedia:Main page#section",
        "wikipedia:en:Main page#section",
    ]
    for title in titles:
        api_title = api.Title(title)
        db_title = db.Title(title)
        assert api_title.context == db_title.context
        assert api_title == db_title


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

    import time
    time1 = time.time()
    db.sync_with_api(api)
    time2 = time.time()
    print("Syncing took {:.2f} seconds.".format(time2 - time1))

    select_titles(api, db)
    check_titles(api, db)

    select_recentchanges(api, db)
    select_logging(api, db)
    select_allpages(api, db)
    select_protected_titles(api, db)
    select_revisions(api, db)
