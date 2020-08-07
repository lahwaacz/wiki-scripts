#! /usr/bin/env python3

import logging

import pytest
import requests_mock
import mwparserfromhell

from ws.checkers import ExtlinkReplacements
from ws.client import API, APIError
import ws.ArchWiki.lang as lang

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


logger = logging.getLogger(__name__)

def require_login(api):
    pass

class ExtlinkReplacementsChecker(ExtlinkReplacements):
    # TODO: refactoring - this should be in some class in the ws.checkers subpackage

    interactive_only_pages = []
    skip_pages = []

    def __init__(self, api, interactive=False, dry_run=False, first=None, title=None, langnames=None, connection_timeout=30, max_retries=3):
        if not dry_run:
            # ensure that we are authenticated
            require_login(api)

        super().__init__(api, None, interactive=interactive, timeout=connection_timeout, max_retries=max_retries)

        self.dry_run = dry_run

        # parameters for self.run()
        self.first = first
        self.title = title
        self.langnames = langnames

    def update_page(self, src_title, text):
        """
        Parse the content of the page and call various methods to update the links.

        :param str src_title: title of the page
        :param str text: content of the page
        :returns: a (text, edit_summary) tuple, where text is the updated content
            and edit_summary is the description of performed changes
        """
        if lang.detect_language(src_title)[0] in self.skip_pages:
            logger.info("Skipping blacklisted page [[{}]]".format(src_title))
            return text, ""
        if lang.detect_language(src_title)[0] in self.interactive_only_pages and self.interactive is False:
            logger.info("Skipping page [[{}]] which is blacklisted for non-interactive mode".format(src_title))
            return text, ""

        logger.info("Parsing page [[{}]] ...".format(src_title))
        # FIXME: skip_style_tags=True is a partial workaround for https://github.com/earwig/mwparserfromhell/issues/40
        wikicode = mwparserfromhell.parse(text, skip_style_tags=True)
        summary_parts = []

        for extlink in wikicode.ifilter_external_links(recursive=True):
            self.update_extlink(wikicode, extlink, summary_parts)

        # deduplicate and keep order
        parts = set()
        parts_add = parts.add
        summary_parts = [part for part in summary_parts if not (part in parts or parts_add(part))]

        edit_summary = ", ".join(summary_parts)
#        if self.interactive is True:
#            edit_summary += " (interactive)"

        return str(wikicode), edit_summary


# this should be function-scoped so that ExtlinkStatusChecker's requests session
# and URL status caches are properly reset between tests
@pytest.fixture(scope="function")
def extlink_replacements(api_mock, mocker):
    checker = ExtlinkReplacementsChecker(api_mock)

    # mock the checker's requests session
    # https://requests-mock.readthedocs.io/en/latest/mocker.html#mocking-specific-sessions
    with requests_mock.Mocker(session=checker.session) as session_mock:
        # put session_mock into the checker so that tests can register mocked responses
        checker.session_mock = session_mock
        yield checker
