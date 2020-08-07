#! /usr/bin/env python3

import re

from pytest_bdd import scenarios, given, when, then, parsers

scenarios("ExtlinkReplacements")

@given(parsers.parse("the wiki site URL is \"{site_url}\""))
def set_site_url(extlink_replacements, site_url):
    if not site_url.endswith("/"):
        site_url += "/"
    regex = re.escape(site_url) + r"(?P<pagename>[^\s\?]+)"
    extlink_replacements.wikisite_extlink_regex = re.compile(regex)

@given(parsers.parse("these working URLs:\n{text}"))
def mock_url_status_200(extlink_replacements, text):
    for url in text.splitlines():
        extlink_replacements.session_mock.get(url, status_code=200)

@given(parsers.parse("these broken URLs:\n{text}"))
def mock_url_status_404(extlink_replacements, text):
    for url in text.splitlines():
        extlink_replacements.session_mock.get(url, status_code=404)


@when(parsers.parse("a page contains \"{text}\""))
def create_page(page, text):
    page.text = text

@when("a page contains an extlink with <url> and content <pattern>")
def create_page_with_extlink(page, url, pattern):
    page.text = pattern.format(url)
    page.original_text = page.text

@when("I run ExtlinkReplacements")
def run_ExtlinkReplacements(page, extlink_replacements):
    page.text, page.last_edit_summary = extlink_replacements.update_page("dummy page", page.text)


@then(parsers.parse("the page should contain \"{text}\""))
def check_page_text(page, text):
    assert page.text == text

@then(parsers.parse("the <url> should be replaced with \"{new_url}\""))
def check_url_replaced(page, url, new_url):
    text = page.original_text.replace(url, new_url)
    assert page.text == text

@then("the <url> should not be replaced")
def check_url_not_replaced(page, url):
    assert page.text == page.original_text

@then("the last edit summary should be empty")
def check_page_text(page):
    assert page.last_edit_summary == ""

@then(parsers.parse("the last edit summary should be \"{summary}\""))
def check_page_text(page, summary):
    assert page.last_edit_summary == summary
