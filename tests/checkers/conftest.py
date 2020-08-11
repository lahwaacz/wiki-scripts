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


@pytest.fixture(scope="session")
def req_mock():
    with requests_mock.mock() as mock:
        yield mock


# requests_mock is function-scoped...
@pytest.fixture(scope="session")
def api_mock(session_mocker, title_context):
# FIXME: requests mocking does not work: https://github.com/jamielennox/requests-mock/issues/142
#def api_mock(req_mock):
#    # create the API object
#    api_url = "mock://wiki.archlinux.org/api.php"
#    index_url = "mock://wiki.archlinux.org/index.php"
#    session = API.make_session(ssl_verify=False)
#
#    # register a callback function for dynamic responses
#    # https://requests-mock.readthedocs.io/en/latest/response.html#dynamic-response
#    def api_callback(request, context):
#        print(dir(request))
#        print(request.url)
#        print(request)
#        # defaults
#        context.status_code = 404
#        context.reason = "Missing mock for the query parameters '{}'".format(request.params)
#    req_mock.get(api_url, json=api_callback)
##    req_mock.get(api_url, status_code=404, reason="Missing mocks for the api.php entry point")
#    req_mock.get(index_url, status_code=404, reason="Missing mocks for the index.php entry point")

    # create the API object
    api_url = "https://wiki.archlinux.org/api.php"
    index_url = "https://wiki.archlinux.org/index.php"
    session = API.make_session(ssl_verify=True)
    api = API(api_url, index_url, session)

    # mock the title context class
    mContext = session_mocker.patch("ws.parser_helpers.title.Context", session_mocker.create_autospec(title_context))
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
