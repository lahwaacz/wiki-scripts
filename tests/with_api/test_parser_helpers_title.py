#! /usr/bin/env python3

from nose.tools import assert_equals, assert_true, raises
from nose.plugins.attrib import attr

from . import fixtures
from ws.parser_helpers.title import *

class test_canonicalize:
    # keys: input, values: expected result
    titles = {
        "": "",
        " _  ": "",
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
            "sectionname": "section",
            "fullpagename": "en:Help:Style",
        },

        # test anchor canonicalization
        "Main page #  _foo_  ": {
            "pagename": "Main page",
            "sectionname": "foo",
        },
        "#  _foo_  ": {
            "pagename": "",
            "sectionname": "foo",
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

        # test local/external namespaces
        "en:Foo:Bar": {
            "iwprefix": "en",
            "namespace": "",
            "pagename": "Foo:Bar",
            "fullpagename": "en:Foo:Bar",
        },
        "wikipedia:Foo:Bar": {
            "iwprefix": "wikipedia",
            "namespace": "Foo",
            "pagename": "Bar",
            "fullpagename": "wikipedia:Foo:Bar",
        },

        # test alternative namespace names
        "Project:Foo": {
            "iwprefix": "",
            "namespace": "Project",
            "pagename": "Foo",
            "fullpagename": "Project:Foo",
        },
        "Image:Foo": {
            "iwprefix": "",
            "namespace": "Image",
            "pagename": "Foo",
            "fullpagename": "Image:Foo",
        },

        # test colons
        ":Category:Foo": {
            "iwprefix": "",
            "namespace": "Category",
            "pagename": "Foo",
            "fullpagename": "Category:Foo",
        },
        "Foo::Bar": {
            "iwprefix": "",
            "namespace": "",
            "pagename": "Foo::Bar",
            "fullpagename": "Foo::Bar",
        },
        "::Help:Style": {
            "iwprefix": "",
            "namespace": "Help",
            "pagename": "Style",
            "fullpagename": "Help:Style",
        },
        "wikipedia::Wikipedia:Manual of Style": {
            "iwprefix": "wikipedia",
            "namespace": "Wikipedia",
            "pagename": "Manual of Style",
            "fullpagename": "wikipedia:Wikipedia:Manual of Style",
        },
        # even MediaWiki chokes on this one (rendered as plain text instead of link)
        "Help::Style": {
            "iwprefix": "",
            "namespace": "Help",
            "pagename": "Style",
            "fullpagename": "Help:Style",
        },
    }

    def test(self):
        for src, expected in self.titles.items():
            yield self._do_test, src, expected

    def _do_test(self, src, expected):
        title = Title(fixtures.api, src)
        for attr, value in expected.items():
            assert_equals(getattr(title, attr), value)

@attr(speed="slow")
class test_title_setters():
    attributes = ["iwprefix", "namespace", "pagename", "sectionname"]

    @classmethod
    def setup_class(klass):
        klass.api = fixtures.api

    def setup(self):
        self.title = Title(self.api, "en:Help:Style#section")


    @raises(TypeError)
    def _do_type_test(self, attr, value):
        setattr(self.title, attr, value)

    def test_invalid_type(self):
        for attr in self.attributes:
            yield self._do_type_test, attr, None


    def test_iwprefix(self):
        assert_equals(self.title.iwprefix, "en")
        assert_equals(str(self.title), "en:Help:Style#section")
        # test internal tag
        self.title.iwprefix = "cs"
        assert_equals(self.title.iwprefix, "cs")
        assert_equals(str(self.title), "cs:Help:Style#section")
        # test external tag
        self.title.iwprefix = "de"
        assert_equals(self.title.iwprefix, "de")
        assert_equals(str(self.title), "de:Help:Style#section")
        # test empty
        self.title.iwprefix = ""
        assert_equals(self.title.iwprefix, "")
        assert_equals(str(self.title), "Help:Style#section")

    def test_namespace(self):
        assert_equals(self.title.namespace, "Help")
        assert_equals(str(self.title), "en:Help:Style#section")
        # test talkspace
        self.title.namespace = self.title.talkspace
        assert_equals(self.title.namespace, "Help talk")
        assert_equals(str(self.title), "en:Help talk:Style#section")
        # test namespace canonicalization
        self.title.namespace = "helP_ Talk"
        assert_equals(self.title.namespace, "Help talk")
        assert_equals(str(self.title), "en:Help talk:Style#section")
        # test empty
        self.title.namespace = ""
        assert_equals(self.title.namespace, "")
        assert_equals(str(self.title), "en:Style#section")

    def test_pagename(self):
        assert_equals(self.title.pagename, "Style")
        assert_equals(str(self.title), "en:Help:Style#section")
        # test simple
        self.title.pagename = "Main page"
        assert_equals(self.title.pagename, "Main page")
        assert_equals(str(self.title), "en:Help:Main page#section")
        # test canonicalize
        self.title.pagename = " foo  _Bar_"
        assert_equals(self.title.pagename, "Foo Bar")
        assert_equals(str(self.title), "en:Help:Foo Bar#section")

    def test_sectionname(self):
        assert_equals(self.title.sectionname, "section")
        assert_equals(str(self.title), "en:Help:Style#section")
        # test simple
        self.title.sectionname = "another section"
        assert_equals(self.title.sectionname, "another section")
        assert_equals(str(self.title), "en:Help:Style#another section")
        # test canonicalize
        self.title.sectionname = " foo  _Bar_"
        assert_equals(self.title.sectionname, "foo Bar")
        assert_equals(str(self.title), "en:Help:Style#foo Bar")


    def test_eq(self):
        other_title = Title(self.api, "")
        other_title.iwprefix = "en"
        other_title.namespace = "Help"
        other_title.pagename = "Style"
        other_title.sectionname = "section"
        assert_true(self.title == other_title)

    def test_str_repr(self):
        self.title.iwprefix = ""
        self.title.namespace = ""
        self.title.pagename = "Main page"
        self.title.sectionname = ""
        assert_equals(str(self.title), "Main page")
        assert_equals(repr(self.title), "<class 'ws.parser_helpers.title.Title'>('Main page')")


    @raises(ValueError)
    def test_invalid_iwprefix(self):
        self.title.iwprefix = "invalid prefix"

    @raises(ValueError)
    def test_invalid_namespace(self):
        self.title.namespace = "invalid namespace"
