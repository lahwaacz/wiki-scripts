#! /usr/bin/env python3

from nose.tools import assert_equals, assert_false, raises
from nose.plugins.attrib import attr

from . import fixtures

from ws.core.api import LoginFailed

@attr(speed="slow")
class test_api:
    """
    Some basic sanity checks, intended mostly for detecting changes in the
    ArchWiki configuration.
    """

    # uncategorized categories on ArchWiki (should be only these all the time)
    uncat_cats = ["Category:Archive", "Category:DeveloperWiki", "Category:Languages", "Category:Maintenance", "Category:Sandbox"]

    # check correct server
    def test_hostname(self):
        assert_equals(fixtures.api.get_hostname(), "wiki.archlinux.org")

# TODO: not sure if this is such a good idea...
#    # test LoginFailed exception
#    @raises(LoginFailed)
#    def test_login_failed(self):
#        fixtures.api.login("wiki-scripts testing invalid user", "invalid password")

    # this is anonymous test
    def test_is_loggedin(self):
        assert_false(fixtures.api.user.is_loggedin)

    # check user rights for anonymous users
    def test_user_rights(self):
        expected = ["createaccount", "read", "createpage", "createtalk",
                    "editmyusercss", "editmyuserjs", "viewmywatchlist",
                    "editmywatchlist", "viewmyprivateinfo", "editmyprivateinfo",
                    "editmyoptions", "abusefilter-log-detail", "abusefilter-view",
                    "abusefilter-log"]
        assert_equals(fixtures.api.user.rights, expected)

    def test_max_ids_per_query(self):
        assert_equals(fixtures.api.max_ids_per_query, 50)

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

    # testing on uncategorized categories (should contain only 5 items all the time)
    def test_query_continue(self):
        q = fixtures.api.query_continue(action="query", list="querypage", qppage="Uncategorizedcategories", qplimit=1)
        titles = []
        for chunk in q:
            titles += [i["title"] for i in chunk["querypage"]["results"]]
        assert_equals(titles, self.uncat_cats)

    def test_list(self):
        q = fixtures.api.list(list="querypage", qppage="Uncategorizedcategories", qplimit="max")
        titles = []
        for i in q:
            titles.append(i["title"])
        assert_equals(titles, self.uncat_cats)

    def test_generator(self):
        q = fixtures.api.generator(generator="querypage", gqppage="Uncategorizedcategories", gqplimit="max")
        titles = []
        for i in q:
            titles.append(i["title"])
        assert_equals(titles, self.uncat_cats)
