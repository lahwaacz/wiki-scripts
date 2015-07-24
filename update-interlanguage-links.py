#! /usr/bin/env python3

# TODO:
#   take the final title from "displaytitle" property (available from API) (would be necessary to check if it is valid)

import os.path
import itertools
import re

import mwparserfromhell

from ws.core import API
from ws.interactive import *
from ws.diff import diff_highlighted
import ws.ArchWiki.lang as lang
import ws.utils as utils
from ws.parser_helpers import canonicalize, remove_and_squash, get_parent_wikicode

class HeaderError(Exception):
    pass

def get_header_parts(wikicode, magics=None, cats=None, langlinks=None, remove_from_parent=False):
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

    Only 1-3 are safe to be updated automatically. This function will extract
    the header parts from the wikicode and return them as tuple
    ``(parent, magics, cats, langlinks)``, where ``parent`` is an instance of
    :py:class:`mwparserfromhell.wikicode.Wikicode` containing all extracted
    elements. It is assumed that all header elements are children of the same
    parent node, otherwise :py:exc:`HeaderError` is raised.

    If ``remove_from_parent`` is ``True``, the extracted header elements  are
    also removed from the parent node and :py:func:`build_header` should be
    called to insert them back.

    The parameters ``magics``, ``cats`` and ``langlinks`` can be lists of
    objects (either string, wikicode or node) to be added to the header if not
    already present. These deduplication rules are applied:
      - supplied magic words take precedence over those present in wikicode
      - category links are considered duplicate when they point to the same
        category (e.g. [[Category:Foo]] is equivalent to [[category:foo]])
      - interlanguage links are considered duplicate when they have the same
        language tag (i.e. there can be only one interlanguage link for each
        language)

    The lists of magics and langlinks are sorted, the order of catlinks is
    preserved.
    """
    if magics is None:
        magics = []
    if cats is None:
        cats = []
    if langlinks is None:
        langlinks = []

    # make sure that we work with `Wikicode` objects
    magics = [mwparserfromhell.utils.parse_anything(item) for item in magics]
    cats = [mwparserfromhell.utils.parse_anything(item) for item in cats]
    langlinks = [mwparserfromhell.utils.parse_anything(item) for item in langlinks]

    parent = None

    def _prefix(title):
        if ":" not in title:
            return ""
        return title.split(":", 1)[0].strip()

    # check the parent wikicode object and remove node from it
    def _remove(node):
        nonlocal parent
        if parent is None:
            parent = get_parent_wikicode(wikicode, node)
        else:
            p = get_parent_wikicode(wikicode, node)
            if parent is not p:
                raise HeaderError
        if remove_from_parent is True:
            remove_and_squash(parent, node)

    def _add_to_magics(template):
        _remove(template)
        if not any(magic.get(0).name.matches(template.name) for magic in magics):
            magics.append(mwparserfromhell.utils.parse_anything(template))

    def _add_to_cats(catlink):
        # TODO: non-duplicate "typos" are still ignored -- is this important enough to handle it?
        if not any(cat.get(0).title.matches(catlink.title) for cat in cats):
            # only remove from wikicode if we actually append to cats (duplicate category
            # links are considered typos, e.g. [[Category:foo]] instead of [[:Category:foo]],
            # which are quite common)
            _remove(catlink)
            cats.append(mwparserfromhell.utils.parse_anything(catlink))

    def _add_to_langlinks(langlink):
        # always remove langlinks to handle renaming of pages
        # (typos such as [[en:Main page]] in text are quite rare)
        _remove(langlink)
        if not any(_prefix(link.get(0).title).lower() == _prefix(langlink.title).lower() for link in langlinks):
            # not all tags work as interlanguage links
            if lang.is_interlanguage_tag(_prefix(langlink.title).lower()):
                langlinks.append(mwparserfromhell.utils.parse_anything(langlink))

    # count extracted header elements
    _extracted_count = 0

    for template in wikicode.filter_templates():
        # TODO: temporary workaround for a bug in parser:
        #       https://github.com/earwig/mwparserfromhell/issues/111
        if not template.name:
            continue
        if canonicalize(template.name) in ["Lowercase title", "Template", "Template:Template"] or _prefix(template.name) == "DISPLAYTITLE":
            _add_to_magics(template)
            _extracted_count += 1

    for link in wikicode.filter_wikilinks():
        prefix = _prefix(link.title).lower()
        if prefix == "category":
            _add_to_cats(link)
            _extracted_count += 1
        elif prefix in lang.get_language_tags():
            _add_to_langlinks(link)
            _extracted_count += 1

    magics.sort()
    langlinks.sort()

    if parent is None:
        if _extracted_count > 0:
            # this indicates parser error (e.g. unclosed <div> tags)
            raise HeaderError("no parent Wikicode object")
        else:
            # for pages without any header elements
            parent = wikicode

    return parent, magics, cats, langlinks

def build_header(wikicode, parent, magics, cats, langlinks):
    # First strip blank lines if there is some text. Note that there can be multiple
    # succesive Text nodes as the result of removing header elements.
    i = 0
    while i < len(parent.nodes):
        node = parent.get(i)
        if isinstance(node, mwparserfromhell.nodes.text.Text):
            if node.value:
                firstline = node.value.splitlines(keepends=True)[0]
                while firstline.strip() == "":
                    node.value = node.value.replace(firstline, "", 1)
                    if node.value == "":
                        break
                    firstline = node.value.splitlines(keepends=True)[0]
                # not an empty string after stripping, don't process any
                # following Text nodes
                if node.value:
                    break
        else:
            break
        i += 1

    count = 0
    # If the parent is not the top-level wikicode object (i.e. nested wikicode inside
    # some node, such as <noinclude>), starting with newline does not produce the
    # infamous gap in the HTML and the wikicode looks better
    # NOTE: not tested with different nodes than <noinclude>
    if parent is not wikicode:
        parent.insert(count, "\n")
        count += 1
    for item in magics + cats + langlinks:
        parent.insert(count, item)
        parent.insert(count + 1, "\n")
        count += 2

def fix_header(wikicode):
    parent, magics, cats, langlinks = get_header_parts(wikicode, remove_from_parent=True)
    build_header(wikicode, parent, magics, cats, langlinks)


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
        3.1 Determine the family of the page.
        3.2 Assemble a set of pages in the family. This is done by first including
            the pages in the group from step 2., then pulling any internal langlinks
            from the pages in the set (in unspecified order), and finally based on
            the presence of an English page in the family:
              - If there is an English page directly in the group from step 2. or if
                other pages link to an English page whose group can be merged with
                the current group without causing a conflict, its external langlinks
                are pulled in. As a result, external langlinks removed from the
                English page are assumed to be invalid and removed also from other
                pages in the family. For consistency, also internal langlinks are
                pulled from the English page.
              - If the pulling from an English page was not done, external langlinks
                are pulled from the other pages (in unspecified order), which
                completes the previous inclusion of internal langlinks.
        3.3 Check if it is necessary to update the page by comparing the new set of
            langlinks for a page (i.e. ``family.titles - {title}``) with the old set
            obtained from the wiki's API. If an update is needed:
              - Fetch content of the page.
              - Update the langlinks of the page.
              - If there is a difference, save the page.
    """

    namespaces = [0, 4, 10, 12, 14]
    edit_summary = "update interlanguage links (https://github.com/lahwaacz/wiki-scripts/blob/master/update-interlanguage-links.py)"

    def __init__(self, api):
        self.api = api
        self.redirects = self.api.redirects_map()

        self.limit = 500 if "apihighlimits" in self.api.user_rights() else 50

        self.allpages = None
        self.wrapped_titles = None
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
                # of the information, hence the utils.dmerge
                try:
                    db_page = utils.bisect_find(allpages, page["title"], index_list=wrapped_titles)
                    utils.dmerge(page, db_page)
                except IndexError:
                    utils.bisect_insert_or_replace(allpages, page["title"], data_element=page, index_list=wrapped_titles)
        return allpages

    @staticmethod
    def _group_into_families(pages, case_sensitive=False):
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

        if case_sensitive is True:
            _family_key = lambda page: lang.detect_language(page["title"])[0]
        else:
            _family_key = lambda page: lang.detect_language(page["title"])[0].lower()
        pages.sort(key=_family_key)
        families_groups = itertools.groupby(_valid_interlanguage_pages(pages), key=_family_key)

        families = {}
        for family, pages in families_groups:
            pages = list(pages)
            tags = set(lang.tag_for_langname(lang.detect_language(page["title"])[1]) for page in pages)
            if len(tags) == len(pages):
                families[family] = pages
            elif case_sensitive is False:
                # sometimes case-insensitive matching is not enough, e.g. [[fish]] is
                # not [[FiSH]] (and neither is redirect)
                families.update(Interlanguage._group_into_families(pages, case_sensitive=True))
            else:
                # this should never happen
                raise Exception
        return families

    @staticmethod
    # check if interlanguage links are supported for the language of the given title
    def _is_valid_interlanguage(full_title):
        return lang.is_interlanguage_tag(lang.tag_for_langname(lang.detect_language(full_title)[1]))

    # check if given (tag, title) form a valid internal langlink
    def _is_valid_internal(self, tag, title):
        if not lang.is_internal_tag(tag):
            return False
        if tag == "en":
            full_title = title
        else:
            full_title = "{} ({})".format(title, lang.langname_for_tag(tag))
        return full_title in self.wrapped_titles

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

    def _titles_in_family(self, master_title):
        """
        Get the titles in the family corresponding to ``title``.

        :returns: a ``(titles, tags)`` tuple, where ``titles`` is the set of titles
                  in the family (including ``title``) and ``tags`` is the set of
                  corresponding language tags
        """
        family = self.family_index[master_title]
        family_pages = self.families[family]
        # we don't need the full title any more
        master_title, master_lang = lang.detect_language(master_title)
        master_tag = lang.tag_for_langname(master_lang)

        tags = []
        titles = []

        # populate titles/tags with the already present pages
        for page in family_pages:
            title, langname = lang.detect_language(page["title"])
            tag = lang.tag_for_langname(langname)
            if tag not in tags:
                tags.append(tag)
                titles.append(title)
        had_english_early = "en" in tags

        def _pull_from_page(page, condition=lambda tag, title: True):
            # default to empty tuple
            for langlink in page.get("langlinks", ()):
                tag = langlink["lang"]
                # conversion back and forth is necessary to resolve redirect
                full_title = self._title_from_langlink(langlink)
                title, langname = lang.detect_language(full_title)
                # TODO: check if the resulting tag is equal to the original?
#                tag = lang.tag_for_langname(langname)
                if tag not in tags and condition(tag, title):
                    tags.append(tag)
                    titles.append(title)

        # Pull in internal langlinks from any page. This will pull in English page
        # if there is any.
        for page in family_pages:
            _pull_from_page(page, condition=lambda tag, title: self._is_valid_internal(tag, title))

        # Make sure that external langlinks are pulled in only from the English page
        # when appropriate. For consistency, pull in also internal langlinks from the
        # English page.
        _pulled_from_english = False
        if "en" in tags:
            en_title = titles[tags.index("en")]
            en_page = utils.bisect_find(self.allpages, en_title, index_list=self.wrapped_titles)
            # If the English page is present from the beginning, pull its langlinks.
            # This will take priority over other pages in the family.
            if master_tag == "en" or had_english_early:
                _pull_from_page(en_page, condition=lambda tag, title: lang.is_external_tag(tag) or self._is_valid_internal(tag, title))
                _pulled_from_english = True
            else:
                # Otherwise check if the family of the English page is the same as
                # this one or if it does not contain master_tag. This will effectively
                # merge the families.
                en_tags, en_titles = self._titles_in_family(en_title)
                if master_title in en_titles or master_tag not in en_tags:
                    _pull_from_page(en_page, condition=lambda tag, title: lang.is_external_tag(tag) or self._is_valid_internal(tag, title))
                    _pulled_from_english = True

        if not _pulled_from_english:
            # Pull in external langlinks from any page. This completes the
            # inclusion in case pulling from English page was not done.
            for page in family_pages:
                _pull_from_page(page, condition=lambda tag, title: lang.is_external_tag(tag))

        assert(master_tag in tags)
        assert(master_title in titles)
        assert(len(tags) == len(titles))

        return tags, titles

    def _get_langlinks(self, full_title):
        """
        Uses :py:meth:`self._titles_in_family` to get the titles of all pages in
        the family, removes the link to the passed title and sorts the list by
        the language subtag.

        :returns: a list of ``(tag, title)`` tuples
        """
        # get all titles in the family
        tags, titles = self._titles_in_family(full_title)
        langlinks = set(zip(tags, titles))
        # remove title of the page to be updated
        title, langname = lang.detect_language(full_title)
        tag = lang.tag_for_langname(langname)
        langlinks.remove((tag, title))
        # transform to list, sort by the language tag
        langlinks = sorted(langlinks, key=lambda t: t[0])
        return langlinks

    def build_graph(self):
        self.allpages = self._get_allpages()
        self.wrapped_titles = utils.ListOfDictsAttrWrapper(self.allpages, "title")
        self.families = self._group_into_families(self.allpages)
        # sort again, this time by title (self._group_into_families sorted it by
        # the family key)
        self.allpages.sort(key=lambda page: page["title"])

        # create inverse mapping for fast searching
        self.family_index = {}
        for family, pages in self.families.items():
            for page in pages:
                self.family_index[page["title"]] = family

    @staticmethod
    def _update_interlanguage_links(page, langlinks, weak_update=True):
        """
        :param page: a dictionary with page properties obtained from the wiki API.
                     Must contain the content under the ``revisions`` key.
        :param langlinks: a sorted list of ``(tag, title)`` tuples as obtained
                          from :py:meth:`self._get_langlinks`
        :param weak_update:
            When ``True``, the langlinks present on the page are mixed with those
            suggested by ``family_titles``. This is necessary only when there are
            multiple "intersecting" families, in which case the intersection should
            be preserved and solved manually. This is reported in _merge_families.
        :returns: updated wikicode
        """
        title = page["title"]
        text = page["revisions"][0]["*"]

        # temporarily skip main pages until the behavior switches
        # (__NOTOC__ etc.) can be parsed by mwparserfromhell
        if re.search("__NOTOC__|__NOEDITSECTION__", text):
            print("Skipping page '{}' (contains behavior switch(es))".format(title))
            return text

        # format langlinks, in the prefix form
        # (e.g. "cs:Some title" for title="Some title" and tag="cs")
        langlinks = ["[[{}:{}]]".format(tag, title) for tag, title in langlinks]

        print("Parsing '{}'...".format(title))
        wikicode = mwparserfromhell.parse(text)
        if weak_update is True:
            parent, magics, cats, langlinks = get_header_parts(wikicode, langlinks=langlinks, remove_from_parent=True)
        else:
            # drop the extracted langlinks
            parent, magics, cats, _ = get_header_parts(wikicode, remove_from_parent=True)
        build_header(wikicode, parent, magics, cats, langlinks)
        return wikicode

    @staticmethod
    def _needs_update(page, langlinks_new):
        langlinks_old = []
        try:
            for langlink in page["langlinks"]:
                langlinks_old.append((langlink["lang"], langlink["*"]))
        except KeyError:
            pass
        return set(langlinks_new) != set(langlinks_old)

    def update_allpages(self):
        self.build_graph()

        def _updates_gen(pages_gen):
            for page in pages_gen:
                title = page["title"]
                # unsupported languages need to be skipped now
                if not self._is_valid_interlanguage(title):
                    print("Skipping page '{}' (unsupported language)".format(title))
                    continue
                langlinks = self._get_langlinks(title)
                if self._needs_update(page, langlinks):
                    yield page, langlinks
                else:
                    print("Page '{}' is up to date".format(title))

        for chunk in utils.iter_chunks(_updates_gen(self.allpages), self.limit):
            pages_props, pages_langlinks = zip(*list(chunk))
            pageids = "|".join(str(page["pageid"]) for page in pages_props)
            result = self.api.call(action="query", pageids=pageids, prop="revisions", rvprop="content|timestamp")
            pages = result["pages"]

            for page, langlinks in zip(pages_props, pages_langlinks):
                # substitute the dictionary with langlinks with the dictionary with content
                page = pages[str(page["pageid"])]

                timestamp = page["revisions"][0]["timestamp"]
                text_old = page["revisions"][0]["*"]
                try:
                    text_new = self._update_interlanguage_links(page, langlinks, weak_update=False)
                except HeaderError:
                    print("Error: failed to extract header elements. Please investigate.")
                    continue

                if text_old != text_new:
                    edit_interactive(api, page["pageid"], text_old, text_new, timestamp, self.edit_summary, bot="")
#                    self.api.edit(page["pageid"], text_new, timestamp, self.edit_summary, bot="")
#                    print(diff_highlighted(text_old, text_new))
#                    input()


if __name__ == "__main__":
    api_url = "https://wiki.archlinux.org/api.php"
    cookie_path = os.path.expanduser("~/.cache/ArchWiki.bot.cookie")

    api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

    il = Interlanguage(api)
    il.update_allpages()

    snippet = """
__TOC__

Some text with [[it:langlinks]] inside.

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
