import hashlib
import logging
import re
from typing import Iterator

import httpx
import pytest
import pytest_httpx
import pytest_mock

from ws.checkers import ExtlinkReplacements, URLStatusChecker
from ws.client import API
from ws.parser_helpers.title import Context

# set up the global logger
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
httpx_log = logging.getLogger("httpx")
httpx_log.setLevel(logging.DEBUG)
httpx_log.propagate = True


class Page:
    def __init__(self, text: str = "", last_edit_summary: str = ""):
        self.text = text
        self.original_text = text
        self.last_edit_summary = last_edit_summary


@pytest.fixture(scope="function")
def page() -> Page:
    return Page()


@pytest.fixture(scope="function")
def api_mock(
    httpx_mock: pytest_httpx.HTTPXMock,
    module_mocker: pytest_mock.MockerFixture,
    title_context: Context,
) -> API:
    # create the API object
    api_url = "http://wiki-scripts.localhost/api.php"
    index_url = "http://wiki-scripts.localhost/index.php"
    session = API.make_session()
    api = API(api_url, index_url, session)

    # register a callback function for dynamic responses
    # https://requests-mock.readthedocs.io/en/latest/response.html#dynamic-response
    def api_callback(request: httpx.Request) -> httpx.Response:
        if not str(request.url).startswith(api_url):
            return httpx.Response(status_code=404, text="unexpected request")

        query = request.url.query.decode()
        params: dict[str, str] = dict(pair.split("=") for pair in query.split("&"))
        if params.get("format") == "json" and params.get("action") == "query":
            if params.get("meta") == "siteinfo" and params.get("siprop") == "general":
                # only props which may be relevant for tests are in the mocked response
                general = {
                    "mainpage": "Main page",
                    "base": "http://wiki-scripts.localhost/index.php/Main_page",
                    "sitename": "wiki-scripts tests",
                    "articlepath": "/index.php/$1",
                    "scriptpath": "",
                    "script": "/index.php",
                    "server": "http://wiki-scripts.localhost",
                    "servername": "wiki-scripts.localhost",
                }
                return httpx.Response(
                    status_code=200,
                    json={"batchcomplete": "", "query": {"general": general}},
                )
        # defaults
        return httpx.Response(
            status_code=404, text=f"Missing mock for the query parameters '{query}'"
        )

    httpx_mock.add_callback(
        api_callback, url=re.compile(f"{api_url}.*"), is_optional=True, is_reusable=True
    )
    httpx_mock.add_response(
        url=index_url,
        status_code=404,
        text="Missing mocks for the index.php entry point",
        is_optional=True,
        is_reusable=True,
    )

    # mock the title context class
    mContext = module_mocker.patch(
        "ws.parser_helpers.title.Context", module_mocker.create_autospec(title_context)
    )
    # override the from_api method to always return the fixture
    mContext.from_api = lambda api: title_context

    return api


@pytest.fixture(scope="function")
def SmarterEncryptionList_mock(httpx_mock: pytest_httpx.HTTPXMock) -> None:
    mocked_http_domains = [
        "foo",
        "foo.sourceforge.net",
    ]
    mocked_https_domains = [
        "wiki.archlinux.org",
    ]
    # map of prefixes to the set of full hashes
    hash_map: dict[str, set] = {}
    for domain in mocked_http_domains + mocked_https_domains:
        h = hashlib.sha1(bytes(domain, encoding="utf-8"))
        value = h.hexdigest()
        key = value[:4]
        s = hash_map.setdefault(key, set())
        if domain in mocked_https_domains:
            s.add(value)

    # mock SmarterEncryption queries
    # reference: https://help.duckduckgo.com/duckduckgo-help-pages/privacy/smarter-encryption/
    endpoint = "https://duckduckgo.com/smarter_encryption.js?pv1={hash_prefix}"
    for prefix, hashes in hash_map.items():
        httpx_mock.add_response(
            url=endpoint.format(hash_prefix=prefix),
            json=sorted(hashes),
            is_optional=True,
            is_reusable=True,
        )


# this should be function-scoped so that ExtlinkStatusChecker's requests session
# and URL status caches are properly reset between tests
@pytest.fixture(scope="function")
def extlink_replacements(
    api_mock: API, SmarterEncryptionList_mock: None, httpx_mock: pytest_httpx.HTTPXMock
) -> Iterator[ExtlinkReplacements]:
    # ensure that LRU cache is always empty for each test
    URLStatusChecker.get_url_check.cache_clear()

    checker = ExtlinkReplacements(api_mock, timeout=1, max_retries=1)

    # put session_mock into the checker so that tests can register mocked responses
    checker.httpx_mock = httpx_mock  # type: ignore [attr-defined]
    yield checker
