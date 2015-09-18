#! /usr/bin/env python3

from nose.tools import assert_equals

import mwparserfromhell

from ws.parser_helpers.wikicode import *

class test_get_adjacent_node:
    def test_basic(self):
        snippet = "[[Arch Linux]] is the best!"
        wikicode = mwparserfromhell.parse(snippet)
        first = wikicode.get(0)
        last = get_adjacent_node(wikicode, first)
        assert_equals(str(last), " is the best!")

    def test_last_node(self):
        snippet = "[[Arch Linux]] is the best!"
        wikicode = mwparserfromhell.parse(snippet)
        last = get_adjacent_node(wikicode, " is the best!")
        assert_equals(last, None)

    def test_whitespace_preserved(self):
        snippet = "[[Arch Linux]] \t\n is the best!"
        wikicode = mwparserfromhell.parse(snippet)
        first = wikicode.get(0)
        last = get_adjacent_node(wikicode, first, ignore_whitespace=True)
        assert_equals(str(last), " \t\n is the best!")

    def test_ignore_whitespace(self):
        snippet = "[[Arch Linux]] \t\n [[link]] is the best!"
        wikicode = mwparserfromhell.parse(snippet)
        first = wikicode.get(0)
        wikicode.remove("[[link]]")
        last = get_adjacent_node(wikicode, first, ignore_whitespace=True)
        assert_equals(str(last), " is the best!")

class test_get_parent_wikicode:
    snippet = """\
{{Note|This [[wikipedia:reference]] is to be noted.}}
Some other text.
"""
    wikicode = mwparserfromhell.parse(snippet)

    def test_toplevel(self):
        parent = get_parent_wikicode(self.wikicode, self.wikicode.get(0))
        assert_equals(str(parent), self.snippet)

    def test_nested(self):
        note = self.wikicode.filter_templates()[0]
        link = self.wikicode.filter_wikilinks()[0]
        parent = get_parent_wikicode(self.wikicode, link)
        assert_equals(str(parent), str(note.params[0]))

class test_remove_and_squash:
    @staticmethod
    def _do_test(wikicode, remove, expected):
        node = wikicode.get(wikicode.index(remove))
        remove_and_squash(wikicode, node)
        assert_equals(str(wikicode), expected)

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

    def test_multiple_nodes(self):
        snippet = "[[link1]][[link2]][[link3]]"
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link1]]", "[[link2]][[link3]]")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link2]]", "[[link1]][[link3]]")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link3]]", "[[link1]][[link2]]")

    def test_multiple_nodes_spaces(self):
        snippet = "[[link1]] [[link2]] [[link3]]"
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link1]]", "[[link2]] [[link3]]")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link2]]", "[[link1]] [[link3]]")
        wikicode = mwparserfromhell.parse(snippet)
        self._do_test(wikicode, "[[link3]]", "[[link1]] [[link2]]")

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
        assert_equals(result, expected)

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
