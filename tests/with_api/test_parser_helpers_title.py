#! /usr/bin/env python3

from nose.tools import assert_equals
from nose.plugins.attrib import attr

from . import fixtures
from ws.parser_helpers.title import *

class test_canonicalize():
    # keys: input, values: expected result
    titles = {
        "Foo_bar": "Foo bar",
        " Foo_bar__": "Foo bar",
        " foo   _ bar__": "Foo bar",
        "foo": "Foo",
        "foo:bar": "Foo:bar",
        "fOOo BaAar": "FOOo BaAar",
    }

    def test(self):
        for src, expected in self.titles.items():
            yield self._do_test, src, expected

    def _do_test(self, src, expected):
        result = canonicalize(src)
        assert_equals(result, expected)

@attr(speed="slow")
class test_title():
    # keys: input, values: dictionary of expected attributes of the Title object
    titles = {
        # test splitting and fullpagename formatting
        "Foo:Bar:Baz#section": {
            "iwprefix": "",
            "namespace": "",
            "pagename": "Foo:Bar:Baz",
            "sectionname": "section",
            "fullpagename": "Foo:Bar:Baz",
        },
        "Talk:Foo": {
            "iwprefix": "",
            "namespace": "Talk",
            "pagename": "Foo",
            "sectionname": "",
            "fullpagename": "Talk:Foo",
        },
        "en:Main page": {
            "iwprefix": "en",
            "namespace": "",
            "pagename": "Main page",
            "sectionname": "",
            "fullpagename": "en:Main page",
        },
        "en:help:style#section": {
            "iwprefix": "en",
            "namespace": "Help",
            "pagename": "Style",
            "sectionname": "section",
            "fullpagename": "en:Help:Style",
        },

        # test stripping whitespace around colons
        "en : help : style # section": {
            "iwprefix": "en",
            "namespace": "Help",
            "pagename": "Style",
            "sectionname": " section",
            "fullpagename": "en:Help:Style",
        },

        # test anchor canonicalization
        "Main page #  _foo_  ": {
            "pagename": "Main page",
            "sectionname": " _foo_",
        },
        "#  _foo_  ": {
            "pagename": "",
            "sectionname": " _foo_",
        },

        # test MediaWiki-like properties
        "foo": {
            "fullpagename": "Foo",
            "pagename": "Foo",
            "basepagename": "Foo",
            "subpagename": "Foo",
            "rootpagename": "Foo",
            "articlepagename": "Foo",
            "talkpagename": "Talk:Foo",
            "namespace": "",
            "namespacenumber": 0,
            "articlespace": "",
            "talkspace": "Talk",
        },
        "talk:foo": {
            "fullpagename": "Talk:Foo",
            "pagename": "Foo",
            "basepagename": "Foo",
            "subpagename": "Foo",
            "rootpagename": "Foo",
            "articlepagename": "Foo",
            "talkpagename": "Talk:Foo",
            "namespace": "Talk",
            "namespacenumber": 1,
            "articlespace": "",
            "talkspace": "Talk",
        },
        "help talk:foo/Bar/baz": {
            "fullpagename": "Help talk:Foo/Bar/baz",
            "pagename": "Foo/Bar/baz",
            "basepagename": "Foo/Bar",
            "subpagename": "baz",
            "rootpagename": "Foo",
        },
        "Help talk:Style": {
            "articlepagename": "Help:Style",
            "talkpagename": "Help talk:Style",
            "namespace": "Help talk",
            "namespacenumber": 13,
            "articlespace": "Help",
            "talkspace": "Help talk",
        },
        "Help:Style": {
            "articlepagename": "Help:Style",
            "talkpagename": "Help talk:Style",
            "namespace": "Help",
            "namespacenumber": 12,
            "articlespace": "Help",
            "talkspace": "Help talk",
        },
    }

    def test(self):
        for src, expected in self.titles.items():
            yield self._do_test, src, expected

    def _do_test(self, src, expected):
        title = Title(fixtures.api, src)
        for attr, value in expected.items():
            assert_equals(getattr(title, attr), value)
