from pprint import pprint
import datetime
import traceback
import copy

import sqlalchemy as sa

from ws.client import API
from ws.interactive import require_login
from ws.db.database import Database


def _check_entries(i, db_entry, api_entry):
    try:
        assert db_entry == api_entry
    except AssertionError:
        print("db_entry no. {}:".format(i))
        pprint(db_entry)
        print("api_entry no. {}:".format(i))
        pprint(api_entry)
        raise

def _check_lists(db_list, api_list):
    try:
        assert len(db_list) == len(api_list), "{} vs. {}".format(len(db_list), len(api_list))
        for i, entries in enumerate(zip(db_list, api_list)):
            db_entry, api_entry = entries
            _check_entries(i, db_entry, api_entry)
    except AssertionError:
        traceback.print_exc()

def _check_lists_of_unordered_pages(db_list, api_list):
    # FIXME: apparently the ArchWiki's MySQL backend does not use the C locale...
    # difference between C and MySQL's binary collation: "2bwm (简体中文)" should come before "2bwm(简体中文)"
    # TODO: if we connect to MediaWiki running on PostgreSQL, its locale might be anything...
    api_list = sorted(api_list, key=lambda item: item["pageid"])
    db_list = sorted(db_list, key=lambda item: item["pageid"])

    _check_lists(db_list, api_list)


def check_titles(api, db):
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


def check_specific_titles(api, db):
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


def check_recentchanges(api, db):
    print("Checking the recentchanges table...")

    params = {
        "list": "recentchanges",
        "rclimit": "max",
    }
    rcprop = {"title", "ids", "user", "userid", "flags", "timestamp", "comment", "sizes", "loginfo", "patrolled", "sha1", "redirect", "tags"}

    db_list = list(db.query(**params, rcprop=rcprop))
    api_list = list(api.list(**params, rcprop="|".join(rcprop)))

    # FIXME: some deleted pages stay in recentchanges, although according to the tests they should be deleted
    s = sa.select([db.page.c.page_id])
    current_pageids = {page["page_id"] for page in db.engine.execute(s)}
    new_api_list = []
    for rc in api_list:
        if "logid" in rc or rc["pageid"] in current_pageids:
            new_api_list.append(rc)
    api_list = new_api_list

    try:
        assert len(db_list) == len(api_list), "{} vs {}".format(len(db_list), len(api_list))
        for i, entries in enumerate(zip(db_list, api_list)):
            db_entry, api_entry = entries
            # TODO: how the hell should we know...
            if "autopatrolled" in api_entry:
                del api_entry["autopatrolled"]
            # TODO: I don't know what this means
            if "unpatrolled" in api_entry:
                del api_entry["unpatrolled"]

            # FIXME: rolled-back edits are automatically patrolled, but there does not seem to be any way to detect this
            # skipping all patrol checks for now...
            if "patrolled" in api_entry:
                del api_entry["patrolled"]
            if "patrolled" in db_entry:
                del db_entry["patrolled"]

            _check_entries(i, db_entry, api_entry)
    except AssertionError:
        traceback.print_exc()


def check_logging(api, db):
    print("Checking the logging table...")

    params = {
        "list": "logevents",
        "lelimit": "max",
    }
    leprop = {"user", "userid", "comment", "timestamp", "title", "ids", "type", "details", "tags"}

    db_list = list(db.query(**params, leprop=leprop))
    api_list = list(api.list(**params, leprop="|".join(leprop)))

    _check_lists(db_list, api_list)


def check_allpages(api, db):
    print("Checking the page table...")

    params = {
        "list": "allpages",
        "aplimit": "max",
    }

    db_list = list(db.query(**params))
    api_list = list(api.list(**params))

    _check_lists_of_unordered_pages(db_list, api_list)


def check_info(api, db):
    print("Checking prop=info...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
        "prop": "info",
    }
    inprop = {"protection", "displaytitle"}

    db_list = list(db.query(**params, inprop=inprop))
    api_list = list(api.generator(**params, inprop="|".join(inprop)))

    # fix ordering of the protection lists
    for entry in db_list:
        if "protection" in entry:
            entry["protection"].sort(key=lambda p: p["type"])
    for entry in api_list:
        if "protection" in entry:
            entry["protection"].sort(key=lambda p: p["type"])

    # FIXME: we can't assert page_touched because we track only page edits, not cache invalidations...
    for db_entry, api_entry in zip(db_list, api_list):
        del db_entry["touched"]
        del api_entry["touched"]

    _check_lists_of_unordered_pages(db_list, api_list)


def check_pageprops(api, db):
    print("Checking prop=pageprops...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
        "prop": "pageprops",
    }

    db_list = list(db.query(params))
    api_list = list(api.generator(params))

    _check_lists_of_unordered_pages(db_list, api_list)


def check_protected_titles(api, db):
    print("Checking the protected_titles table...")

    params = {
        "list": "protectedtitles",
        "ptlimit": "max",
    }
    ptprop = {"timestamp", "user", "userid", "comment", "expiry", "level"}

    db_list = list(db.query(**params, ptprop=ptprop))
    api_list = list(api.list(**params, ptprop="|".join(ptprop)))

    for db_entry, api_entry in zip(db_list, api_list):
        # the timestamps may be off by couple of seconds, because we're looking in the logging table
        if "timestamp" in db_entry and "timestamp" in api_entry:
            if abs(db_entry["timestamp"] - api_entry["timestamp"]) <= datetime.timedelta(seconds=1):
                db_entry["timestamp"] = api_entry["timestamp"]

    _check_lists(db_list, api_list)


def check_revisions(api, db):
    print("Checking the revision table...")

    since = datetime.datetime.utcnow() - datetime.timedelta(days=30)

    params = {
        "list": "allrevisions",
        "arvlimit": "max",
        "arvdir": "newer",
        "arvstart": since,
    }
    arvprop = {"ids", "flags", "timestamp", "user", "userid", "size", "sha1", "contentmodel", "comment", "tags"}

    db_list = list(db.query(**params, arvprop=arvprop))
    api_list = list(api.list(**params, arvprop="|".join(arvprop)))

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


def check_latest_revisions(api, db):
    print("Checking latest revisions...")

    db_params = {
        "generator": "allpages",
        "prop": "latestrevisions",
    }
    api_params = {
        "generator": "allpages",
        "gaplimit": "max",
        "prop": "revisions",
    }

    db_list = list(db.query(db_params))
    api_list = list(api.generator(api_params))

    _check_lists_of_unordered_pages(db_list, api_list)


def check_revisions_of_main_page(api, db):
    print("Checking revisions of the Main page...")

    titles = {"Main page"}
    rvprop = {"ids", "flags", "timestamp", "user", "userid", "size", "sha1", "contentmodel", "comment", "tags"}
    api_params = {
        "prop": "revisions",
        "rvlimit": "max",
    }

    db_list = list(db.query(**api_params, titles=titles, rvprop=rvprop))
    api_dict = api.call_api(**api_params, action="query", titles="|".join(titles), rvprop="|".join(rvprop))["pages"]
    api_list = list(api_dict.values())

    # first check the lists without revisions
    db_list_copy = copy.deepcopy(db_list)
    api_list_copy = copy.deepcopy(api_list)
    _check_lists(db_list_copy, api_list_copy)

    # then check only the revisions
    for db_page, api_page in zip(db_list, api_list):
        _check_lists(db_page["revisions"], api_page["revisions"])


def check_templatelinks(api, db):
    print("Checking the templatelinks table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
    }
    prop = {"templates", "transcludedin"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))

    _check_lists_of_unordered_pages(db_list, api_list)


def check_pagelinks(api, db):
    print("Checking the pagelinks table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
    }
    prop = {"links", "linkshere"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))

    _check_lists_of_unordered_pages(db_list, api_list)


def check_imagelinks(api, db):
    print("Checking the imagelinks table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
    }
    prop = {"images"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))

    _check_lists_of_unordered_pages(db_list, api_list)


def check_categorylinks(api, db):
    print("Checking the categorylinks table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
    }
    prop = {"categories"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))

    # drop unsupported automatic categories
    automatic_categories = {
        "Category:Pages with broken file links",
        "Category:Pages with template loops",
    }
    for page in api_list:
        if "categories" in page:
            page["categories"] = [cat for cat in page["categories"] if cat["title"] not in automatic_categories]
            # remove empty list
            if not page["categories"]:
                del page["categories"]

    _check_lists_of_unordered_pages(db_list, api_list)


def check_interwiki_links(api, db):
    print("Checking the langlinks and iwlinks tables...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
    }
    prop = {"langlinks", "iwlinks"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))

    # we store spaces instead of underscores in the database
    for page in api_list:
        for langlink in page.get("langlinks", []):
            langlink["*"] = langlink["*"].replace("_", " ")
        for iwlink in page.get("iwlinks", []):
            iwlink["*"] = iwlink["*"].replace("_", " ")

    _check_lists_of_unordered_pages(db_list, api_list)


def check_external_links(api, db):
    print("Checking the externallinks table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
    }
    prop = {"extlinks"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))

    # MediaWiki does not order the URLs
    for page in api_list:
        if "extlinks" in page:
            page["extlinks"].sort(key=lambda d: d["*"])

    _check_lists_of_unordered_pages(db_list, api_list)


def check_redirects(api, db):
    print("Checking the redirects table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
    }
    prop = {"redirects"}
    rdprop = {"pageid", "title", "fragment"}

    db_list = list(db.query(**params, prop=prop, rdprop=rdprop))
    api_list = list(api.generator(**params, prop="|".join(prop), rdprop="|".join(rdprop)))

    _check_lists_of_unordered_pages(db_list, api_list)


if __name__ == "__main__":
    import ws.config
    import ws.logging

    argparser = ws.config.getArgParser(description="Test grabbers")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    argparser.add_argument("--sync", dest="sync", action="store_true", default=True,
            help="synchronize the SQL database with the remote wiki API (default: %(default)s)")
    argparser.add_argument("--no-sync", dest="sync", action="store_false",
            help="opposite of --sync")
    argparser.add_argument("--parser-cache", dest="parser_cache", action="store_true", default=False,
            help="update parser cache (default: %(default)s)")
    argparser.add_argument("--no-parser-cache", dest="parser_cache", action="store_false",
            help="opposite of --parser-cache")

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    if args.sync:
        require_login(api)

        db.sync_with_api(api)
        db.sync_latest_revisions_content(api)

        check_titles(api, db)
        check_specific_titles(api, db)

        check_recentchanges(api, db)
        check_logging(api, db)
        check_allpages(api, db)
        check_info(api, db)
        check_pageprops(api, db)
        check_protected_titles(api, db)
        check_revisions(api, db)
        check_latest_revisions(api, db)
        check_revisions_of_main_page(api, db)

    if args.parser_cache:
        db.update_parser_cache()

        check_templatelinks(api, db)
        check_pagelinks(api, db)
        check_imagelinks(api, db)
        check_categorylinks(api, db)
        check_interwiki_links(api, db)
        check_external_links(api, db)
        check_redirects(api, db)
