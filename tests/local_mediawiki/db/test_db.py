from pytest_bdd import scenarios, given, when, then

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
    print(db_list)
