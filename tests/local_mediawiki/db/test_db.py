import sqlalchemy as sa

from pytest_bdd import scenarios, given, when, then, parsers

import ws.db.grabbers as grabbers
import ws.db.grabbers.namespace
import ws.db.grabbers.recentchanges
import ws.db.grabbers.user
import ws.db.grabbers.logging
import ws.db.grabbers.page
import ws.db.grabbers.revision
import ws.db.selects as selects
import ws.db.selects.logevents
import ws.db.selects.allpages
import ws.db.selects.allrevisions
import ws.db.selects.alldeletedrevisions

scenarios(".")

@given("an api to an empty MediaWiki")
def empty_mediawiki(mediawiki):
    mediawiki.clear()

@given("an empty wiki-scripts database")
def empty_wsdb(db):
    # TODO: the db is currently function-scoped, so clearing is useless
#    db.clear()
    pass

@when("I sync the page tables")
def sync_page_tables(mediawiki, db):
    api = mediawiki.api
    g = grabbers.namespace.GrabberNamespaces(api, db)
    g.update()
    g = grabbers.recentchanges.GrabberRecentChanges(api, db)
    g.update()
    g = grabbers.user.GrabberUsers(api, db)
    g.update()
    g = grabbers.logging.GrabberLogging(api, db)
    g.update()
    g = grabbers.page.GrabberPages(api, db)
    g.update()
    g = grabbers.revision.GrabberRevisions(api, db, with_content=True)
    g.update()

@when(parsers.parse("I create page \"{title}\""))
def create_page(mediawiki, title):
    # all pages are created as empty
    mediawiki.api.create(title, "", title)

@when(parsers.re("I move page \"(?P<src_title>.+?)\" to \"(?P<dest_title>.+?)\"(?P<noredirect> without leaving a redirect)?"))
def move_page(mediawiki, src_title, dest_title, noredirect):
    noredirect = False if noredirect is None else True
    # TODO: implement in API
#    mediawiki.api.move(src_title, dest_title, "moved due to BDD tests")
    params = {
        "action": "move",
        "from": src_title,
        "to": dest_title,
        "reason": "moved due to BDD tests",
        "movetalk": "1",
    }
    if noredirect is True:
        params["noredirect"] = "1"
    mediawiki.api.call_with_csrftoken(params)

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

# debugging step
@when(parsers.parse("I wait {num:d} seconds"))
def wait(num):
    import time
    time.sleep(num)

@when(parsers.parse("I make a null edit to page \"{title}\""))
def null_edit(mediawiki, title):
    mediawiki.api.call_with_csrftoken(action="edit", title=title, appendtext="")

@when(parsers.parse("I execute MediaWiki jobs"))
def run_jobs(mediawiki):
    mediawiki.run_jobs()

@then("the logevents should match")
def select_logging(mediawiki, db):
    prop = {"user", "userid", "comment", "timestamp", "title", "ids", "type", "details", "tags"}
    api_params = {
        "list": "logevents",
        "leprop": "|".join(prop),
        "lelimit": "max",
    }

    api_list = list(mediawiki.api.list(api_params))
    db_list = list(selects.logevents.list(db, prop=prop))

    assert db_list == api_list

@then("the allpages lists should match")
def check_allpages_match(mediawiki, db):
    api_params = {
        "list": "allpages",
        "aplimit": "max",
    }

    api_list = list(mediawiki.api.list(api_params))
    db_list = list(selects.allpages.list(db))

    # FIXME: hack around the unknown remote collation
    api_list.sort(key=lambda item: item["pageid"])
    db_list.sort(key=lambda item: item["pageid"])

    assert db_list == api_list

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
    db_list = list(selects.allrevisions.list(db, prop=prop))

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
    db_list = list(selects.alldeletedrevisions.list(db, prop=prop))

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
        # FIXME: MediaWiki sets all pageids of deleted revisions to 0, see https://phabricator.wikimedia.org/T183398
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
