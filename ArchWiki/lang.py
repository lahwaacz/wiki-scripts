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
    {"name": "Български", "subtag": "bg", "english": "Bulgarian"},
    {"name": "Català", "subtag": "ca", "english": "Catalan"},
    {"name": "Česky", "subtag": "cs", "english": "Czech"},
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
    {"name": "Indonesia", "subtag": "id", "english": "Indonesian"},
    {"name": "Italiano", "subtag": "it", "english": "Italian"},
    {"name": "日本語", "subtag": "ja", "english": "Japanese"},
    {"name": "한국어", "subtag": "ko", "english": "Korean"},
    {"name": "Lietuviškai", "subtag": "lt", "english": "Lithuanian"},
    {"name": "Norsk Bokmål", "subtag": "nb", "english": "Norwegian (Bokmål)"},
    {"name": "Nederlands", "subtag": "nl", "english": "Dutch"},
    {"name": "Polski", "subtag": "pl", "english": "Polish"},
    {"name": "Português", "subtag": "pt", "english": "Portuguese"},
    {"name": "Română", "subtag": "ro", "english": "Romanian"},
    {"name": "Русский", "subtag": "ru", "english": "Russian"},
    {"name": "Slovenský", "subtag": "sk", "english": "Slovak"},
    {"name": "Српски", "subtag": "sr", "english": "Serbian"},
    {"name": "Svenska", "subtag": "sv", "english": "Swedish"},
    {"name": "ไทย", "subtag": "th", "english": "Thai"},
    {"name": "Türkçe", "subtag": "tr", "english": "Turkish"},
    {"name": "Українська", "subtag": "uk", "english": "Ukrainian"},
    {"name": "Tiếng Việt", "subtag": "vi", "english": "Vietnamese"},
    {"name": "简体中文", "subtag": "zh-cn", "english": "Chinese (Simplified)"},
    {"name": "正體中文", "subtag": "zh-tw", "english": "Chinese (Traditional)"},
]
# languages that have a category "Category:<lang>" on ArchWiki
__category_languages = [
    "العربية",
    "Български",
    "Català",
    "Česky",
    "Dansk",
    "Ελληνικά",
    "English",
    "Esperanto",
    "Español",
    "Suomi",
    "עברית",
    "Hrvatski",
    "Magyar",
    "Indonesia",
    "Italiano",
    "日本語",
    "한국어",
    "Lietuviškai",
    "Norsk Bokmål",
    "Nederlands",
    "Polski",
    "Português",
    "Русский",
    "Slovenský",
    "Српски",
    "ไทย",
    "Українська",
    "简体中文",
    "正體中文"
]
__interlanguage_external = ["de", "fa", "fi", "fr", "ja", "ro", "sv", "tr"]
__interlanguage_internal = ["ar", "bg", "cs", "da", "el", "en", "es", "he", "hr",
                            "hu", "id", "it", "ko", "lt", "nl", "pl", "pt",
                            "ru", "sk", "sr", "th", "uk", "zh-cn", "zh-tw"]


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


def get_category_languages():
    return __category_languages

def is_category_language(lang):
    return lang in get_category_languages()


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


def detect_language(title):
    """
    Detect language of a given title. The matching is case-sensitive and spaces are
    treated the same way as underscores.

    :param title: page title to work with
    :returns: a ``(pure, lang)`` tuple, where ``pure`` is the pure page title without
        the language suffix and ``lang`` is the detected language in long, localized form
    """
    pure_title = title
    detected_language = get_local_language()
    match = re.match(r"^(.+?)([ _]\(([^\(]+)\))?$", title)
    if match:
        lang = match.group(3)
        if lang in get_language_names():
            detected_language = lang
            pure_title = match.group(1)
    return pure_title, detected_language
