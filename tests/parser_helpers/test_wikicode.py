#! /usr/bin/env python3

import mwparserfromhell

from ws.parser_helpers.wikicode import *

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

class test_is_redirect:
    redirects = [
        # any number of spaces
        "#redirect[[foo]]",
        "#redirect [[foo]]",
        "#redirect  [[foo]]",
        # optional colon
        "#redirect: [[foo]]",
        "#redirect :[[foo]]",
        "#redirect : [[foo]]",
        # any capitalization
        "#reDiRect  [[foo]]",
        "#REDIRECT  [[foo]]",
        # leading whitespace
        "\n \n #redirect [[foo]]",
        # any section and alternative text (which is ignored)
        "#redirect [[foo#section]]",
        "#redirect [[foo#section|ignored]]",
        # templates
        # FIXME: probably not possible to pair '{{' and '}}' with a regex
#        "#redirect [[{{echo|Foo}}bar]]",
    ]

    nonredirects = [
        "#redirect [[]]",
        "#redirect [[]]",
        "#redirect [[<nowikifoo]]",
        "#redirect :: [[foo]]",
        "#redirect [[foo{}]]",
    ]

    def test_redirects(self):
        for text in self.redirects:
            assert is_redirect(text, full_match=False)
            assert is_redirect(text, full_match=True)
            text += "\n"
            assert is_redirect(text, full_match=False)
            assert is_redirect(text, full_match=True)
            text += "bar"
            assert is_redirect(text, full_match=False)
            assert not is_redirect(text, full_match=True)

    def test_nonredirects(self):
        for text in self.redirects:
            assert not is_redirect("foo" + text, full_match=False)
            assert not is_redirect("foo" + text, full_match=True)
        for text in self.nonredirects:
            assert not is_redirect("foo" + text, full_match=False)
            assert not is_redirect("foo" + text, full_match=True)
