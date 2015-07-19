#! /usr/bin/env python3

# TODO:
#   placement of __NOTOC__, __NOEDITSECTION__
#   blank line at the top is sometimes removed, sometimes added
#   redirects are not handled properly
#   links to external wiki are not propagated to all other pages in the family

import os.path
import itertools

import mwparserfromhell

from MediaWiki import API
from MediaWiki.interactive import *
from MediaWiki.diff import diff_highlighted
import ArchWiki.lang as lang
import utils
from parser_helpers import canonicalize, remove_and_squash

def extract_header_parts(wikicode, magics=None, cats=None, interlinks=None):
    """
    According to Help:Style, the layout of the page should be as follows:
        1. Magic words (optional)
           (includes only {{DISPLAYTITLE:...}} and {{Lowercase title}})
        2. Categories
        3. Interlanguage links (if any)
        4. Article status templates (optional)
        5. Related articles box (optional)
        6. Preface or introduction
        7. Table of contents (automatic)
        8. Article-specific sections

    Only 1-3 are safe to be updated automatically. This function will extract the
    header parts and return them as tuple (magics, cats, interlinks). All returned
    objects are removed from the wikicode. Call `build_header` to insert them back
    into the wikicode.

    The parameters can be lists of objects (either string, wikicode or node) to be
    added to the header if not already present. These deduplication rules are applied:
        - supplied magic words take precedence over those present in wikicode
        - category links are considered duplicate when they point to the same category
          (e.g. [[Category:Foo]] is equivalent to [[category:foo]])
        - interlanguage links are considered duplicate when they have the same
          language tag (i.e. there can be only one interlanguage link for each
          language)

    The lists of magics and interlinks are sorted, the order of catlinks is preserved.
    """
    if magics is None:
        magics = []
    if cats is None:
        cats = []
    if interlinks is None:
        interlinks = []

    # make sure that we work with `Wikicode` objects
    magics = [mwparserfromhell.utils.parse_anything(item) for item in magics]
    cats = [mwparserfromhell.utils.parse_anything(item) for item in cats]
    interlinks = [mwparserfromhell.utils.parse_anything(item) for item in interlinks]

    def _prefix(title):
        if ":" not in title:
            return ""
        return title.split(":", 1)[0]

    def _add_to_magics(template):
        remove_and_squash(wikicode, template)
        if not any(magic.get(0).name.matches(template.name) for magic in magics):
            magics.append(mwparserfromhell.utils.parse_anything(template))

    def _add_to_cats(catlink):
        # TODO: non-duplicate "typos" are still ignored -- is this important enough to handle it?
        if not any(cat.get(0).title.matches(catlink.title) for cat in cats):
            # only remove from wikicode if we actually append to cats (duplicate category
            # links are considered typos, e.g. [[Category:foo]] instead of [[:Category:foo]],
            # which are quite common)
            remove_and_squash(wikicode, catlink)
            cats.append(mwparserfromhell.utils.parse_anything(catlink))

    def _add_to_interlinks(interlink):
        # always remove interlinks to handle renaming of pages
        # (typos such as [[en:Main page]] in text are quite rare)
        remove_and_squash(wikicode, interlink)
        if not any(_prefix(link.get(0).title).lower() == _prefix(interlink.title).lower() for link in interlinks):
            # not all tags work as interlanguage links
            if lang.is_interlanguage_tag(_prefix(interlink.title).lower()):
                interlinks.append(mwparserfromhell.utils.parse_anything(interlink))

    # all of magic words, catlinks and interlinks have effect even when nested
    # in other nodes, but let's ignore this case for now
    for template in wikicode.filter_templates(recursive=False):
        # TODO: temporary workaround for a bug in parser:
        #       https://github.com/earwig/mwparserfromhell/issues/111
        if not template.name:
            continue
        if canonicalize(template.name) == "Lowercase title" or _prefix(template.name) == "DISPLAYTITLE":
            _add_to_magics(template)

    for link in wikicode.filter_wikilinks(recursive=False):
        prefix = _prefix(link.title).lower()
        if prefix == "category":
            _add_to_cats(link)
        elif prefix in lang.get_language_tags():
            _add_to_interlinks(link)

    magics.sort()
    interlinks.sort()

    return magics, cats, interlinks

def build_header(wikicode, magics, cats, interlinks):
    # first remove starting newline
    if wikicode.startswith("\n"):
        first = wikicode.get(0)
        wikicode.replace(first, first.lstrip("\n"))
    count = 0
    for item in magics + cats + interlinks:
        wikicode.insert(count, item)
        wikicode.insert(count + 1, "\n")
        count += 2

def fix_header(wikicode):
    magics, cats, interlinks = extract_header_parts(wikicode)
    build_header(wikicode, magics, cats, interlinks)


class Interlanguage:
# TODO: make this a docstring (perhaps for the module rather than the class)
# algorithm:
# 1. fetch list of all pages with prop=langlinks to be able to build a langlink
#    graph (separate from the content dict for quick searching)
# 2. group pages into families based on their title, transform each group into
#    a Family object (The set of pages in the family will be denoted as
#    `titles`, it will change as pages are added to the family. The family name
#    corresponds to the only English page in the family.)
# 3. merge families based on the langlink graph queried from the wiki API
# 4. for each (family, page):
#    4.1 fetch content of the page
#    4.2 extract interlanguage links from the page
#    4.4 update the langlinks of the page as `family.titles - {title}`
#    4.5 save the page
#
# TODO: should be obsolete by the langlink map
# NOTE: Content of all pages is pulled into memory at the same time and not freed until the program exits,
#       so memory consumption will be huge. If the algorithm is modified to update pages one by one, the
#       memory consumption would stay at reasonable levels but a page could be edited multiple times as
#       families are merged, which is probably acceptable cost.

    namespaces = [0, 4, 10, 12, 14]
    edit_summary = "fix header, update interlanguage links (https://github.com/lahwaacz/wiki-scripts/blob/master/update-interlanguage-links.py)"

    def __init__(self, api):
        self.api = api

    def _get_allpages(self):
        print("Fetching langlinks property of all pages...")
        allpages = []
        # not necessary to wrap in each iteration since lists are mutable
        wrapped_titles = utils.ListOfDictsAttrWrapper(allpages, "title")

        for ns in self.namespaces:
            g = self.api.generator(generator="allpages", gapfilterredir="nonredirects", gapnamespace=ns, gaplimit="max", prop="langlinks", lllimit="max")
            for page in g:
                # the same page may be yielded multiple times with different pieces
                # of the information, hence the db_page.update()
                try:
                    db_page = utils.bisect_find(allpages, page["title"], index_list=wrapped_titles)
                    db_page.update(page)
                except IndexError:
                    utils.bisect_insert_or_replace(allpages, page["title"], data_element=page, index_list=wrapped_titles)
        return allpages

    @staticmethod
    def _group_into_families(pages):
        """
        Takes list of page titles, returns an iterator (itertools object) yielding
        a tuple of 2 elements: `family_key` and `family_iter`, where `family_key`
        is the base title without the language suffix (i.e. "Some title" for
        "Some title (Česky)") and `family_iter` is an iterator yielding the titles
        of pages that belong to the family (have the same `family_key`).
        """
        # interlanguage links are not valid for all languages, the invalid
        # need to be dropped now
        def _valid_interlanguage_pages():
            for page in pages:
                langname = lang.detect_language(page["title"])[1]
                tag = lang.tag_for_langname(langname)
                if lang.is_interlanguage_tag(tag):
                    yield page

        _family_key = lambda page: lang.detect_language(page["title"])[0]
        families_groups = itertools.groupby(_valid_interlanguage_pages(), key=_family_key)
        families = {}
        for family, pages in families_groups:
            families[family] = list(pages)
        return families

    @staticmethod
    def _merge_families(families):
        """
        Merges the families based on the "langlinks" property of the pages.
        """
        def _title_from_langlink(langlink):
            return "{} ({})".format(langlink["*"], lang.langname_for_tag(langlink["lang"]))

        def _merge(family1, family2):
            assert(family1 != family2)
            try:
                pages1 = families[family1]
                pages2 = families[family2]
            except KeyError:
                return
            langs1 = set(lang.detect_language(page["title"])[1] for page in pages1)
            langs2 = set(lang.detect_language(page["title"])[1] for page in pages2)

            # merge only if the intersection is an empty set
            if langs1 & langs2 == set():
                # swap the corresponding objects to have the English page in the
                # 1st family (if present)
                if "English" in langs2:
                    family1, family2 = family2, family1
                    pages1, pages2 = pages2, pages1
                    langs1, langs2 = langs2, langs1

                # merge the 2nd family into the 1st
                pages1 += pages2
                families.pop(family2)
            # TODO: figure out what to do else
#            else:
#                print("merging families would result in multiple pages of the same language in the family")
#                print("Family", family1)
#                print(pages1)
#                print(langs1)
#                print("Family", family2)
#                print(pages2)
#                print(langs2)
#                input()

        for family in list(families.keys()):
            # We need to iterate from copy of the keys because the size of the
            # main dict changes during iteration. Then we need to check if the
            # key is still valid.
            try:
                pages = families[family]
            except KeyError:
                continue

            for page in pages:
                # default to empty tuple
                for langlink in page.get("langlinks", ()):
                    title = _title_from_langlink(langlink)
                    if title not in [page["title"] for page in pages]:
                        newfamily = langlink["*"]
                        if family != newfamily:
                            _merge(family, newfamily)

    @staticmethod
    def _update_interlanguage_links(text, title, family_titles):
        """
        :param title: title of the page to update (str)
        :param family_titles: titles of the family to appear on the page (set)
        :returns: updated wikicode
        """
        # the page should not have a link to itself
        assert title not in family_titles

        # transform suffix into prefix and construct interlanguage links
        # e.g. "Some title (Česky)" into "cs:Some title"
        def _transform_title(title):
            pure, langname = lang.detect_language(title)
            tag = lang.tag_for_langname(langname)
            # FIXME: ``tag`` is always lowercase, but ArchWiki uses strictly capitalized
            # versions for zh-CN and zh-TW, even though MediaWiki recognizes language
            # tags case insensitively
            if tag == "zh-cn":
                tag = "zh-CN"
            if tag == "zh-tw":
                tag = "zh-TW"
            return "[[{}:{}]]".format(tag, pure)

        interlinks = sorted(_transform_title(title) for title in family_titles)

        wikicode = mwparserfromhell.parse(text)
        magics, cats, interlinks = extract_header_parts(wikicode, interlinks=interlinks)
        # TODO: check if the interlinks are valid, handle redirects etc.
        build_header(wikicode, magics, cats, interlinks)
        return wikicode

    def update_allpages(self, ns=0):
        allpages = self._get_allpages()
        allpages.sort(key=lambda page: page["title"])
        families = self._group_into_families(allpages)
        self._merge_families(families)

        # TODO: it should be theoretically possible to determine which pages need
        #       to be changed from the langlink graph and families groups
        # create inverse mapping for fast searching
        family_index = {}
        for family, pages in families.items():
            for page in pages:
                family_index[page["title"]] = family

        for ns in self.namespaces:
            g = self.api.generator(generator="allpages", gaplimit="max", gapfilterredir="nonredirects", gapnamespace=ns, prop="revisions", rvprop="content|timestamp")
            for page in g:
                # the same page may be yielded multiple times with different pieces
                # of the information, so we need to check if the expected properties
                # are already available
                if "revisions" in page:
                    title = page["title"]
                    print("Processing page '{}'".format(title))

                    text_old = page["revisions"][0]["*"]
                    timestamp = page["revisions"][0]["timestamp"]

                    family_pages = families[family_index[title]]
                    # TODO: include titles from langlinks (e.g. external wikis)
                    family_titles = set(page["title"] for page in family_pages)
                    assert(title in family_titles)
                    text_new = self._update_interlanguage_links(text_old, title, family_titles - {title})

                    if text_old != text_new:
                        print("    pages in family:", family_titles)
                        edit_interactive(api, page["pageid"], text_old, text_new, timestamp, self.edit_summary, bot="")
#                        self.api.edit(page["pageid"], text_new, timestamp, self.edit_summary, bot="")
#                        print(diff_highlighted(text_old, text_new))
#                        input()


if __name__ == "__main__":
    api_url = "https://wiki.archlinux.org/api.php"
    cookie_path = os.path.expanduser("~/.cache/ArchWiki.bot.cookie")

    api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

    il = Interlanguage(api)
    il.update_allpages()

    snippet = """
__TOC__

Some text with [[it:interlink]] inside.

[[Category:foo]]
This [[category:foo|catlink]] is a typo.
[[en:bar]]

Some other text [[link]]
[[category:bar]]
[[cs:some page]]

{{DISPLAYTITLE:lowercase title}}
{{Lowercase title}}
"""

    snippet = """
{{out of date}}
[[Category:ASUS]]
==Hardware==
"""

#    wikicode = mwparserfromhell.parse(snippet)
#    fix_header(wikicode)
#    print(snippet, end="")
#    print("=" * 42)
#    print(wikicode, end="")
