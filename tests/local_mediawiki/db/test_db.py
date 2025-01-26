import os.path

import sqlalchemy as sa
from pytest_bdd import given, parsers, scenarios, then, when

scenarios(".")

@given("an api to an empty MediaWiki")
def empty_mediawiki(mediawiki):
    mediawiki.clear()

@given("an empty wiki-scripts database")
def empty_wsdb(db):
    # TODO: the db is currently function-scoped, so clearing is useless
#    db.clear()
    pass

@when("I synchronize the wiki-scripts database")
def sync_page_tables(mediawiki, db):
    mediawiki.run_jobs()
    db.sync_with_api(mediawiki.api, with_content=True, check_needs_update=False)

@when(parsers.parse("I create page \"{title}\""))
def create_page(mediawiki, title):
    # all pages are created as empty
    mediawiki.api.create(title, "", title)

@when(parsers.re("I move page \"(?P<src_title>.+?)\" to \"(?P<dest_title>.+?)\"(?P<noredirect> without leaving a redirect)?"))
def move_page(mediawiki, src_title, dest_title, noredirect):
    noredirect = False if noredirect is None else True
    mediawiki.api.move(src_title, dest_title, "moved due to BDD tests", noredirect=noredirect)

def _get_content_api(api, title):
    result = api.call_api(action="query", titles=title, prop="revisions", rvprop="content|timestamp")
    page = list(result["pages"].values())[0]
    text = page["revisions"][0]["*"]
    timestamp = page["revisions"][0]["timestamp"]
    return text, timestamp, page["pageid"]

@when(parsers.parse("I edit page \"{title}\" to contain \"{content}\""))
def edit_page(mediawiki, title, content):
    api = mediawiki.api
    old_text, timestamp, pageid = _get_content_api(api, title)
    assert content != old_text
    api.edit(title, pageid, content, timestamp, "setting content to '{}'".format(content))
    # Check that the page really contains what we want. It might actually fail
    # due to the object cache persisting across mediawiki database resets...
    new_text, _, _ = _get_content_api(api, title)
    assert new_text == content

@when(parsers.parse("I protect page \"{title}\""))
def protect_page(mediawiki, title):
    mediawiki.api.call_with_csrftoken(action="protect", title=title, protections="edit=sysop|move=sysop")

@when(parsers.parse("I unprotect page \"{title}\""))
def unprotect_page(mediawiki, title):
    mediawiki.api.call_with_csrftoken(action="protect", title=title, protections="edit=all|move=all")

@when(parsers.parse("I partially protect page \"{title}\""))
def protect_page(mediawiki, title):
    mediawiki.api.call_with_csrftoken(action="protect", title=title, protections="edit=sysop")

@when(parsers.parse("I partially unprotect page \"{title}\""))
def unprotect_page(mediawiki, title):
    mediawiki.api.call_with_csrftoken(action="protect", title=title, protections="edit=all")

@when(parsers.parse("I delete page \"{title}\""))
def delete_page(mediawiki, title):
    mediawiki.api.call_with_csrftoken(action="delete", title=title)

@when(parsers.parse("I undelete page \"{title}\""))
def undelete_page(mediawiki, title):
    mediawiki.api.call_with_csrftoken(action="undelete", title=title)

@when(parsers.parse("I merge page \"{source}\" into \"{target}\""))
def merge_page(mediawiki, source, target):
    params = {
        "action": "mergehistory",
        "from": source,
        "to": target,
    }
    mediawiki.api.call_with_csrftoken(params)

@when(parsers.parse("I delete the oldest revision of page \"{title}\""))
def delete_revision(mediawiki, title):
    pages = mediawiki.api.call_api(action="query", titles=title, prop="revisions", rvprop="ids", rvdir="newer", rvlimit=1)["pages"]
    revid = list(pages.values())[0]["revisions"][0]["revid"]
    params = {
        "action": "revisiondelete",
        "type": "revision",
        "target": title,
        "ids": revid,
        "hide": "content|comment|user",
    }
    mediawiki.api.call_with_csrftoken(params)

@when(parsers.parse("I undelete the oldest revision of page \"{title}\""))
def undelete_revision(mediawiki, title):
    pages = mediawiki.api.call_api(action="query", titles=title, prop="revisions", rvprop="ids", rvdir="newer", rvlimit=1)["pages"]
    revid = list(pages.values())[0]["revisions"][0]["revid"]
    params = {
        "action": "revisiondelete",
        "type": "revision",
        "target": title,
        "ids": revid,
        "show": "content|comment|user",
    }
    mediawiki.api.call_with_csrftoken(params)

@when(parsers.parse("I delete the first logevent"))
def delete_revision(mediawiki):
    logid = mediawiki.api.call_api(action="query", list="logevents", ledir="newer", leprop="ids", lelimit=1)["logevents"][0]["logid"]
    params = {
        "action": "revisiondelete",
        "type": "logging",
        "ids": logid,
        "hide": "content|comment|user",
    }
    mediawiki.api.call_with_csrftoken(params)

@when(parsers.parse("I undelete the first logevent"))
def delete_revision(mediawiki):
    logid = mediawiki.api.call_api(action="query", list="logevents", ledir="newer", leprop="ids", lelimit=1)["logevents"][0]["logid"]
    params = {
        "action": "revisiondelete",
        "type": "logging",
        "ids": logid,
        "show": "content|comment|user",
    }
    mediawiki.api.call_with_csrftoken(params)

@when(parsers.parse("I create tag \"{tag}\""))
def create_tag(mediawiki, tag):
    params = {
        "action": "managetags",
        "operation": "create",
        "tag": tag,
    }
    mediawiki.api.call_with_csrftoken(params)

def _api_get_revisions_of_page(api, title):
    pages = api.call_api(action="query", titles=title, prop="revisions", rvprop="ids", rvlimit="max")["pages"]
    page = list(pages.values())[0]
    if "revisions" in page:
        return [str(r["revid"]) for r in page["revisions"]]
    return []

def _api_get_deleted_revisions_of_page(api, title):
    pages = api.call_api(action="query", titles=title, prop="deletedrevisions", drvprop="ids", drvlimit="max")["pages"]
    page = list(pages.values())[0]
    if "deletedrevisions" in page:
        return [str(r["revid"]) for r in page["deletedrevisions"]]
    return []

@when(parsers.parse("I add tag \"{tag}\" to all revisions of page \"{title}\""))
def tag_revisions(mediawiki, tag, title):
    revids = _api_get_revisions_of_page(mediawiki.api, title) + \
             _api_get_deleted_revisions_of_page(mediawiki.api, title)
    assert revids
    params = {
        "action": "tag",
        "revid": "|".join(revids),
        "add": tag,
    }
    mediawiki.api.call_with_csrftoken(params)

@when(parsers.parse("I remove tag \"{tag}\" from all revisions of page \"{title}\""))
def untag_revisions(mediawiki, tag, title):
    revids = _api_get_revisions_of_page(mediawiki.api, title) + \
             _api_get_deleted_revisions_of_page(mediawiki.api, title)
    assert revids
    params = {
        "action": "tag",
        "revid": "|".join(revids),
        "remove": tag,
    }
    mediawiki.api.call_with_csrftoken(params)

@when(parsers.parse("I add tag \"{tag}\" to the first logevent"))
def tag_logevent(mediawiki, tag):
    logid = mediawiki.api.call_api(action="query", list="logevents", ledir="newer", leprop="ids", lelimit=1)["logevents"][0]["logid"]
    params = {
        "action": "tag",
        "logid": logid,
        "add": tag,
    }
    mediawiki.api.call_with_csrftoken(params)

@when(parsers.parse("I remove tag \"{tag}\" from the first logevent"))
def untag_logevent(mediawiki, tag):
    logid = mediawiki.api.call_api(action="query", list="logevents", ledir="newer", leprop="ids", lelimit=1)["logevents"][0]["logid"]
    params = {
        "action": "tag",
        "logid": logid,
        "remove": tag,
    }
    mediawiki.api.call_with_csrftoken(params)

@when(parsers.parse("I import the testing dataset"))
def import_dataset(mediawiki):
    xml_file = os.path.join(os.path.dirname(__file__), "../../../misc/MediaWiki-import-data.xml")
    xml = open(xml_file, "r").read()
    params = {
        "action": "import",
        "xml": xml,
        "interwikiprefix": "wikipedia",
    }
    mediawiki.api.call_with_csrftoken(params)

# debugging step
@when(parsers.parse("I wait {num:d} seconds"))
def wait(num):
    import time
    time.sleep(num)

@when(parsers.parse("I make a null edit to page \"{title}\""))
def null_edit(mediawiki, title):
    mediawiki.api.call_with_csrftoken(action="edit", title=title, appendtext="")

@then("the recent changes should match")
def check_recentchanges(mediawiki, db):
    # FIXME: Checking the recentchanges table is highly unexplored and unstable. The test is disabled for now...
    return True

    prop = {"title", "ids", "user", "userid", "flags", "timestamp", "comment", "sizes", "loginfo", "patrolled", "sha1", "redirect", "tags"}
    api_params = {
        "list": "recentchanges",
        "rcprop": "|".join(prop),
        "rclimit": "max",
    }

    api_list = list(mediawiki.api.list(api_params))
    db_list = list(db.query(list="recentchanges", rcprop=prop))

    assert db_list == api_list

@then("the logevents should match")
def check_logging(mediawiki, db):
    prop = {"user", "userid", "comment", "timestamp", "title", "ids", "type", "details", "tags"}
    api_params = {
        "list": "logevents",
        "leprop": "|".join(prop),
        "lelimit": "max",
    }

    api_list = list(mediawiki.api.list(api_params))
    db_list = list(db.query(list="logevents", leprop=prop))

    assert db_list == api_list

@then("the allpages lists should match")
def check_allpages_match(mediawiki, db):
    api_params = {
        "list": "allpages",
        "aplimit": "max",
    }

    api_list = list(mediawiki.api.list(api_params))
    db_list = list(db.query(list="allpages"))

    # FIXME: hack around the unknown remote collation
    api_list.sort(key=lambda item: item["pageid"])
    db_list.sort(key=lambda item: item["pageid"])

    assert db_list == api_list

@then(parsers.parse("the {table} table should be empty"))
def check_table_not_empty(db, table):
    t = getattr(db, table)
    s = sa.select([sa.func.count()]).select_from(t)
    result = db.engine.execute(s).fetchone()
    assert result[0] == 0, "The {} table is not empty.".format(table)

@then(parsers.parse("the {table} table should not be empty"))
def check_table_not_empty(db, table):
    t = getattr(db, table)
    s = sa.select([sa.func.count()]).select_from(t)
    result = db.engine.execute(s).fetchone()
    assert result[0] > 0, "The {} table is empty.".format(table)

def _check_allrevisions(mediawiki, db):
    prop = {"ids", "flags", "timestamp", "user", "userid", "size", "sha1", "contentmodel", "comment", "content", "tags"}
    api_params = {
        "list": "allrevisions",
        "arvprop": "|".join(prop),
        "arvlimit": "max",
    }

    api_list = list(mediawiki.api.list(api_params))
    db_list = list(db.query(list="allrevisions", arvprop=prop))

    # FIXME: hack until we have per-page grouping like MediaWiki
    api_revisions = []
    for page in api_list:
        for rev in page["revisions"]:
            rev["pageid"] = page["pageid"]
            rev["ns"] = page["ns"]
            rev["title"] = page["title"]
            api_revisions.append(rev)
    api_revisions.sort(key=lambda item: item["revid"], reverse=True)
    api_list = api_revisions

    # FIXME: WTF, MediaWiki does not restore rev_parent_id when undeleting...
    # https://phabricator.wikimedia.org/T183375
    for rev in db_list:
        del rev["parentid"]
    for rev in api_list:
        del rev["parentid"]

    assert db_list == api_list

def _check_alldeletedrevisions(mediawiki, db):
    prop = {"ids", "flags", "timestamp", "user", "userid", "size", "sha1", "contentmodel", "comment", "content", "tags"}
    api_params = {
        "list": "alldeletedrevisions",
        "adrprop": "|".join(prop),
        "adrlimit": "max",
    }

    api_list = list(mediawiki.api.list(api_params))
    db_list = list(db.query(list="alldeletedrevisions", adrprop=prop))

    # FIXME: hack until we have per-page grouping like MediaWiki
    api_revisions = []
    for page in api_list:
        for rev in page["revisions"]:
            rev["pageid"] = page["pageid"]
            rev["ns"] = page["ns"]
            rev["title"] = page["title"]
            api_revisions.append(rev)
    api_revisions.sort(key=lambda item: item["revid"], reverse=True)
    api_list = api_revisions

    for rev in db_list:
        # FIXME: MediaWiki returns either 0 or the ID of another page with the same title, which was created
        # without undeleting the former revisions, see https://phabricator.wikimedia.org/T183398
        rev["pageid"] = 0
        # FIXME: ar_parent_id is not visible through the API: https://phabricator.wikimedia.org/T183376
        del rev["parentid"]
    # if another page with the same title has been created, new pageid is allocated for it
    # and we don't get pageid=0 for the deleted revisions of the old page
    for rev in api_list:
        rev["pageid"] = 0

    assert db_list == api_list

@then("the revisions should match")
def check_revisions_match(mediawiki, db):
    _check_allrevisions(mediawiki, db)
    _check_alldeletedrevisions(mediawiki, db)
