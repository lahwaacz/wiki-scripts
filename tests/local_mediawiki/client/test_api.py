#! /usr/bin/env python3

import sqlalchemy as sa

import pytest

from ws.client.api import LoginFailed

class test_simple_queries:
# TODO: figure out how to restore the fixture state after the test
#    @raises(LoginFailed)
#    def test_login_failed(self, mediawiki):
#        mediawiki.api.login("wiki-scripts testing invalid user", "invalid password")

    def test_max_ids_per_query(self, mediawiki):
        assert mediawiki.api.max_ids_per_query == 500

    def test_list_dummy(self, mediawiki):
        with pytest.raises(ValueError):
            next(mediawiki.api.list())

    def test_list_empty(self, mediawiki):
        mediawiki.clear()
        pages = mediawiki.api.list(list="allpages", aplimit="max")
        titles = [p["title"] for p in pages]
        assert titles == []

    def test_generator_dummy(self, mediawiki):
        with pytest.raises(ValueError):
            next(mediawiki.api.generator())

    def test_generator_empty(self, mediawiki):
        mediawiki.clear()
        pages = mediawiki.api.generator(generator="allpages", gaplimit="max")
        titles = [p["title"] for p in pages]
        assert titles == []

class test_actions:
    def _create_page(self, api, title):
        # title is also the content (2nd arg) and summary (3rd arg)
        api.create(title, title, title)

    def _check_titles_api(self, api, expected_titles):
        pages = api.list(list="allpages", aplimit="max")
        titles = set(p["title"] for p in pages)
        assert titles == set(expected_titles)

    def _check_titles_db(self, engine, expected_titles):
        metadata = sa.MetaData(bind=engine, reflect=True)
        conn = engine.connect()
        t = metadata.tables["page"]
        # we assume that the tests work only with the main namespace
        s = sa.select([t.c.page_title])
        result = conn.execute(s)
        titles = set(row[0] for row in result)
        assert titles == set(t.replace(" ", "_") for t in expected_titles)

    # ignore "SAWarning: Predicate of partial index page_main_title ignored during reflection" etc.
    @pytest.mark.filterwarnings("ignore:Predicate of partial index")
    def test_create(self, mediawiki):
        mediawiki.clear()
        api = mediawiki.api
        engine = mediawiki.db_engine
        created_titles = set()
        for i in range(5):
            title = "Test {}".format(i)
            self._create_page(api, title)
            created_titles.add(title)
        self._check_titles_api(api, created_titles)
        self._check_titles_db(engine, created_titles)

    def _get_content_api(self, api, title):
        result = api.call_api(action="query", titles=title, prop="revisions", rvprop="content|timestamp")
        page = list(result["pages"].values())[0]
        text = page["revisions"][0]["*"]
        timestamp = page["revisions"][0]["timestamp"]
        return text, timestamp, page["pageid"]

    def test_edit(self, mediawiki):
        mediawiki.clear()
        api = mediawiki.api
        self._create_page(api, "Test page")
        text, timestamp, pageid = self._get_content_api(api, "Test page")
        text += text
        api.edit("Test page", pageid, text, timestamp, "summary 1")
        new_text, new_timestamp, new_pageid = self._get_content_api(api, "Test page")
        assert new_pageid == pageid
        assert new_text == text

    def test_last_revision_id(self, mediawiki):
        mediawiki.clear()
        api = mediawiki.api
        assert api.last_revision_id is None
        self._create_page(api, "Test 1")
        assert api.last_revision_id == 1
        self._create_page(api, "Test 2")
        assert api.last_revision_id == 2

class test_query_continue:
    titles = ["Test {}".format(i) for i in range(10)]

    def test_query_continue_dummy(self, mediawiki):
        with pytest.raises(ValueError):
            next(mediawiki.api.query_continue(params=0))

    def test_query_continue(self, mediawiki):
        mediawiki.clear()
        api = mediawiki.api

        for title in self.titles:
            api.create(title, title, title)

        q = api.query_continue(action="query", list="allpages", aplimit=1)
        titles = []
        for chunk in q:
            print(chunk)
            titles += [i["title"] for i in chunk["allpages"]]
        assert titles == self.titles

    def test_query_continue_params(self, mediawiki):
        mediawiki.clear()
        api = mediawiki.api

        for title in self.titles:
            api.create(title, title, title)

        data = {
            "list": "allpages",
            "aplimit": 1,
        }
        q = api.query_continue(data)
        titles = []
        for chunk in q:
            titles += [i["title"] for i in chunk["allpages"]]
        assert titles == self.titles

    def test_query_continue_params_kwargs(self, mediawiki):
        with pytest.raises(ValueError):
            next(mediawiki.api.query_continue(params={"foo": 0}, bar=1))
