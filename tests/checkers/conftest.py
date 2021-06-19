#! /usr/bin/env python3

import logging

import pytest
import requests_mock

from ws.client import API
from ws.checkers import ExtlinkReplacements

# set up the global logger
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True


class Page:
    def __init__(self, text="", last_edit_summary=""):
        self.text = text
        self.original_text = text
        self.last_edit_summary = last_edit_summary

@pytest.fixture(scope="function")
def page():
    return Page()


# requests_mock is function-scoped, so we need a custom module-scoped fixture
# Note that it should not be session-scoped, since e.g. tests/local_mediawiki/
# rely on making actual connections to other fixtures.
@pytest.fixture(scope="module")
def req_mock():
    with requests_mock.mock() as mock:
        yield mock

@pytest.fixture(scope="module")
def api_mock(req_mock, module_mocker, title_context):
    # create the API object
    api_url = "http://wiki-scripts.localhost/api.php"
    index_url = "http://wiki-scripts.localhost/index.php"
    session = API.make_session(ssl_verify=False)
    api = API(api_url, index_url, session)

    # register a callback function for dynamic responses
    # https://requests-mock.readthedocs.io/en/latest/response.html#dynamic-response
    def api_callback(request, context):
        params = request.qs
        if params.get("format") == ["json"] and params.get("action") == ["query"]:
            if params.get("meta") == ["siteinfo"] and params.get("siprop") == ["general"]:
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
                return {"batchcomplete": "", "query": {"general": general}}
        # defaults
        context.status_code = 404
        context.reason = "Missing mock for the query parameters '{}'".format(request.qs)
    req_mock.get(api_url, json=api_callback)
    req_mock.get(index_url, status_code=404, reason="Missing mocks for the index.php entry point")

    # mock the title context class
    mContext = module_mocker.patch("ws.parser_helpers.title.Context", module_mocker.create_autospec(title_context))
    # override the from_api method to always return the fixture
    mContext.from_api = lambda api: title_context

    return api


# this should be function-scoped so that ExtlinkStatusChecker's requests session
# and URL status caches are properly reset between tests
@pytest.fixture(scope="function")
def extlink_replacements(api_mock):
    checker = ExtlinkReplacements(api_mock, None)

    # mock the checker's requests session
    # https://requests-mock.readthedocs.io/en/latest/mocker.html#mocking-specific-sessions
    with requests_mock.Mocker(session=checker.session) as session_mock:
        # put session_mock into the checker so that tests can register mocked responses
        checker.session_mock = session_mock
        yield checker
