import re

import mwparserfromhell
from pytest_bdd import given, parsers, scenarios, then, when

from ws.pageupdater import PageUpdater

scenarios("ExtlinkReplacements")


@given(parsers.parse('the wiki site URL is "{site_url}"'))
def set_site_url(extlink_replacements, site_url):
    if not site_url.endswith("/"):
        site_url += "/"
    regex = re.escape(site_url) + r"(?P<pagename>[^\s\?]+)"
    extlink_replacements.wikisite_extlink_regex = re.compile(regex)


@given("these working URLs:")
def mock_url_status_200(extlink_replacements, docstring):
    for line in docstring.splitlines():
        if line.startswith("#"):
            continue
        extlink_replacements.httpx_mock.add_response(
            url=line.strip(), status_code=200, is_optional=True, is_reusable=True
        )


@given("these broken URLs:")
def mock_url_status_404(extlink_replacements, docstring):
    for line in docstring.splitlines():
        if line.startswith("#"):
            continue
        extlink_replacements.httpx_mock.add_response(
            url=line.strip(), status_code=404, is_optional=True, is_reusable=True
        )


@given(parsers.parse("the URL {url} gives status {status:d}"))
def mock_url_status(extlink_replacements, url, status):
    extlink_replacements.httpx_mock.add_response(
        url=url, status_code=status, is_optional=True, is_reusable=True
    )


@given(parsers.parse("the URL {url} redirects to {target_url}"))
def mock_url_status_302(extlink_replacements, url, target_url):
    extlink_replacements.httpx_mock.add_response(
        url=url,
        status_code=302,
        headers={"Location": target_url},
        is_optional=True,
        is_reusable=True,
    )


@when(parsers.parse('a page contains "{text}"'))
def create_page(page, text):
    page.text = text


@when(parsers.parse("a page contains {pattern} formatted with {value}"))
def create_page_with_extlink(page, pattern, value):
    page.text = pattern.format(value)
    page.original_text = page.text


@when("I run ExtlinkReplacements")
def run_ExtlinkReplacements(page, extlink_replacements, mocker):
    # mock the require_login function which is used by PageUpdater
    mocker.patch("ws.pageupdater.require_login", return_value=lambda api: None)

    updater = PageUpdater(extlink_replacements.api)
    updater.add_checker(mwparserfromhell.nodes.ExternalLink, extlink_replacements)

    page.text, page.last_edit_summary = updater.update_page("dummy page", page.text)


@then(parsers.parse('the page should contain "{text}"'))
def check_page_text(page, text):
    assert page.text == text


@then(parsers.parse('the page content should be "{pattern}" formatted with "{text}"'))
def check_page_text_formatted(page, pattern, text):
    assert page.text == pattern.format(text)


@then(parsers.parse('the {url} should be replaced with "{new_url}"'))
def check_url_replaced(page, url, new_url):
    text = page.original_text.replace(url, new_url)
    assert page.text == text


@then("the page should have the original content")
def check_url_not_replaced(page):
    assert page.text == page.original_text


@then("the last edit summary should be empty")
def check_edit_summary_empty(page):
    assert page.last_edit_summary == ""


@then(parsers.parse('the last edit summary should be "{summary}"'))
def check_edit_summary(page, summary):
    assert page.last_edit_summary == summary
