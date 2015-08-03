#! /usr/bin/env python3

from nose.tools import assert_equals

import mwparserfromhell

from ws.parser_helpers.wikicode import *

class test_get_adjacent_node():
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
