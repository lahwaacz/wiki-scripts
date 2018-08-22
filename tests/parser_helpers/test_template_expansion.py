#! /usr/bin/env python3

import pytest

import mwparserfromhell

from ws.parser_helpers.template_expansion import *
from ws.parser_helpers.title import Title, TitleError

class common_base:
    @staticmethod
    def _do_test(title_context, d, title, expected, **kwargs):
        def content_getter(title):
#            if "<" in str(title) or ">" in title:
#                raise TitleError
            try:
                return d[str(title)]
            except KeyError:
                raise ValueError

        content = d[title]
        wikicode = mwparserfromhell.parse(content)
        expand_templates(Title(title_context, title), wikicode, content_getter, **kwargs)
        assert wikicode == expected

class test_expand_templates(common_base):
    def test_type_of_wikicode(self, title_context):
        def void_getter(title):
            raise ValueError
        with pytest.raises(TypeError):
            expand_templates("title", "content", void_getter)

    def test_basic(self, title_context):
        d = {
            "Template:Echo": "{{{1}}}",
            "Title": "{{Echo|{{Echo|foo}}}}",
        }
        title = "Title"
        expected = "foo"
        self._do_test(title_context, d, title, expected)

    def test_explicit_template_prefix(self, title_context):
        d = {
            "Template:Echo": "{{{1}}}",
            "Talk:Foo": "foo",
            "Title 1": "{{Template:Echo|foo}}",
            "Title 2": "{{Talk:Foo}}",
        }

        for title in ["Title 1", "Title 2"]:
            expected = "foo"
            self._do_test(title_context, d, title, expected)

    def test_default_values(self, title_context):
        d = {
            "Template:Note": "{{{1|default}}}",
            "Title": "{{Note|{{Note}}}} {{Note|}} {{Note|non-default}}",
        }
        title = "Title"
        expected = "default  non-default"
        self._do_test(title_context, d, title, expected)

    def test_invalid_template(self, title_context):
        d = {
            "Title": "{{invalid}}",
        }
        title = "Title"
        expected = "[[Template:Invalid]]"
        self._do_test(title_context, d, title, expected)

    def test_invalid_page(self, title_context):
        d = {
            "Title": "{{:invalid}}",
        }
        title = "Title"
        expected = "[[Invalid]]"
        self._do_test(title_context, d, title, expected)

    def test_title_error(self, title_context):
        # in order to test the TitleError case, we need to get the tags inside the braces using transclusion,
        # because mwparserfromhell does not even parse {{<code>foo</code>}} as a template
        d = {
            "Template:Ic": "<code>{{{1}}}</code>",
            "Title": "{{ {{ic|foo}} }}",
        }
        title = "Title"
        expected = "{{ <code>foo</code> }}"
        self._do_test(title_context, d, title, expected)

    def test_infinite_loop_protection(self, title_context):
        d = {
            "Template:A": "a: {{b}}",
            "Template:B": "b: {{c}}",
            "Template:C": "c: {{:title 1}}",
            "Title 1": "{{a}}",
            "Template:AAA": "{{AAA}}",
            "Title 2": "{{AAA}}",
            "Template:Echo": "{{{1}}}",
            "Title 3": "{{Echo|{{Echo|{{Echo|{{Echo|foo}}}}}}}}",
        }

        title = "Title 1"
        expected = "a: b: c: <span class=\"error\">Template loop detected: [[Template:A]]</span>"
        self._do_test(title_context, d, title, expected)

        title = "Template:AAA"
        expected = "<span class=\"error\">Template loop detected: [[Template:AAA]]</span>"
        self._do_test(title_context, d, title, expected)

        title = "Title 2"
        expected = "<span class=\"error\">Template loop detected: [[Template:AAA]]</span>"
        self._do_test(title_context, d, title, expected)

        title = "Title 3"
        expected = "foo"
        self._do_test(title_context, d, title, expected)

    def test_relative_transclusion(self, title_context):
        d = {
            "Template:A": "a: {{/B}}",
            "Template:A/B": "b: {{c}}",
            "Title": "{{a}}",
        }
        title = "Title"
        # this is very weird, but that's what MediaWiki does...
        expected = "a: [[Title/B]]"
        self._do_test(title_context, d, title, expected)

    def test_named_parameers(self, title_context):
        d = {
            "Template:A": "a: {{{a|b: {{{b|c: {{{c|}}} }}} }}}",
            "Title 1": "x{{A}}y",
            "Title 2": "x{{A|a=foo}}y",
            "Title 3": "x{{A|b=foo}}y",
            "Title 4": "x{{A|c=foo}}y",
        }

        title = "Title 1"
        expected = "xa: b: c:   y"
        self._do_test(title_context, d, title, expected)

        title = "Title 2"
        expected = "xa: fooy"
        self._do_test(title_context, d, title, expected)

        title = "Title 3"
        expected = "xa: b: foo y"
        self._do_test(title_context, d, title, expected)

        title = "Title 4"
        expected = "xa: b: c: foo  y"
        self._do_test(title_context, d, title, expected)

    def test_nested_argument_name(self, title_context):
        d = {
            "Template:A": "{{{ {{{1}}} |foo }}}",
            "Title 1": "x{{A}}y",
            "Title 2": "x{{A|1|bar}}y",
            "Title 3": "x{{A|2|bar}}y",
            "Title 4": "x{{A|3|bar}}y",
        }

        title = "Title 1"
        expected = "xfoo y"
        self._do_test(title_context, d, title, expected)

        title = "Title 2"
        expected = "x1y"
        self._do_test(title_context, d, title, expected)

        title = "Title 3"
        expected = "xbary"
        self._do_test(title_context, d, title, expected)

        title = "Title 4"
        expected = "xfoo y"
        self._do_test(title_context, d, title, expected)

    def test_noinclude(self, title_context):
        d = {
            "Template:A": "<noinclude>foo {{{1}}}</noinclude>bar",
            "Title 1": "{{a}}",
            "Title 2": "{{a|b}}",
        }
        expected = "bar"

        title = "Title 1"
        self._do_test(title_context, d, title, expected)

        title = "Title 2"
        self._do_test(title_context, d, title, expected)

    def test_nested_noinclude(self, title_context):
        d = {
            "Template:A": "<noinclude>foo <noinclude>{{{1}}}</noinclude></noinclude>bar",
            "Title 1": "{{a}}",
            "Title 2": "{{a|b}}",
        }
        expected = "bar"

        title = "Title 1"
        self._do_test(title_context, d, title, expected)

        title = "Title 2"
        self._do_test(title_context, d, title, expected)

    def test_includeonly(self, title_context):
        d = {
            "Template:A": "foo <includeonly>bar {{{1|}}}</includeonly>",
            "Title 1": "{{a}}",
            "Title 2": "{{a|b}}",
        }

        title = "Title 1"
        expected = "foo bar "
        self._do_test(title_context, d, title, expected)

        title = "Title 2"
        expected = "foo bar b"
        self._do_test(title_context, d, title, expected)

    def test_nested_includeonly(self, title_context):
        d = {
            "Template:A": "foo <includeonly>bar <includeonly>{{{1|}}}</includeonly></includeonly>",
            "Title 1": "{{a}}",
            "Title 2": "{{a|b}}",
        }

        title = "Title 1"
        expected = "foo bar "
        self._do_test(title_context, d, title, expected)

        title = "Title 2"
        expected = "foo bar b"
        self._do_test(title_context, d, title, expected)

    def test_noinclude_and_includeonly(self, title_context):
        d = {
            "Template:A": "<noinclude>foo</noinclude><includeonly>bar</includeonly>",
            "Title": "{{a}}",
        }
        title = "Title"
        expected = "bar"
        self._do_test(title_context, d, title, expected)

    def test_nested_noinclude_and_includeonly(self, title_context):
        d = {
            "Template:A": "<noinclude>foo <includeonly>bar</includeonly></noinclude>",
            "Title": "{{a}}",
        }
        title = "Title"
        expected = ""
        self._do_test(title_context, d, title, expected)

    def test_onlyinclude(self, title_context):
        d = {
            "Template:A": "foo <onlyinclude>bar</onlyinclude>",
            "Title": "{{a}}",
        }
        title = "Title"
        expected = "bar"
        self._do_test(title_context, d, title, expected)

    def test_noinclude_and_includeonly_and_onlyinclude(self, title_context):
        d = {
            "Template:A": "<noinclude>foo</noinclude><includeonly>bar</includeonly><onlyinclude>baz</onlyinclude>",
            "Title": "{{a}}",
        }
        title = "Title"
        expected = "baz"
        self._do_test(title_context, d, title, expected)

    def test_nested_noinclude_and_includeonly_and_onlyinclude(self, title_context):
        d = {
            "Template:A": "<noinclude><includeonly><onlyinclude>{{{1}}}<onlyinclude>{{{2}}}</onlyinclude></onlyinclude></includeonly>discarded text</noinclude>",
            "Title": "{{a|foo|bar}}",
        }

        title = "Title"
        # MW incompatibility: MediaWiki does not render the closing </onlyinclude>, most likely it does not pair them correctly
        expected = "foo<onlyinclude>bar</onlyinclude>"
        self._do_test(title_context, d, title, expected)

    def test_recursive_passing_of_arguments(self, title_context):
        d = {
            "Template:A": "{{{1}}}",
            "Title": "{{a|{{{1}}}}}",
        }
        title = "Title"
        expected = "{{{1}}}"
        self._do_test(title_context, d, title, expected)

class test_magic_words(common_base):
    def test_pagename(self, title_context):
        d = {
            "Talk:Title": "{{PAGENAME}}",
        }
        title = "Talk:Title"
        self._do_test(title_context, d, title, "Title")

    def test_encoding(self, title_context):
        d = {
            "Template:A": "http://example.com/{{urlencode:{{{1}}}}}/",
            "Template:B": "http://example.com/#{{anchorencode:{{{1}}}}}",
            "Title 1": "{{a|foo bar}}",
            "Title 2": "{{b|foo bar}}",
        }

        title = "Title 1"
        expected = "http://example.com/foo%20bar/"
        self._do_test(title_context, d, title, expected)

        title = "Title 2"
        expected = "http://example.com/#foo_bar"
        self._do_test(title_context, d, title, expected)

    def test_disabled(self, title_context):
        d = {
            "Template:A": "http://example.com/{{urlencode:{{{1}}}}}/",
            "Template:B": "http://example.com/#{{anchorencode:{{{1}}}}}",
            "Title 1": "{{a|foo bar}}",
            "Title 2": "{{b|foo bar}}",
        }

        title = "Title 1"
        expected = "http://example.com/{{urlencode:foo bar}}/"
        self._do_test(title_context, d, title, expected, substitute_magic_words=False)

        title = "Title 2"
        expected = "http://example.com/#{{anchorencode:foo bar}}"
        self._do_test(title_context, d, title, expected, substitute_magic_words=False)

    def test_unhandled(self, title_context):
        # this is mostly to complete the code coverage...
        d = {
            "Title": "{{LOCALTIMESTAMP}} {{#special:foo}}",
        }
        title = "Title"
        expected = d[title]
        self._do_test(title_context, d, title, expected)

    def test_if(self, title_context):
        d = {
            "No": "{{ #if: | Yes | No }}",
            "Yes": "{{ #if: string | Yes | No }}",
            "XY": "X{{ #if: | Yes }}Y",
            "YZ": "Y{{ #if: string }}Z",
        }
        for title in d.keys():
            self._do_test(title_context, d, title, title)

    def test_switch(self, title_context):
        d = {
            "Baz": "{{#switch: baz | foo = Foo | baz = Baz | Bar }}",
            "Foo": "{{#switch: foo | foo = Foo | baz = Baz | Bar }}",
            "Bar": "{{#switch: zzz | foo = Foo | baz = Baz | Bar }}",
            "XY": "X{{#switch: zzz | foo = Foo | baz = Baz }}Y",
        }
        for title in d.keys():
            self._do_test(title_context, d, title, title)

    def test_nested(self, title_context):
        d = {
            "Yes": "{{ #if: string | {{PAGENAME}} | No }}",
            "No": "{{ #if: {{urlencode:}} | Yes | No }}",
        }
        for title in d.keys():
            self._do_test(title_context, d, title, title)

    def test_cat_main(self, title_context):
        d = {
            "Template:Cat main": """<noinclude>{{Cat main}}</noinclude><includeonly>{{
                        #switch: {{#if:{{{1|}}}|1|0}}{{#if:{{{2|}}}|1|0}}{{#if:{{{3|}}}|1|0}}
                        | 000 = The main article for this category is [[{{PAGENAME}}]].
                        | 100 = The main article for this category is [[{{{1}}}]].
                        | 110 = The main articles for this category are [[{{{1}}}]] and [[{{{2}}}]].
                        | 111 = The main articles for this category are [[{{{1}}}]], [[{{{2}}}]] and [[{{{3}}}]].
                    }}</includeonly>""",
            "Title 1": "{{Cat main}}",
            "Title 2": "{{Cat main|Foo}}",
            "Title 3": "{{Cat main|Foo|Bar}}",
            "Title 4": "{{Cat main|Foo|Bar|Baz}}",
        }

        title = "Title 1"
        expected = "The main article for this category is [[Title 1]]."
        self._do_test(title_context, d, title, expected)

        title = "Title 2"
        expected = "The main article for this category is [[Foo]]."
        self._do_test(title_context, d, title, expected)

        title = "Title 3"
        expected = "The main articles for this category are [[Foo]] and [[Bar]]."
        self._do_test(title_context, d, title, expected)

        title = "Title 4"
        expected = "The main articles for this category are [[Foo]], [[Bar]] and [[Baz]]."
        self._do_test(title_context, d, title, expected)

        title = "Template:Cat main"
        expected = "<noinclude>The main article for this category is [[Cat main]].</noinclude><includeonly>The main articles for this category are [[{{{1}}}]], [[{{{2}}}]] and [[{{{3}}}]].</includeonly>"
        self._do_test(title_context, d, title, expected)
