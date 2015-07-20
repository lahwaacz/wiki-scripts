#! /usr/bin/env python3

# TODO:
#   take the final title from "displaytitle" property (available from API)

import os.path
import itertools
import re

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
        return title.split(":", 1)[0].strip()

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
    # first strip blank lines if there is some text
    if len(wikicode.nodes) > 0:
        first = wikicode.get(0)
        if isinstance(first, mwparserfromhell.nodes.text.Text):
            firstline = first.value.splitlines(keepends=True)[0]
            while firstline.strip() == "":
                first.value = first.value.replace(firstline, "", 1)
                if first.value == "":
                    break
                firstline = first.value.splitlines(keepends=True)[0]
    count = 0
    for item in magics + cats + interlinks:
        wikicode.insert(count, item)
        wikicode.insert(count + 1, "\n")
        count += 2

def fix_header(wikicode):
    magics, cats, interlinks = extract_header_parts(wikicode)
    build_header(wikicode, magics, cats, interlinks)


class Interlanguage:
    """
    Update interlanguage links on ArchWiki based on the following algorithm:

     1. Fetch list of all pages with prop=langlinks to be able to build a langlink
        graph (separate from the content dict for quick searching).
     2. Group pages into families based on their title, which is the primary key to
        denote a family. The grouping is case-insensitive and includes even pages
        without any interlanguage links. The family name corresponds to the only
        English page in the family (or when not present, to the English base of the
        localized title).
     3. For every page on the wiki:
        3.1 Fetch content of the page.
        3.2 Determine the family of the page.
        3.3 Assemble a set of pages in the family. This is done by first including
            the pages in the group from step 2., then pulling any internal langlinks
            from the pages in the set (in unspecified order), and finally based on
            the presence of an English page in the family:
              - If there is an English page, its external langlinks are pulled in.
                As a result, external langlinks removed from the English page are
                assumed to be invalid and removed also from other pages. For
                consistency, also internal langlinks are pulled from the English page.
              - If there is not an English page, external langlinks are pulled from
                the other pages (in unspecified order), which completes the previous
                inclusion of internal langlinks.
        3.4 Update the langlinks of the page as ``family.titles - {title}``.
        3.5 If there is a difference, save the page.
    """

    namespaces = [0, 4, 10, 12, 14]
    edit_summary = "update interlanguage links (https://github.com/lahwaacz/wiki-scripts/blob/master/update-interlanguage-links.py)"

    def __init__(self, api):
        self.api = api
        self.redirects = self.api.redirects_map()

        self.allpages = None
        self.families = None

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
        Takes list of pages and groups them based on their title. Returns a
        mapping of `family_key` to `family_pages`, where `family_key` is the
        base title without the language suffix (e.g. "Some title" for
        "Some title (Česky)") and `family_pages` is a list of pages belonging
        to the family (have the same `family_key`).
        """
        # interlanguage links are not valid for all languages, the invalid
        # need to be dropped now
        def _valid_interlanguage_pages(pages):
            for page in pages:
                langname = lang.detect_language(page["title"])[1]
                tag = lang.tag_for_langname(langname)
                if lang.is_interlanguage_tag(tag):
                    yield page

        _family_key = lambda page: lang.detect_language(page["title"])[0].lower()
        families_groups = itertools.groupby(_valid_interlanguage_pages(pages), key=_family_key)
        families = {}
        for family, pages in families_groups:
            families[family] = list(pages)
        return families

    def _title_from_langlink(self, langlink):
        langname = lang.langname_for_tag(langlink["lang"])
        if langname == "English":
            title = langlink["*"]
        else:
            title = "{} ({})".format(langlink["*"], langname)
        if lang.is_internal_tag(langlink["lang"]):
            title = canonicalize(title)
            # resolve redirects
            if title in self.redirects:
                title = self.redirects[title].split("#", maxsplit=1)[0]
        return title

    def _titles_in_family(self, family_pages):
        tags = set()
        titles = set()

        # populate titles/tags with the already present pages
        for page in family_pages:
            title = page["title"]
            tag = lang.tag_for_langname(lang.detect_language(title)[1])
            tags.add(tag)
            titles.add(title)

        wrapped_titles = utils.ListOfDictsAttrWrapper(self.allpages, "title")

        def _pull_from_page(page, condition=lambda title, tag: True):
            # default to empty tuple
            for langlink in page.get("langlinks", ()):
                title = self._title_from_langlink(langlink)
                tag = langlink["lang"]
                if tag not in tags and condition(title, tag):
                    tags.add(tag)
                    titles.add(title)

        # Pull in internal langlinks from any page. This will pull in English page
        # if there is any.
        for page in family_pages:
            _pull_from_page(page, condition=lambda title, tag: lang.is_internal_tag(tag) and title in wrapped_titles)

        # FIXME: still needs some work...
        # Make sure that external langlinks are pulled in only from the English page
        # if there is any. For consistency, pull in also internal langlinks from the
        # English page.
        if "en" in tags:
            title = [title for title in titles if lang.detect_language(title)[1] == "English"][0]
            page = utils.bisect_find(self.allpages, title, index_list=wrapped_titles)
            _pull_from_page(page, condition=lambda title, tag: lang.is_external_tag(tag) or title in wrapped_titles)#, condition=lambda tag: lang.is_external_tag(tag))
        else:
            # Pull in external langlinks from any page. This completes the
            # inclusion in case there is no English page.
            for page in family_pages:
                _pull_from_page(page, condition=lambda title, tag: lang.is_external_tag(tag))

        assert(len(tags) == len(titles))

        return titles, tags

    # TODO: unused method
    def _merge_families(self, families):
        """
        Merges the families based on the "langlinks" property of the pages.
        """
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
#                print("Attempted to merge families with multiple pages of the same language")
#                print("Family", family1)
#                pprint([page["title"] for page in pages1])
#                pprint(langs1)
#                print("Family", family2)
#                pprint([page["title"] for page in pages2])
#                pprint(langs2)
#                input()

        # FIXME: change priority of pulling the interlinks, the current random approach is not good
        for family in list(families.keys()):
            # We need to iterate from copy of the keys because the size of the
            # main dict changes during iteration. Then we need to check if the
            # key is still valid.
            try:
                pages = families[family]
            except KeyError:
                continue

            titles, _ = self._titles_in_family(pages)
            # enumerate titles of possible new families to be merged in
            for title in titles:
                if title not in [page["title"] for page in pages]:
                    if family != title:
                        _merge(family, title)
                        # update the set of titles
                        titles = self._titles_in_family(pages)

    def build_graph(self):
        self.allpages = self._get_allpages()
        self.allpages.sort(key=lambda page: page["title"])
        self.families = self._group_into_families(self.allpages)
#        self._merge_families(self.families)

    @staticmethod
    def _update_interlanguage_links(text, title, family_titles, weak_update=True):
        """
        :param title: title of the page to update (str)
        :param family_titles: titles of the family to appear on the page (set)
        :param weak_update:
            When ``True``, the interlinks present on the page are mixed with those
            suggested by ``family_titles``. This is necessary only when there are
            multiple "intersecting" families, in which case the intersection should
            be preserved and solved manually. This is reported in _merge_families.
        :returns: updated wikicode
        """
        # the page should not have a link to itself
        # FIXME: check tag, not the title!
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
        if weak_update is True:
            magics, cats, interlinks = extract_header_parts(wikicode, interlinks=interlinks)
        else:
            # drop the extracted interlinks
            magics, cats, _ = extract_header_parts(wikicode)
        build_header(wikicode, magics, cats, interlinks)
        return wikicode

    def update_allpages(self):
        self.build_graph()
        # TODO: it should be theoretically possible to determine which pages need
        #       to be changed from the langlink graph and families groups
        # create inverse mapping for fast searching
        family_index = {}
        for family, pages in self.families.items():
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
                    text_old = page["revisions"][0]["*"]
                    timestamp = page["revisions"][0]["timestamp"]

                    # temporarily skip main pages until the behavior switches
                    # (__NOTOC__ etc.) can be parsed by mwparserfromhell
                    if re.search("__NOTOC__|__NOEDITSECTION__", text_old):
                        print("Skipping page '{}' (contains behavior switch(es))".format(title))
                        continue

                    # temporarily skip Beginners' guides until mwparserfromhell (or
                    # maybe just extract_header_parts() function?) is fixed -- content
                    # in <noinclude> tags is not parsed
                    if re.search("<noinclude>", text_old):
                        print("Skipping page '{}' (contains <noinclude>)".format(title))
                        continue

                    # skip unsupported languages
                    if title not in family_index:
                        print("Skipping page '{}' (unsupported language)".format(title))
                        continue

                    print("Processing page '{}'".format(title))

                    family_pages = self.families[family_index[title]]
                    family_titles, family_tags = self._titles_in_family(family_pages)
                    if len(family_titles) == len(family_tags):
                        assert(title in family_titles)
                        text_new = self._update_interlanguage_links(text_old, title, family_titles - {title}, weak_update=False)
                    else:
                        # TODO: unused branch
                        print("warning: multiple pages of the same language in a family:", family_titles)
                        family_titles = set(page["title"] for page in family_pages)
                        assert(title in family_titles)
                        text_new = self._update_interlanguage_links(text_old, title, family_titles - {title}, weak_update=True)

                    if text_old != text_new:
                        print("    pages in family:", sorted(family_titles))
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

    snippet = """
{{Lowercase_title}}
[[en:Main page]]
text
"""

    snippet = """
The [[vi]] editor.
"""

# TODO
    snippet = """
__NOTOC__
[[es:Main page]]
Text of the first paragraph...
"""

#    wikicode = mwparserfromhell.parse(snippet)
#    fix_header(wikicode)
#    print(snippet, end="")
#    print("=" * 42)
#    print(wikicode, end="")
