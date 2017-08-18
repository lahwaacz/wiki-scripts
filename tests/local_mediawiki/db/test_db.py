import sqlalchemy as sa

from pytest_bdd import scenarios, given, when, then, parsers

import ws.db.grabbers as grabbers
import ws.db.grabbers.namespace
import ws.db.grabbers.recentchanges
import ws.db.grabbers.user
import ws.db.grabbers.logging
import ws.db.grabbers.page
import ws.db.selects as selects
import ws.db.selects.allpages

scenarios("pages.feature")

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

# debugging step
@when(parsers.parse("I wait {num:d} seconds"))
def wait(num):
    import time
    time.sleep(num)

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
