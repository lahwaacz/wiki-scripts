#! /usr/bin/env python3

import pytest

from ws.ArchWiki.lang import *

# data for testing (expected values)
language_names = ["العربية", "Bosanski", "Български", "Català", "Čeština", "Dansk", "Deutsch", "Ελληνικά", "English", "Esperanto", "Español", "فارسی", "Suomi", "Français", "עברית", "Hrvatski", "Magyar", "Bahasa Indonesia", "Italiano", "日本語", "한국어", "Lietuvių", "Norsk Bokmål", "Nederlands", "Polski", "Português", "Română", "Русский", "Slovenčina", "Српски", "Svenska", "ไทย", "Türkçe", "Українська", "Tiếng Việt", "粵語", "简体中文", "正體中文"]
english_language_names = ["Arabic", "Bosnian", "Bulgarian", "Catalan", "Czech", "Danish", "German", "Greek", "English", "Esperanto", "Spanish", "Persian", "Finnish", "French", "Hebrew", "Croatian", "Hungarian", "Indonesian", "Italian", "Japanese", "Korean", "Lithuanian", "Norwegian (Bokmål)", "Dutch", "Polish", "Portuguese", "Romanian", "Russian", "Slovak", "Serbian", "Swedish", "Thai", "Turkish", "Ukrainian", "Vietnamese", "Cantonese", "Chinese (Simplified)", "Chinese (Traditional)"]
language_tags = ["ar", "bs", "bg", "ca", "cs", "da", "de", "el", "en", "eo", "es", "fa", "fi", "fr", "he", "hr", "hu", "id", "it", "ja", "ko", "lt", "nb", "nl", "pl", "pt", "ro", "ru", "sk", "sr", "sv", "th", "tr", "uk", "vi", "yue", "zh-hans", "zh-hant"]
external_tags = ["de", "fa", "fr", "ja", "sv"]
internal_tags = ["ar", "bs", "bg", "cs", "da", "el", "en", "es", "fi", "he", "hr", "hu", "id", "it", "ko", "lt", "nl", "pl", "pt", "ru", "sk", "sr", "th", "tr", "uk", "zh-hans", "zh-hant"]
rtl_languages = ["עברית", "العربية"]
rtl_tags = ["ar", "he"]

class test_getters:
    def _test(self, values, getter):
        result = getter()
        assert values == result

    def test_get_language_names(self):
        self._test(language_names, get_language_names)

    def test_get_english_language_names(self):
        self._test(english_language_names, get_english_language_names)

    def test_get_language_tags(self):
        self._test(language_tags, get_language_tags)

    def test_get_external_tags(self):
        self._test(external_tags, get_external_tags)

    def test_get_internal_tags(self):
        self._test(internal_tags, get_internal_tags)

class test_checkers:
    def _test(self, values, checker):
        for value in values:
            assert checker(value) is True

    def test_is_language_name(self):
        self._test(language_names, is_language_name)

    def test_is_english_language_name(self):
        self._test(english_language_names, is_english_language_name)

    def test_is_language_tag(self):
        self._test(language_tags, is_language_tag)

    def test_is_rtl_tag(self):
        self._test(rtl_tags, is_rtl_tag)

    def test_is_rtl_language(self):
        self._test(rtl_languages, is_rtl_language)

    def test_is_external_tag(self):
        self._test(external_tags, is_external_tag)

    def test_is_internal_tag(self):
        self._test(internal_tags, is_internal_tag)

#class test_languages_data_sanity:
#    """
#    Tests sanity of the languages' data.
#    """
#
## FIXME: failing because some tags are not supported (i.e. not registered in the
##        interwiki map on ArchWiki, see the table in
##        https://wiki.archlinux.org/index.php/Help:I18n
#    def test_tags_concatenation(self):
#        assert_count_equal(get_language_tags(), get_external_tags() + get_internal_tags())

class test_conversion:
    # list of (targetlist, srclist, target_for_src_function) tuples
    # the lists must be sorted so that the values with same indexes correspond
    testsuite = [
        (language_names, english_language_names, langname_for_english),
        (language_names, language_tags, langname_for_tag),
        (english_language_names, language_names, english_for_langname),
        (english_language_names, language_tags, english_for_tag),
        (language_tags, language_names, tag_for_langname),
        (language_tags, english_language_names, tag_for_english),
    ]

    def test(self):
        for targetlist, srclist, conversion_func in self.testsuite:
            for lang in srclist:
                expected = targetlist[srclist.index(lang)]
                assert conversion_func(lang) == expected

class test_detect_language:
    default = get_local_language()

    # mapping of input to expected result
    testsuite = {
        "": ("", default),
        "foo": ("foo", default),
        "foo (bar)": ("foo (bar)", default),
        "foo (Čeština)": ("foo", "Čeština"),
        "foo_bar": ("foo_bar", default),
        "foo_(Čeština)": ("foo", "Čeština"),
        "foo(Čeština)": ("foo(Čeština)", default),
        "foo/bar": ("foo/bar", default),

        # ArchWiki uses only one scheme, but wiki-scripts should detect both
        # schemes to not be confused by users' errors. See also FS#39668:
        # https://bugs.archlinux.org/task/39668
        "foo/bar (Čeština)": ("foo/bar", "Čeština"),
        "foo (Čeština)/bar": ("foo/bar", "Čeština"),
        # new scheme as of 2019:
        # https://wiki.archlinux.org/index.php?title=Help_talk:I18n&oldid=624942#Localized_subpages
        "foo (Čeština)/bar (Čeština)": ("foo/bar", "Čeština"),
        "foo (Italiano)/bar (Čeština)": ("foo (Italiano)/bar", "Čeština"),

        # this case used to be for old pages, the suffix for English pages is not used
        # nevertheless it is useful to keep the algorithm simple
        "foo (English)": ("foo", "English"),

        # language categories
        "Category:Foo": ("Category:Foo", default),
        "Category:Čeština": ("Category:Čeština", "Čeština"),
    }

    @pytest.mark.parametrize("title, expected", testsuite.items())
    def test_suite(self, title, expected):
        assert detect_language(title) == expected

    @pytest.mark.parametrize("lang", language_names)
    def test_all_langs(self, lang):
        assert detect_language("foo ({})".format(lang)) == ("foo", lang)

    @pytest.mark.parametrize("lang", language_names)
    def test_all_cats(self, lang):
        title = "Category:{}".format(lang)
        assert detect_language(title) == (title, lang)

class test_format_title:
    default = get_local_language()

    # mapping of input to expected result
    testsuite = {
        "": ("", default),
        "foo": ("foo", default),
        "foo (bar)": ("foo (bar)", default),
        "foo (Čeština)": ("foo", "Čeština"),
        "foo bar": ("foo bar", default),
        "foo (Čeština)": ("foo", "Čeština"),
        "foo(Čeština)": ("foo(Čeština)", default),
        "foo/bar": ("foo/bar", default),

        # new scheme as of 2019:
        # https://wiki.archlinux.org/index.php?title=Help_talk:I18n&oldid=624942#Localized_subpages
        "foo (Čeština)/bar (Čeština)": ("foo/bar", "Čeština"),

        # language categories
        "Category:Foo": ("Category:Foo", default),
        "Category:Čeština": ("Category:Čeština", "Čeština"),
    }

    @pytest.mark.parametrize("title, expected", testsuite.items())
    def test_suite(self, title, expected):
        assert format_title(*expected) == title

    @pytest.mark.parametrize("lang", language_names)
    def test_all_langs(self, lang):
        if lang == self.default:
            expected = "foo"
        else:
            expected = "foo ({})".format(lang)
        assert format_title("foo", lang) == expected

    @pytest.mark.parametrize("lang", language_names)
    def test_all_cats(self, lang):
        title = "Category:{}".format(lang)
        assert format_title(title, lang) == title

    def test_invalid_langname(self):
        with pytest.raises(ValueError):
            format_title("foo", "bar")
