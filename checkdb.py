#! /usr/bin/env python3

from pprint import pprint, pformat
import datetime
import traceback
import copy
from collections import OrderedDict
from itertools import chain
import html

import sqlalchemy as sa
import requests.packages.urllib3 as urllib3

from ws.client import API
from ws.interactive import require_login
from ws.db.database import Database, parser_cache
from ws.utils.containers import dmerge
import ws.diff
from ws.parser_helpers.encodings import urldecode


def _pprint_diff(i, db_entry, api_entry, *, key=None):
    if key is not None:
        print(f"\n\nDiff for entry no. {i}: {key}={db_entry[key]}")
        if key == "pageid" and "title" in db_entry:
            print(f"Page title: [[{db_entry['title']}]]")

    # diff shows just the difference
    db_f = pformat(db_entry)
    api_f = pformat(api_entry)
    print(ws.diff.diff_highlighted(db_f, api_f, "db_entry", "api_entry"))

    if key is None:
        # full entries are needed for context
        print("db_entry no. {}:".format(i))
        pprint(db_entry)
        print("api_entry no. {}:".format(i))
        pprint(api_entry)
        print()

def _check_entries(i, db_entry, api_entry, *, key=None):
    try:
        assert db_entry == api_entry
    except AssertionError:
        _pprint_diff(i, db_entry, api_entry, key=key)
        raise

def _check_lists(db_list, api_list, *, key=None, db=None):
    if key is not None and len(db_list) != len(api_list):
        print("Lists have different lengths: {} vs {}".format(len(db_list), len(api_list)))
        db_keys = set(item[key] for item in db_list)
        api_keys = set(item[key] for item in api_list)

        # compare common items
        common_db_items = [item for item in db_list if item[key] in api_keys]
        common_api_items = [item for item in api_list if item[key] in db_keys]
        print("Comparing common items...")
        _check_lists(common_db_items, common_api_items)

        # extra DB items
        extra_db_items = [item for item in db_list if item[key] not in api_keys]
        if extra_db_items:
            print("Extra items from the SQL database:")
            pprint(extra_db_items)

        # extra API items
        extra_api_items = [item for item in api_list if item[key] not in db_keys]
        if extra_api_items:
            print("Extra items from the API:")
            pprint(extra_api_items)

    else:
        try:
            assert len(db_list) == len(api_list), "{} vs. {}".format(len(db_list), len(api_list))
            last_assert_exc = None
            invalid_keys = set()
            for i, entries in enumerate(zip(db_list, api_list)):
                db_entry, api_entry = entries
                try:
                    _check_entries(i, db_entry, api_entry, key=key)
                except AssertionError as e:
                    if key:
                        invalid_keys.add(db_entry[key])
                    last_assert_exc = e
                    pass
            if db and key == "pageid" and invalid_keys:
                cache = parser_cache.ParserCache(db)
                cache.invalidate_pageids(invalid_keys)
                print("Invalidated pageids in the parser cache:", invalid_keys)
            if last_assert_exc is not None:
                raise AssertionError from last_assert_exc
        except AssertionError:
            traceback.print_exc()

def _check_lists_of_unordered_pages(db_list, api_list, *, db=None):
    # FIXME: apparently the ArchWiki's MySQL backend does not use the C locale...
    # difference between C and MySQL's binary collation: "2bwm (简体中文)" should come before "2bwm(简体中文)"
    # TODO: if we connect to MediaWiki running on PostgreSQL, its locale might be anything...
    api_list = sorted(api_list, key=lambda item: item["pageid"])
    db_list = sorted(db_list, key=lambda item: item["pageid"])

    _check_lists(db_list, api_list, key="pageid", db=db)

# pages may be yielded multiple times, so we need to merge them manually
def _squash_list_of_dicts(api_list, *, key="pageid"):
    api_dict = OrderedDict()
    for item in api_list:
        key_value = item[key]
        if key_value not in api_dict:
            api_dict[key_value] = item
        else:
            dmerge(item, api_dict[key_value])
    return list(api_dict.values())

def _deduplicate_list_of_dicts(iterable):
    return [dict(t) for t in {tuple(d.items()) for d in iterable}]


def check_titles(api, db):
    print("Checking individual titles...")

    titles = {"Main page", "Nonexistent"}
    pageids = {1, 2, 3, 4, 5}

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

    for api_entry in api_list:
        # TODO: how the hell should we know...
        if "autopatrolled" in api_entry:
            del api_entry["autopatrolled"]
        # TODO: I don't know what this means
        if "unpatrolled" in api_entry:
            del api_entry["unpatrolled"]

    for entry in chain(db_list, api_list):
        # FIXME: rolled-back edits are automatically patrolled, but there does not seem to be any way to detect this
        # skipping all patrol checks for now...
        if "patrolled" in entry:
            del entry["patrolled"]
        # MediaWiki does not sort tags alphabetically
        entry["tags"].sort()
        # since MW 1.36.1, the "mw-reverted" tag is applied to past revisions
        # that were reverted/undone and wiki-scripts cannot sync that on past
        # revisions
        if "mw-reverted" in entry["tags"]:
            entry["tags"].remove("mw-reverted")

    _check_lists(db_list, api_list, key="rcid")


def check_logging(api, db):
    print("Checking the logging table...")

    since = datetime.datetime.utcnow() - datetime.timedelta(days=30)

    params = {
        "list": "logevents",
        "lelimit": "max",
        "ledir": "newer",
        "lestart": since,
    }
    leprop = {"user", "userid", "comment", "timestamp", "title", "ids", "type", "details", "tags"}

    db_list = list(db.query(**params, leprop=leprop))
    api_list = list(api.list(**params, leprop="|".join(leprop)))

    for entry in db_list:
        # hack for the comparison of infinite protection expirations
        if entry["type"] == "protect" and "details" in entry["params"]:
            details = entry["params"]["details"]
            for item in details:
                if item["expiry"] == "infinite":
                    item["expiry"] = datetime.datetime.max
        # hack for the comparison of moved DeveloperWiki pages
        elif entry["type"] == "move":
            if entry["params"]["target_title"].startswith("DeveloperWiki:"):
                entry["params"]["target_ns"] = 3000
            elif entry["params"]["target_title"].startswith("Talk:DeveloperWiki:"):
                entry["params"]["target_ns"] = -1
                entry["params"]["target_title"] = "Special:Badtitle/" + entry["params"]["target_title"]
        elif entry["type"] == "protect" and entry["action"] == "move_prot":
            if entry["params"]["oldtitle_title"].startswith("DeveloperWiki:"):
                entry["params"]["oldtitle_ns"] = 3000

    _check_lists(db_list, api_list, key="logid")


def check_users(api, db):
    print("Checking the user table...")

    params = {
        "list": "allusers",
        "aulimit": "max",
    }
    auprop = {"groups", "blockinfo", "registration", "editcount"}

    db_list = list(db.query(**params, auprop=auprop))
    api_list = list(api.list(**params, auprop="|".join(auprop)))

    # skip the "Anonymous" dummy user residing in MediaWiki running on PostgreSQL
    api_list = [user for user in api_list if user["userid"] > 0]

    # fix sorting due to potentially different locale
    db_list.sort(key=lambda u: u["name"])
    api_list.sort(key=lambda u: u["name"])

    # sort user groups - neither we or MediaWiki do that
    for user in chain(db_list, api_list):
        user["groups"].sort()

    for user in chain(db_list, api_list):
        # drop autoconfirmed - not reliably refreshed in the SQL database
        # TODO: try to fix that...
        if "autoconfirmed" in user["groups"]:
            user["groups"].remove("autoconfirmed")
        # drop blockedtimestampformatted - unimportant, only in API entries since some MW version
        if "blockedtimestampformatted" in user:
            del user["blockedtimestampformatted"]

    _check_lists(db_list, api_list, key="userid")


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
    for entry in chain(db_list, api_list):
        if "protection" in entry:
            entry["protection"].sort(key=lambda p: p["type"])

    # FIXME: we can't assert page_touched because we track only page edits, not cache invalidations...
    for entry in chain(db_list, api_list):
        del entry["touched"]
        # MW 1.39 does not decode HTML entities
        if "displaytitle" in entry:
            entry["displaytitle"] = html.unescape(entry["displaytitle"])

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

    _check_lists(db_list, api_list, key="pageid")


def check_archive(api, db):
    print("Checking the archive table...")

    params = {
        "list": "alldeletedrevisions",
        "adrlimit": "max",
        "adrdir": "newer",
        "adrslots": "main",
    }
    adrprop = {"ids", "flags", "timestamp", "user", "userid", "size", "sha1", "contentmodel", "comment", "tags"}

    db_list = list(db.query(**params, adrprop=adrprop))
    api_list = list(api.list(**params, adrprop="|".join(adrprop)))

    # compare without the lost revisions - see issue #47
    db_list = [r for r in db_list if r["title"] != "Deleted archived revision (original title lost)"]

    # FIXME: hack until we have per-page grouping like MediaWiki
    api_revisions = []
    for page in api_list:
        for rev in page["revisions"]:
            rev["pageid"] = page["pageid"]
            rev["ns"] = page["ns"]
            rev["title"] = page["title"]
            api_revisions.append(rev)
    api_revisions.sort(key=lambda item: (item["timestamp"], item["revid"]))
    api_list = api_revisions

    # MediaWiki does not sort tags alphabetically
    for rev in api_list:
        rev["tags"].sort()

    _check_lists(db_list, api_list, key="revid")


def check_revisions(api, db):
    print("Checking the revision table...")

    since = datetime.datetime.utcnow() - datetime.timedelta(days=30)

    params = {
        "list": "allrevisions",
        "arvlimit": "max",
        "arvdir": "newer",
        "arvstart": since,
        "arvslots": "main",
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
    api_revisions.sort(key=lambda item: (item["timestamp"], item["revid"]))
    api_list = api_revisions

    for rev in chain(db_list, api_list):
        # FIXME: WTF, MediaWiki does not restore rev_parent_id when undeleting...
        # https://phabricator.wikimedia.org/T183375
        del rev["parentid"]
        # MediaWiki does not sort tags alphabetically
        rev["tags"].sort()
        # since MW 1.36.1, the "mw-reverted" tag is applied to past revisions
        # that were reverted/undone and wiki-scripts cannot sync that on past
        # revisions
        if "mw-reverted" in rev["tags"]:
            rev["tags"].remove("mw-reverted")

    _check_lists(db_list, api_list, key="revid")


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
        "rvslots": "main",
    }

    db_list = list(db.query(**api_params, titles=titles, rvprop=rvprop))
    api_dict = api.call_api(**api_params, action="query", titles="|".join(titles), rvprop="|".join(rvprop))["pages"]
    api_list = list(api_dict.values())

    # first check the lists without revisions
    db_list_copy = copy.deepcopy(db_list)
    api_list_copy = copy.deepcopy(api_list)
    _check_lists(db_list_copy, api_list_copy, key="pageid")

    # then check only the revisions
    for db_page, api_page in zip(db_list, api_list):
        _check_lists(db_page["revisions"], api_page["revisions"], key="revid")


def check_templatelinks(api, db):
    print("Checking the templatelinks table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
        "tllimit": "max",
        "tilimit": "max",
    }
    prop = {"templates", "transcludedin"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))
    api_list = _squash_list_of_dicts(api_list)

    # sort the templates due to different locale (e.g. "Template:Related2" should come after "Template:Related")
    for entry in api_list:
        entry.get("templates", []).sort(key=lambda t: (t["ns"], t["title"]))

    _check_lists_of_unordered_pages(db_list, api_list, db=db)


def check_pagelinks(api, db):
    print("Checking the pagelinks table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
        "pllimit": "max",
        "lhlimit": "max",
    }
    prop = {"links", "linkshere"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))
    api_list = _squash_list_of_dicts(api_list)

    # fix sorting due to different locale
    for page in api_list:
        page.get("links", []).sort(key=lambda d: (d["ns"], d["title"]))
        page.get("linkshere", []).sort(key=lambda d: (d["pageid"]))

    _check_lists_of_unordered_pages(db_list, api_list, db=db)


def check_imagelinks(api, db):
    print("Checking the imagelinks table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
        "imlimit": "max",
    }
    prop = {"images"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))
    api_list = _squash_list_of_dicts(api_list)

    _check_lists_of_unordered_pages(db_list, api_list, db=db)


def check_categorylinks(api, db):
    print("Checking the categorylinks table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
        "cllimit": "max",
    }
    prop = {"categories"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))
    api_list = _squash_list_of_dicts(api_list)

    # drop unsupported automatic categories: http://w.localhost/index.php/Special:TrackingCategories
    automatic_categories = {
        "Category:Indexed pages",
        "Category:Noindexed pages",
        "Category:Pages using duplicate arguments in template calls",
        "Category:Pages with too many expensive parser function calls",
        "Category:Pages containing omitted template arguments",
        "Category:Pages where template include size is exceeded",
        "Category:Hidden categories",
        "Category:Pages with broken file links",
        "Category:Pages where node count is exceeded",
        "Category:Pages where expansion depth is exceeded",
        "Category:Pages with ignored display titles",
        "Category:Pages using invalid self-closed HTML tags",
        "Category:Pages with template loops",
    }
    for page in api_list:
        if "categories" in page:
            page["categories"] = [cat for cat in page["categories"] if cat["title"] not in automatic_categories]
            # remove empty list
            if not page["categories"]:
                del page["categories"]

    _check_lists_of_unordered_pages(db_list, api_list, db=db)


def check_interwiki_links(api, db):
    print("Checking the langlinks and iwlinks tables...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
        "iwlimit": "max",
        "lllimit": "max",
    }
    prop = {"langlinks", "iwlinks"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))
    api_list = _squash_list_of_dicts(api_list)

    # In our database, we store spaces instead of underscores and capitalize first letter.
    def ucfirst(s):
        if s:
            return s[0].upper() + s[1:]
        return s
    for page in api_list:
        for link in chain(page.get("langlinks", []), page.get("iwlinks", [])):
            link["*"] = ucfirst(link["*"].replace("_", " "))
        # deduplicate, [[w:foo]] and [[w:Foo]] should be equivalent
        if "langlinks" in page:
            page["langlinks"] = _deduplicate_list_of_dicts(page["langlinks"])
        if "iwlinks" in page:
            page["iwlinks"] = _deduplicate_list_of_dicts(page["iwlinks"])
        # fix sorting due to different locale
        page.get("langlinks", []).sort(key=lambda d: (d["lang"], d["*"]))
        page.get("iwlinks", []).sort(key=lambda d: (d["prefix"], d["*"]))

    _check_lists_of_unordered_pages(db_list, api_list, db=db)


def check_external_links(api, db):
    print("Checking the externallinks table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
        "ellimit": "max",
    }
    prop = {"extlinks"}

    db_list = list(db.query(**params, prop=prop))
    api_list = list(api.generator(**params, prop="|".join(prop)))
    api_list = _squash_list_of_dicts(api_list)

    hostname = urllib3.util.url.parse_url(api.index_url).host
    def get_hostname(url):
        try:
            return urllib3.util.url.parse_url(url).host
        except urllib3.exceptions.LocationParseError:
            return None

    for page in db_list:
        if "extlinks" in page:
            # MediaWiki does not track external links to its self hostname
            page["extlinks"] = [el for el in page["extlinks"] if get_hostname(el["*"]) != hostname]
            # delete empty list
            if len(page["extlinks"]) == 0:
                del page["extlinks"]
    for page in api_list:
        if "extlinks" in page:
            # MediaWiki has some characters URL-encoded and others decoded
            for el in page["extlinks"]:
                try:
                    el["*"] = urldecode(el["*"])
                except UnicodeDecodeError:
                    pass

    # make sure that extlinks are sorted the same way
    # (MediaWiki does not order the URLs, PostgreSQL ordering does not match Python due to locale)
    for page in chain(db_list, api_list):
        if "extlinks" in page:
            page["extlinks"].sort(key=lambda d: d["*"])

    _check_lists_of_unordered_pages(db_list, api_list, db=db)


def check_redirects(api, db):
    print("Checking the redirects table...")

    params = {
        "generator": "allpages",
        "gaplimit": "max",
        "rdlimit": "max",
    }
    prop = {"redirects"}
    rdprop = {"pageid", "title", "fragment"}

    db_list = list(db.query(**params, prop=prop, rdprop=rdprop))
    api_list = list(api.generator(**params, prop="|".join(prop), rdprop="|".join(rdprop)))
    api_list = _squash_list_of_dicts(api_list)

    for page in db_list:
        for redirect in page.get("redirects", []):
            if "fragment" in redirect:
                # MediaWiki stores URL-decoded fragments
                redirect["fragment"] = urldecode(redirect["fragment"])

    _check_lists_of_unordered_pages(db_list, api_list, db=db)


if __name__ == "__main__":
    import ws.config

    argparser = ws.config.getArgParser(description="Test database synchronization")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)

    argparser.add_argument("--sync", dest="sync", action="store_true", default=True,
            help="synchronize the SQL database with the remote wiki API (default: %(default)s)")
    argparser.add_argument("--no-sync", dest="sync", action="store_false",
            help="opposite of --sync")
    argparser.add_argument("--content-sync-mode", choices=["latest", "all"], default="latest",
            help="mode of revisions content synchronization")
    argparser.add_argument("--parser-cache", dest="parser_cache", action="store_true", default=False,
            help="update parser cache (default: %(default)s)")
    argparser.add_argument("--no-parser-cache", dest="parser_cache", action="store_false",
            help="opposite of --parser-cache")

    args = ws.config.parse_args(argparser)

    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    if args.sync:
        require_login(api)

        db.sync_with_api(api)
        db.sync_revisions_content(api, mode=args.content_sync_mode)

        check_titles(api, db)
        check_specific_titles(api, db)

        check_recentchanges(api, db)
        check_logging(api, db)
        # TODO: select active users
        check_users(api, db)
        check_allpages(api, db)
        check_info(api, db)
        check_pageprops(api, db)
        check_protected_titles(api, db)
        check_archive(api, db)
        check_revisions(api, db)
        check_latest_revisions(api, db)
        check_revisions_of_main_page(api, db)

    if args.parser_cache:
        db.update_parser_cache()

        check_templatelinks(api, db)

        # FIXME:
        #   - mwph can't parse "[[VirtualBox#Installation in EFI mode on VirtualBox < 6.1]]" as a wikilink
        #     (most likely due to the single '<', see https://github.com/earwig/mwparserfromhell/issues/211#issuecomment-570898958 )
        check_pagelinks(api, db)

        check_imagelinks(api, db)
        check_categorylinks(api, db)
        check_interwiki_links(api, db)
        check_external_links(api, db)
        check_redirects(api, db)
