#! /usr/bin/env python3

import pytest

import mwparserfromhell

from ws.parser_helpers.template_expansion import *
from ws.parser_helpers.title import TitleError

class test_expand_templates:
    @staticmethod
    def _do_test(d, title, expected, **kwargs):
        def content_getter(title):
            if "<" in title or ">" in title:
                raise TitleError
            try:
                return d[title]
            except KeyError:
                raise ValueError

        content = d[title]
        wikicode = mwparserfromhell.parse(content)
        expand_templates(title, wikicode, content_getter, **kwargs)
        assert wikicode == expected

    def test_type_of_wikicode(self):
        def void_getter(title):
            raise ValueError
        with pytest.raises(TypeError):
            expand_templates("title", "content", void_getter)

    def test_basic(self):
        d = {
            "Template:Echo": "{{{1}}}",
            "Title": "{{Echo|{{Echo|foo}}}}",
        }
        title = "Title"
        expected = "foo"
        self._do_test(d, title, expected)

    def test_explicit_template_prefix(self):
        d = {
            "Template:Echo": "{{{1}}}",
            "Title": "{{Template:Echo|foo}}",
        }
        title = "Title"
        expected = "foo"
        self._do_test(d, title, expected)

    def test_default_values(self):
        d = {
            "Template:Note": "{{{1|default}}}",
            "Title": "{{Note|{{Note}}}} {{Note|}} {{Note|non-default}}",
        }
        title = "Title"
        expected = "default  non-default"
        self._do_test(d, title, expected)

    def test_invalid_template(self):
        d = {
            "Title": "{{invalid}}",
        }
        title = "Title"
        expected = "[[Template:Invalid]]"
        self._do_test(d, title, expected)

    def test_invalid_page(self):
        d = {
            "Title": "{{:invalid}}",
        }
        title = "Title"
        expected = "[[Invalid]]"
        self._do_test(d, title, expected)

    def test_title_error(self):
        # in order to test the TitleError case, we need to get the tags inside the braces using transclusion,
        # because mwparserfromhell does not even parse {{<code>foo</code>}} as a template
        d = {
            "Template:Ic": "<code>{{{1}}}</code>",
            "Title": "{{ {{ic|foo}} }}",
        }
        title = "Title"
        expected = "{{ <code>foo</code> }}"
        self._do_test(d, title, expected)

    def test_infinite_loop_protection(self):
        d = {
            "Template:A": "a: {{b}}",
            "Template:B": "b: {{c}}",
            "Template:C": "c: {{:title}}",
            "Title": "{{a}}",
        }
        title = "Title"
        expected = "a: b: c: {{a}}"
        self._do_test(d, title, expected)

    def test_relative_transclusion(self):
        d = {
            "Template:A": "a: {{/B}}",
            "Template:A/B": "b: {{c}}",
            "Title": "{{a}}",
        }
        title = "Title"
        # this is very weird, but that's what MediaWiki does...
        expected = "a: [[Title/B]]"
        self._do_test(d, title, expected)

    def test_named_parameers(self):
        d = {
            "Template:A": "a: {{{a|b: {{{b|c: {{{c|}}} }}} }}}",
            "Title 1": "x{{A}}y",
            "Title 2": "x{{A|a=foo}}y",
            "Title 3": "x{{A|b=foo}}y",
            "Title 4": "x{{A|c=foo}}y",
        }

        title = "Title 1"
        expected = "xa: b: c:   y"
        self._do_test(d, title, expected)

        title = "Title 2"
        expected = "xa: fooy"
        self._do_test(d, title, expected)

        title = "Title 3"
        expected = "xa: b: foo y"
        self._do_test(d, title, expected)

        title = "Title 4"
        expected = "xa: b: c: foo  y"
        self._do_test(d, title, expected)

    def test_nested_argument_name(self):
        d = {
            "Template:A": "{{{ {{{1}}} |foo }}}",
            "Title 1": "x{{A}}y",
            "Title 2": "x{{A|1|bar}}y",
            "Title 3": "x{{A|2|bar}}y",
            "Title 4": "x{{A|3|bar}}y",
        }

        title = "Title 1"
        expected = "xfoo y"
        self._do_test(d, title, expected)

        title = "Title 2"
        expected = "x1y"
        self._do_test(d, title, expected)

        title = "Title 3"
        expected = "xbary"
        self._do_test(d, title, expected)

        title = "Title 4"
        expected = "xfoo y"
        self._do_test(d, title, expected)

    def test_noinclude(self):
        d = {
            "Template:A": "<noinclude>foo {{{1}}}</noinclude>bar",
            "Title 1": "{{a}}",
            "Title 2": "{{a|b}}",
        }
        expected = "bar"

        title = "Title 1"
        self._do_test(d, title, expected)

        title = "Title 2"
        self._do_test(d, title, expected)

    def test_nested_noinclude(self):
        d = {
            "Template:A": "<noinclude>foo <noinclude>{{{1}}}</noinclude></noinclude>bar",
            "Title 1": "{{a}}",
            "Title 2": "{{a|b}}",
        }
        expected = "bar"

        title = "Title 1"
        self._do_test(d, title, expected)

        title = "Title 2"
        self._do_test(d, title, expected)

    def test_includeonly(self):
        d = {
            "Template:A": "foo <includeonly>bar {{{1|}}}</includeonly>",
            "Title 1": "{{a}}",
            "Title 2": "{{a|b}}",
        }

        title = "Title 1"
        expected = "foo bar "
        self._do_test(d, title, expected)

        title = "Title 2"
        expected = "foo bar b"
        self._do_test(d, title, expected)

    def test_nested_includeonly(self):
        d = {
            "Template:A": "foo <includeonly>bar <includeonly>{{{1|}}}</includeonly></includeonly>",
            "Title 1": "{{a}}",
            "Title 2": "{{a|b}}",
        }

        title = "Title 1"
        expected = "foo bar "
        self._do_test(d, title, expected)

        title = "Title 2"
        expected = "foo bar b"
        self._do_test(d, title, expected)

    def test_noinclude_and_includeonly(self):
        d = {
            "Template:A": "<noinclude>foo</noinclude><includeonly>bar</includeonly>",
            "Title": "{{a}}",
        }
        title = "Title"
        expected = "bar"
        self._do_test(d, title, expected)

    def test_nested_noinclude_and_includeonly(self):
        d = {
            "Template:A": "<noinclude>foo <includeonly>bar</includeonly></noinclude>",
            "Title": "{{a}}",
        }
        title = "Title"
        expected = ""
        self._do_test(d, title, expected)

    def test_onlyinclude(self):
        d = {
            "Template:A": "foo <onlyinclude>bar</onlyinclude>",
            "Title": "{{a}}",
        }
        title = "Title"
        expected = "bar"
        self._do_test(d, title, expected)

    def test_noinclude_and_includeonly_and_onlyinclude(self):
        d = {
            "Template:A": "<noinclude>foo</noinclude><includeonly>bar</includeonly><onlyinclude>baz</onlyinclude>",
            "Title": "{{a}}",
        }
        title = "Title"
        expected = "baz"
        self._do_test(d, title, expected)

    def test_nested_noinclude_and_includeonly_and_onlyinclude(self):
        d = {
            "Template:A": "<noinclude><includeonly><onlyinclude>{{{1}}}<onlyinclude>{{{2}}}</onlyinclude></onlyinclude></includeonly>discarded text</noinclude>",
            "Title": "{{a|foo|bar}}",
        }

        title = "Title"
        # MW incompatibility: MediaWiki does not render the closing </onlyinclude>, most likely it does not pair them correctly
        expected = "foo<onlyinclude>bar</onlyinclude>"
        self._do_test(d, title, expected)

    def test_recursive_passing_of_arguments(self):
        d = {
            "Template:A": "{{{1}}}",
            "Title": "{{a|{{{1}}}}}",
        }
        title = "Title"
        expected = "{{{1}}}"
        self._do_test(d, title, expected)

    def test_magic_words(self):
        d = {
            "Template:A": "http://example.com/{{urlencode:{{{1}}}}}/",
            "Template:B": "http://example.com/#{{anchorencode:{{{1}}}}}",
            "Title 1": "{{a|foo bar}}",
            "Title 2": "{{b|foo bar}}",
        }

        title = "Title 1"
        expected = "http://example.com/foo%20bar/"
        self._do_test(d, title, expected)

        title = "Title 2"
        expected = "http://example.com/#foo_bar"
        self._do_test(d, title, expected)

    def test_magic_words_disabled(self):
        d = {
            "Template:A": "http://example.com/{{urlencode:{{{1}}}}}/",
            "Template:B": "http://example.com/#{{anchorencode:{{{1}}}}}",
            "Title 1": "{{a|foo bar}}",
            "Title 2": "{{b|foo bar}}",
        }

        title = "Title 1"
        expected = "http://example.com/{{urlencode:foo bar}}/"
        self._do_test(d, title, expected, substitute_magic_words=False)

        title = "Title 2"
        expected = "http://example.com/#{{anchorencode:foo bar}}"
        self._do_test(d, title, expected, substitute_magic_words=False)

    def test_magic_words_unhandled(self):
        # this is mostly to complete the code coverage...
        d = {
            "Title": "{{PAGENAME}} {{#special:foo}}",
        }
        title = "Title"
        expected = d[title]
        self._do_test(d, title, expected)
