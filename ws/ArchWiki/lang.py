#! /usr/bin/env python

"""
The :py:mod:`ArchWiki.lang` submodule contains multiple functions related to
ArchWiki specific way of setting localized page titles, handling of categories
for localized pages etc.

See the documentation on `Help:i18n`_ on ArchWiki for the specification.

.. _`Help:i18n`: https://wiki.archlinux.org/index.php/Help:I18n
"""

import re

# some module-global variables, private to the module
__local_language = "English"
# language data, sorted by subtag
__languages = [
    {"name": "العربية", "subtag": "ar", "english": "Arabic"},
    {"name": "Bosanski", "subtag": "bs", "english": "Bosnian"},
    {"name": "Български", "subtag": "bg", "english": "Bulgarian"},
    {"name": "Català", "subtag": "ca", "english": "Catalan"},
    {"name": "Čeština", "subtag": "cs", "english": "Czech"},
    {"name": "Dansk", "subtag": "da", "english": "Danish"},
    {"name": "Deutsch", "subtag": "de", "english": "German"},
    {"name": "Ελληνικά", "subtag": "el", "english": "Greek"},
    {"name": "English", "subtag": "en", "english": "English"},
    {"name": "Esperanto", "subtag": "eo", "english": "Esperanto"},
    {"name": "Español", "subtag": "es", "english": "Spanish"},
    {"name": "فارسی", "subtag": "fa", "english": "Persian"},
    {"name": "Suomi", "subtag": "fi", "english": "Finnish"},
    {"name": "Français", "subtag": "fr", "english": "French"},
    {"name": "עברית", "subtag": "he", "english": "Hebrew"},
    {"name": "Hrvatski", "subtag": "hr", "english": "Croatian"},
    {"name": "Magyar", "subtag": "hu", "english": "Hungarian"},
    {"name": "Bahasa Indonesia", "subtag": "id", "english": "Indonesian"},
    {"name": "Italiano", "subtag": "it", "english": "Italian"},
    {"name": "日本語", "subtag": "ja", "english": "Japanese"},
    {"name": "한국어", "subtag": "ko", "english": "Korean"},
    {"name": "Lietuvių", "subtag": "lt", "english": "Lithuanian"},
    {"name": "Norsk Bokmål", "subtag": "nb", "english": "Norwegian (Bokmål)"},
    {"name": "Nederlands", "subtag": "nl", "english": "Dutch"},
    {"name": "Polski", "subtag": "pl", "english": "Polish"},
    {"name": "Português", "subtag": "pt", "english": "Portuguese"},
    {"name": "Română", "subtag": "ro", "english": "Romanian"},
    {"name": "Русский", "subtag": "ru", "english": "Russian"},
    {"name": "Slovenčina", "subtag": "sk", "english": "Slovak"},
    {"name": "Српски", "subtag": "sr", "english": "Serbian"},
    {"name": "Svenska", "subtag": "sv", "english": "Swedish"},
    {"name": "ไทย", "subtag": "th", "english": "Thai"},
    {"name": "Türkçe", "subtag": "tr", "english": "Turkish"},
    {"name": "Українська", "subtag": "uk", "english": "Ukrainian"},
    {"name": "Tiếng Việt", "subtag": "vi", "english": "Vietnamese"},
    {"name": "粵語", "subtag": "yue", "english": "Cantonese"},
    {"name": "简体中文", "subtag": "zh-hans", "english": "Chinese (Simplified)"},
    {"name": "正體中文", "subtag": "zh-hant", "english": "Chinese (Traditional)"},
]
# languages with right-to-left script
__rtl = ["ar", "he"]
__interlanguage_external = ["de", "fa", "fr", "ja", "sv"]
__interlanguage_internal = ["ar", "bs", "bg", "cs", "da", "el", "en", "es", "fi", "he",
                            "hr", "hu", "id", "it", "ko", "lt", "nl", "pl", "pt",
                            "ru", "sk", "sr", "th", "tr", "uk", "zh-hans", "zh-hant"]


# basic accessors and checkers
def get_local_language():
    return __local_language

def get_language_names():
    return [lang["name"] for lang in __languages]

def is_language_name(lang):
    return lang in get_language_names()

def get_english_language_names():
    return [lang["english"] for lang in __languages]

def is_english_language_name(lang):
    return lang in get_english_language_names()

def get_language_tags():
    return [lang["subtag"] for lang in __languages]

def is_language_tag(tag):
    return tag.lower() in get_language_tags()


def is_rtl_tag(tag):
    return tag in __rtl

def is_rtl_language(lang):
    return is_rtl_tag(tag_for_langname(lang))


def get_interlanguage_tags():
    return __interlanguage_external + __interlanguage_internal

def is_interlanguage_tag(tag):
    return tag.lower() in get_interlanguage_tags()

def get_external_tags():
    return __interlanguage_external

def is_external_tag(tag):
    return tag.lower() in get_external_tags()

def get_internal_tags():
    return __interlanguage_internal

def is_internal_tag(tag):
    return tag.lower() in get_internal_tags()


# conversion between (local) language names, English language names and subtags
def langname_for_english(lang):
    language = [language for language in __languages if language["english"] == lang][0]
    return language["name"]

def langname_for_tag(tag):
    language = [language for language in __languages if language["subtag"] == tag.lower()][0]
    return language["name"]

def english_for_langname(lang):
    language = [language for language in __languages if language["name"] == lang][0]
    return language["english"]

def english_for_tag(tag):
    language = [language for language in __languages if language["subtag"] == tag.lower()][0]
    return language["english"]

def tag_for_langname(lang):
    language = [language for language in __languages if language["name"] == lang][0]
    return language["subtag"]

def tag_for_english(lang):
    language = [language for language in __languages if language["english"] == lang][0]
    return language["subtag"]


def detect_language(title, *, strip_all_subpage_parts=True):
    """
    Detect language of a given title. The matching is case-sensitive and spaces are
    treated the same way as underscores.

    :param title: page title to work with
    :returns: a ``(pure, lang)`` tuple, where ``pure`` is the pure page title without
        the language suffix and ``lang`` is the detected language in long, localized form
    """
    title_regex = r"(?P<pure>.*?)[ _]\((?P<lang>[^\(\)]+)\)"
    pure_suffix = ""
    # matches "Page name/Subpage (Language)"
    match = re.fullmatch(title_regex, title)
    # matches "Page name (Language)/Subpage"
    if not match and "/" in title:
        base, pure_suffix = title.split("/", maxsplit=1)
        pure_suffix = "/" + pure_suffix
        match = re.fullmatch(title_regex, base)
    # matches "Category:Language"
    if not match:
        match = re.fullmatch(r"(?P<pure>[Cc]ategory[ _]?\:[ _]?(?P<lang>[^\(\)]+))", title)
    if match:
        pure = match.group("pure")
        lang = match.group("lang")
        if lang in get_language_names():
            # strip "(Language)" from all subpage components to handle cases like
            # "Page name (Language)/Subpage (Language)"
            if strip_all_subpage_parts is True and "/" in pure:
                parts = pure.split("/")
                new_parts = []
                for p in parts:
                    match = re.fullmatch(title_regex, p)
                    if match:
                        part_lang = match.group("lang")
                        if part_lang == lang:
                            new_parts.append(match.group("pure"))
                        else:
                            new_parts.append(p)
                    else:
                        new_parts.append(p)
                pure = "/".join(new_parts)
            return pure + pure_suffix, lang
    return title, get_local_language()

def format_title(title, langname, *, augment_all_subpage_parts=True):
    """
    Formats a local title for given base title and language. It is basically
    an inverse operation for :py:func:`detect_language`.

    :param str title: the base title
    :param str langname: the language name of the title to be produced
    :returns: a string representing the local title
    """
    if not is_language_name(langname):
        raise ValueError("Invalid language name: {}".format(langname))
    # local language
    if langname == get_local_language():
        return title
    # master category for language
    if title.lower() == "category:" + langname.lower():
        return title
    # add "(Language)" suffix to all subpage parts, see https://wiki.archlinux.org/index.php/Help:I18n#Page_titles
    if augment_all_subpage_parts is True and is_internal_tag(tag_for_langname(langname)) and "/" in title:
        title = "/".join("{} ({})".format(p, langname) for p in title.split("/"))
        return title
    return "{} ({})".format(title, langname)
