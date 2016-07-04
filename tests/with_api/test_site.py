#! /usr/bin/env python3

from nose.tools import assert_equals, assert_false, raises
from nose.plugins.attrib import attr

from . import fixtures

from ws.core.api import LoginFailed

@attr(speed="slow")
class test_site:

    def test_coverage(self):
        paraminfo = fixtures.api.call_api(action="paraminfo", modules="query+siteinfo")
        properties = set(paraminfo["modules"][0]["parameters"][0]["type"])
        assert_equals(properties, fixtures.api.site.properties)

    def test_interwikimap(self):
        expected = set(['ar', 'arxiv', 'bg', 'commons', 'cs', 'da', 'de', 'debian', 'doi', 'el', 'emacswiki', 'en', 'es', 'fa', 'fi', 'foldoc', 'fr', 'freebsdman', 'funtoo', 'gentoo', 'gregswiki', 'he', 'hr', 'hu', 'id', 'it', 'ja', 'ko', 'linuxwiki', 'lqwiki', 'lt', 'meta', 'metawikimedia', 'mozillawiki', 'mw', 'nl', 'phab', 'phabricator', 'pl', 'pt', 'rfc', 'ro', 'ru', 'sk', 'sourceforge', 'sr', 'sv', 'th', 'tr', 'uk', 'w', 'wikia', 'wikibooks', 'wikimedia', 'wikinews', 'wikipedia', 'wikiquote', 'wikisource', 'wikispecies', 'wikiversity', 'wikivoyage', 'wikt', 'wiktionary', 'wmf', 'zh-cn', 'zh-tw'])
        assert_equals(set(fixtures.api.site.interwikimap), expected)

    def test_interlanguagemap(self):
        external_tags = ["de", "fa", "fi", "fr", "ja", "ro", "sv", "tr"]
        internal_tags = ["ar", "bg", "cs", "da", "el", "en", "es", "he", "hr", "hu", "id", "it", "ko", "lt", "nl", "pl", "pt", "ru", "sk", "sr", "th", "uk", "zh-cn", "zh-tw"]
        expected = set(external_tags + internal_tags)
        assert_equals(set(fixtures.api.site.interlanguagemap), expected)

    def test_namespaces(self):
        expected = {0: '', 1: 'Talk', 2: 'User', 3: 'User talk', 4: 'ArchWiki', 5: 'ArchWiki talk', 6: 'File', 7: 'File talk', 8: 'MediaWiki', 9: 'MediaWiki talk', 10: 'Template', 11: 'Template talk', 12: 'Help', 13: 'Help talk', 14: 'Category', 15: 'Category talk', -1: 'Special', -2: 'Media'}
        assert_equals(fixtures.api.site.namespaces, expected)

