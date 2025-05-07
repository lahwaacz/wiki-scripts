import datetime
import tempfile
from typing import Iterable

import pytest
import sqlalchemy as sa

from tests.fixtures.mediawiki import MediaWikiFixtureInstance
from ws.client.api import API, LoginFailed


class test_simple_queries:
    def test_login_failed(self, mediawiki: MediaWikiFixtureInstance) -> None:
        # NOTE: this test requires the mediawiki fixture to be function-scoped,
        #       otherwise the valid user would not be logged in after the test
        with pytest.raises(LoginFailed):
            mediawiki.api.login("wiki-scripts testing invalid user", "invalid password")

    def test_login_cookies(
        self,
        mediawiki: MediaWikiFixtureInstance,
        containers_dotenv_values: dict[str, str | None],
    ) -> None:
        assert mediawiki.api.user.is_loggedin
        api_url = mediawiki.api.api_url
        index_url = mediawiki.api.index_url
        username = containers_dotenv_values.get("MW_USER")
        password = containers_dotenv_values.get("MW_PASSWORD")
        assert username
        assert password

        with tempfile.NamedTemporaryFile(delete_on_close=False) as cookie_file:
            cookie_file.close()

            session_1 = API.make_session(cookie_file=cookie_file.name)
            api_1 = API(api_url, index_url, session_1)
            api_1.login(username, password)
            assert api_1.user.is_loggedin

            with open(cookie_file.name, "r") as f:
                content = f.read()
                assert content.startswith("#LWP-Cookies-2.0"), content
                assert f'UserName="{api_1.user.name}";' in content, content
                assert f"UserID={api_1.user.id};" in content, content

            session_2 = API.make_session(cookie_file=cookie_file.name)
            api_2 = API(api_url, index_url, session_2)
            assert api_2.user.is_loggedin

    def test_max_ids_per_query(self, mediawiki: MediaWikiFixtureInstance) -> None:
        assert mediawiki.api.max_ids_per_query == 500

    def test_list_dummy(self, mediawiki: MediaWikiFixtureInstance) -> None:
        with pytest.raises(ValueError):
            next(mediawiki.api.list())

    def test_list_empty(self, mediawiki: MediaWikiFixtureInstance) -> None:
        pages = mediawiki.api.list(list="allpages", aplimit="max")
        titles = [p["title"] for p in pages]
        # the Main Page is always created after MediaWiki installation
        assert titles == ["Main Page"]

    def test_generator_dummy(self, mediawiki: MediaWikiFixtureInstance) -> None:
        with pytest.raises(ValueError):
            next(mediawiki.api.generator())

    def test_generator_empty(self, mediawiki: MediaWikiFixtureInstance) -> None:
        pages = mediawiki.api.generator(generator="allpages", gaplimit="max")
        titles = [p["title"] for p in pages]
        # the Main Page is always created after MediaWiki installation
        assert titles == ["Main Page"]


class test_actions:
    def _create_page(self, api: API, title: str) -> None:
        # title is also the content (2nd arg) and summary (3rd arg)
        api.create(title, title, title)

    def _check_titles_api(self, api: API, expected_titles: Iterable[str]) -> None:
        pages = api.list(list="allpages", aplimit="max")
        titles = set(p["title"] for p in pages)
        assert titles == set(expected_titles)

    def _check_titles_db(self, engine: sa.Engine, expected_titles: Iterable[str]) -> None:
        metadata = sa.MetaData()
        metadata.reflect(bind=engine)
        t = metadata.tables["page"]
        with engine.connect() as conn:
            # we assume that the tests work only with the main namespace
            s = sa.select(t.c.page_title)
            result = conn.execute(s)
            titles = set(row[0] for row in result)
            assert titles == set(t.replace(" ", "_") for t in expected_titles)

    def test_create(self, mediawiki: MediaWikiFixtureInstance) -> None:
        api = mediawiki.api
        engine = mediawiki.db_engine
        created_titles = {"Main Page"}
        assert api.last_revision_id == 1
        for i in range(1, 5):
            title = "Test {}".format(i)
            self._create_page(api, title)
            # mediawiki.run_jobs()
            created_titles.add(title)
            assert api.last_revision_id == i + 1
        self._check_titles_api(api, created_titles)
        self._check_titles_db(engine, created_titles)

    def _get_content_api(self, api: API, title: str) -> tuple[str, datetime.datetime, int]:
        result = api.call_api(
            action="query", titles=title, prop="revisions", rvprop="content|timestamp"
        )
        page = list(result["pages"].values())[0]
        text = page["revisions"][0]["*"]
        timestamp = page["revisions"][0]["timestamp"]
        return text, timestamp, page["pageid"]

    def test_edit(self, mediawiki: MediaWikiFixtureInstance) -> None:
        api = mediawiki.api
        # there is one edit due to the Main Page
        assert api.oldest_rc_timestamp == api.newest_rc_timestamp
        self._create_page(api, "Test page")
        text, timestamp, pageid = self._get_content_api(api, "Test page")
        text += text
        api.edit("Test page", pageid, text, timestamp, "summary 1")
        new_text, new_timestamp, new_pageid = self._get_content_api(api, "Test page")
        assert new_pageid == pageid
        assert new_text == text
        assert api.oldest_rc_timestamp
        assert api.oldest_rc_timestamp < timestamp
        assert api.newest_rc_timestamp == new_timestamp


class test_query_continue:
    test_titles = ["Test {}".format(i) for i in range(10)]
    all_titles = ["Main Page"] + test_titles

    def test_query_continue_dummy(self, mediawiki: MediaWikiFixtureInstance) -> None:
        with pytest.raises(ValueError):
            next(mediawiki.api.query_continue(params=0))  # type: ignore[arg-type]

    def test_query_continue(self, mediawiki: MediaWikiFixtureInstance) -> None:
        api = mediawiki.api

        for title in self.test_titles:
            api.create(title, title, title)

        q = api.query_continue(action="query", list="allpages", aplimit=1)
        titles = []
        for chunk in q:
            print(chunk)
            titles += [i["title"] for i in chunk["allpages"]]
        assert titles == self.all_titles

    def test_query_continue_params(self, mediawiki: MediaWikiFixtureInstance) -> None:
        api = mediawiki.api

        for title in self.test_titles:
            api.create(title, title, title)

        data = {
            "list": "allpages",
            "aplimit": 1,
        }
        q = api.query_continue(data)
        titles = []
        for chunk in q:
            titles += [i["title"] for i in chunk["allpages"]]
        assert titles == self.all_titles

    def test_query_continue_params_kwargs(self, mediawiki: MediaWikiFixtureInstance) -> None:
        with pytest.raises(ValueError):
            next(mediawiki.api.query_continue(params={"foo": 0}, bar=1))
