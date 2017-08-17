from pytest_bdd import scenarios, given, when, then, parsers

import ws.db.grabbers as grabbers
import ws.db.grabbers.namespace
import ws.db.grabbers.page
import ws.db.selects as selects
import ws.db.selects.allpages

scenarios("pages.feature")

@given("an api to an empty MediaWiki")
def empty_mediawiki(mediawiki):
    mediawiki.clear()

@given("an empty wiki-scripts database")
def empty_wsdb(db):
    db.clear()

@when("I sync the page tables")
def sync_page_tables(mediawiki, db):
    api = mediawiki.api
    g = grabbers.namespace.GrabberNamespaces(api, db)
    g.update()
    g = grabbers.page.GrabberPages(api, db)
    g.update()

@when(parsers.parse("I create page \"{title}\""))
def create_page(mediawiki, title):
    mediawiki.api.create(title, title, title)

@when(parsers.parse("I move page \"{src_title}\" to \"{dest_title}\""))
def move_page(mediawiki, src_title, dest_title):
    # TODO: implement in API
#    mediawiki.api.move(src_title, dest_title, "moved due to BDD tests")
    params = {
        "action": "move",
        "from": src_title,
        "to": dest_title,
        "reason": "moved due to BDD tests",
        "movetalk": "1",
    }
    mediawiki.api.call_with_csrftoken(params)

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
