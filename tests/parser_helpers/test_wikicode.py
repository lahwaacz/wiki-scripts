#! /usr/bin/env python3

import mwparserfromhell

from ws.parser_helpers.wikicode import *
from ws.parser_helpers.title import canonicalize

class test_get_adjacent_node:
    def test_basic(self):
        snippet = "[[Arch Linux]] is the best!"
        wikicode = mwparserfromhell.parse(snippet)
        first = wikicode.get(0)
        last = get_adjacent_node(wikicode, first)
        assert str(last) == " is the best!"

    def test_last_node(self):
        snippet = "[[Arch Linux]] is the best!"
        wikicode = mwparserfromhell.parse(snippet)
        last = get_adjacent_node(wikicode, " is the best!")
        assert last == None

    def test_whitespace_preserved(self):
        snippet = "[[Arch Linux]] \t\n is the best!"
        wikicode = mwparserfromhell.parse(snippet)
        first = wikicode.get(0)
        last = get_adjacent_node(wikicode, first, ignore_whitespace=True)
        assert str(last) == " \t\n is the best!"

    def test_ignore_whitespace(self):
        snippet = "[[Arch Linux]] \t\n [[link]] is the best!"
        wikicode = mwparserfromhell.parse(snippet)
        first = wikicode.get(0)
        wikicode.remove("[[link]]")
        last = get_adjacent_node(wikicode, first, ignore_whitespace=True)
        assert str(last) == " is the best!"

class test_get_parent_wikicode:
    snippet = """\
{{Note|This [[wikipedia:reference]] is to be noted.}}
Some other text.
"""
    wikicode = mwparserfromhell.parse(snippet)

    def test_toplevel(self):
        parent = get_parent_wikicode(self.wikicode, self.wikicode.get(0))
        assert str(parent) == self.snippet

    def test_nested(self):
        note = self.wikicode.filter_templates()[0]
        link = self.wikicode.filter_wikilinks()[0]
        parent = get_parent_wikicode(self.wikicode, link)
        assert str(parent) == str(note.params[0])

class test_remove_and_squash:
    @staticmethod
    def _do_test(wikicode, remove, expected):
        node = wikicode.get(wikicode.index(remove))
        remove_and_squash(wikicode, node)
        assert str(wikicode) == expected

    def test_inside(self):
        snippet = "Some text with a [[link]] inside."
        expected = "Some text with a inside."
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link]]", expected)

    def test_around(self):
        snippet = """\
First paragraph

[[link1]]
Second paragraph
[[link2]]

Third paragraph
"""
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link1]]", "First paragraph\n\nSecond paragraph\n[[link2]]\n\nThird paragraph\n")
        self._do_test(wikicode, "[[link2]]", "First paragraph\n\nSecond paragraph\n\nThird paragraph\n")

    def test_lineend(self):
        snippet = """\
Some other text [[link]]
Following sentence.
"""
        expected = """\
Some other text
Following sentence.
"""
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link]]", expected)

    def test_linestart(self):
        snippet = """\
Another paragraph.
[[link]] some other text.
"""
        expected = """\
Another paragraph.
some other text.
"""
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link]]", expected)

    def test_lineend_twolinks(self):
        snippet = """\
Some other text [[link1]][[link2]]
Following sentence.
"""
        expected = """\
Some other text [[link1]]
Following sentence.
"""
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link2]]", expected)

    def test_linestart_twolinks(self):
        snippet = """\
Another paragraph.
[[link1]][[link2]] some other text.
"""
        expected = """\
Another paragraph.
[[link2]] some other text.
"""
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link1]]", expected)

    def test_multiple_nodes(self):
        snippet = "[[link1]][[link2]][[link3]]"
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link1]]", "[[link2]][[link3]]")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link2]]", "[[link1]][[link3]]")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link3]]", "[[link1]][[link2]]")

    def test_multiple_nodes_text(self):
        snippet = "foo [[link1]][[link2]][[link3]] bar"
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link1]]", "foo [[link2]][[link3]] bar")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link2]]", "foo [[link1]][[link3]] bar")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link3]]", "foo [[link1]][[link2]] bar")

    def test_multiple_nodes_spaces(self):
        snippet = "foo [[link1]] [[link2]] [[link3]] bar"
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link1]]", "foo [[link2]] [[link3]] bar")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link2]]", "foo [[link1]] [[link3]] bar")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link3]]", "foo [[link1]] [[link2]] bar")

    def test_multiple_nodes_newlines(self):
        snippet = "[[link1]]\n[[link2]]\n[[link3]]"
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link1]]", "[[link2]]\n[[link3]]")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link2]]", "[[link1]]\n[[link3]]")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link3]]", "[[link1]]\n[[link2]]")

    def test_multiple_newlines(self):
        snippet = """\
First paragraph

[[link]]

"""
        expected = """\
First paragraph

"""
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link]]", expected)

class test_get_section_headings:
    @staticmethod
    def _do_test(text, expected):
        result = get_section_headings(text)
        assert result == expected

    def test_balanced(self):
        snippet = """
foo
== Section 1 ==
bar
=== Section 2===
=Section 3 =
== Section 4 ===
"""
        expected = ["Section 1", "Section 2", "Section 3", "Section 4 ="]
        self._do_test(snippet, expected)

    def test_unbalanced(self):
        snippet = """
Invalid section 1 ==
== Invalid section 2
== Valid section 1 =
= Valid section 2 ==
== Valid section 3 = =
= = Valid section 4 ==
"""
        expected = [
            "= Valid section 1",
            "Valid section 2 =",
            "= Valid section 3 =",
            "= Valid section 4 =",
        ]
        self._do_test(snippet, expected)

    def test_levels(self):
        snippet = """
= Level 1 =
== Level 2 ==
=== Level 3 ===
==== Level 4 ====
===== Level 5 =====
====== Level 6 ======
======= Invalid level =======
"""
        expected = [
            "Level 1",
            "Level 2",
            "Level 3",
            "Level 4",
            "Level 5",
            "Level 6",
            "= Invalid level =",
        ]
        self._do_test(snippet, expected)

class test_get_anchors:
    def test_simple(self):
        snippet = """
== foo ==
== bar ==
== foo ==
== foo_2 ==
== foo 2 ==
"""
        expected = ["foo", "bar", "foo_2", "foo_2_2", "foo_2_3"]
        result = get_anchors(get_section_headings(snippet))
        assert result == expected

    def test_complex(self):
        snippet = """
== foo_2 ==
== foo_2_2 ==
== foo ==
== foo ==
== foo 2 ==
== foo 2 ==
"""
        expected = ["foo_2", "foo_2_2", "foo", "foo_3", "foo_2_3", "foo_2_4"]
        result = get_anchors(get_section_headings(snippet))
        assert result == expected

    def test_strip(self):
        snippet = """
== Section with ''wikicode'' ==
== Section with <i>tag</i> ==
== Section with HTML entities &Sigma;, &#931;, and &#x3a3; ==
== Section with [[Main page|wikilink]] ==
== Section with <nowiki><nowiki></nowiki> ==
== #section starting with hash ==
"""
        expected = [
            "Section_with_wikicode",
            "Section_with_tag",
            "Section_with_HTML_entities_.CE.A3.2C_.CE.A3.2C_and_.CE.A3",
            "Section_with_wikilink",
            "Section_with_.3Cnowiki.3E",
            ".23section_starting_with_hash",
        ]
        result = get_anchors(get_section_headings(snippet))
        assert result == expected

    def test_strip_pretty(self):
        snippet = """
== Section with ''wikicode'' ==
== Section with <i>tag</i> ==
== Section with HTML entities &Sigma;, &#931;, and &#x3a3; ==
== Section with [[Main page|wikilink]] ==
== Section with <nowiki><nowiki></nowiki> ==
== #section starting with hash ==
"""
        expected = [
            "Section with wikicode",
            "Section with tag",
            "Section with HTML entities Σ, Σ, and Σ",
            "Section with wikilink",
            "Section with <nowiki>",    # FIXME: should be encoded, i.e. "Section with %3Cnowiki%3E",
            "#section starting with hash",
        ]
        result = get_anchors(get_section_headings(snippet), pretty=True)
        assert result == expected

    def test_encoding(self):
        snippet = """
== Section with | pipe ==
== Section with [brackets] ==
== Section with <invalid tag> ==
"""
        expected = [
            "Section with %7C pipe",
            "Section with %5Bbrackets%5D",
            "Section with <invalid tag>",
        ]
        result = get_anchors(get_section_headings(snippet), pretty=True)
        assert result == expected

    def test_invalid(self):
        snippet = """
== Section with trailing spaces ==  
== Invalid 1 ==  foo
== 
  Invalid 2 ==
== Invalid 3
  ==
== 
  Invalid 4
  ==
== Invalid 5
 foo ==
"""
        expected = [
            "Section with trailing spaces",
        ]
        result = get_anchors(get_section_headings(snippet), pretty=True)
        assert result == expected

class test_ensure_flagged:
    def test_add(self):
        wikicode = mwparserfromhell.parse("[[foo]]")
        link = wikicode.nodes[0]
        flag = ensure_flagged_by_template(wikicode, link, "bar")
        assert str(wikicode) == "[[foo]]{{bar}}"

    def test_preserve(self):
        wikicode = mwparserfromhell.parse("[[foo]] {{bar}}")
        link = wikicode.nodes[0]
        flag = ensure_flagged_by_template(wikicode, link, "bar")
        assert str(wikicode) == "[[foo]] {{bar}}"

    def test_strip_params(self):
        wikicode = mwparserfromhell.parse("[[foo]] {{bar|baz}}")
        link = wikicode.nodes[0]
        flag = ensure_flagged_by_template(wikicode, link, "bar")
        assert str(wikicode) == "[[foo]] {{bar}}"

    def test_replace_params(self):
        wikicode = mwparserfromhell.parse("[[foo]] {{bar|baz}}")
        link = wikicode.nodes[0]
        flag = ensure_flagged_by_template(wikicode, link, "bar", "param1", "param2")
        assert str(wikicode) == "[[foo]] {{bar|param1|param2}}"

    def test_named_params(self):
        wikicode = mwparserfromhell.parse("[[foo]] {{bar|baz}}")
        link = wikicode.nodes[0]
        flag = ensure_flagged_by_template(wikicode, link, "bar", "2=param1", "1=param2")
        assert str(wikicode) == "[[foo]] {{bar|2=param1|1=param2}}"

    def test_dead_link(self):
        wikicode = mwparserfromhell.parse("[[foo]]{{Dead link|2000|01|01}}")
        link = wikicode.nodes[0]
        flag = ensure_flagged_by_template(wikicode, link, "Dead link", "2017", "2", "3", overwrite_parameters=False)
        assert str(wikicode) == "[[foo]]{{Dead link|2000|01|01}}"

class test_ensure_unflagged:
    def test_noop(self):
        wikicode = mwparserfromhell.parse("[[foo]]")
        link = wikicode.nodes[0]
        flag = ensure_unflagged_by_template(wikicode, link, "bar")
        assert str(wikicode) == "[[foo]]"

    def test_preserve(self):
        wikicode = mwparserfromhell.parse("[[foo]] {{baz}}")
        link = wikicode.nodes[0]
        flag = ensure_unflagged_by_template(wikicode, link, "bar")
        assert str(wikicode) == "[[foo]] {{baz}}"

    def test_remove(self):
        wikicode = mwparserfromhell.parse("[[foo]] {{bar}}")
        link = wikicode.nodes[0]
        flag = ensure_unflagged_by_template(wikicode, link, "bar")
        assert str(wikicode) == "[[foo]]"

class test_expand_templates:
    @staticmethod
    def _do_test(d, title, expected):
        def content_getter(title):
            nonlocal d
            try:
                return d[title]
            except KeyError:
                raise ValueError

        content = d[title]
        wikicode = mwparserfromhell.parse(content)
        expand_templates(title, wikicode, content_getter)
        assert wikicode == expected

    def test_basic(self):
        d = {
            "Template:Note": "{{{1}}}",
            "Title": "{{Note|{{Note|foo}}}}"
        }
        title = "Title"
        expected = "foo"
        self._do_test(d, title, expected)

    def test_default_values(self):
        d = {
            "Template:Note": "{{{1|default}}}",
            "Title": "{{Note|{{Note}}}} {{Note|}} {{Note|non-default}}"
        }
        title = "Title"
        expected = "default  non-default"
        self._do_test(d, title, expected)

    def test_invalid_template(self):
        d = {
            "Title": "{{invalid}}"
        }
        title = "Title"
        expected = "[[Template:Invalid]]"
        self._do_test(d, title, expected)

    def test_invalid_page(self):
        d = {
            "Title": "{{:invalid}}"
        }
        title = "Title"
        expected = "[[Invalid]]"
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

    # TODO: what happens in MediaWiki when <onlyinclude> is nested inside <noinclude>?
    # definitely something funny: "<noinclude><onlyinclude>{{{1}}}</onlyinclude>{{a|foo}}</noinclude>" -> "{{{1}}}foo"
