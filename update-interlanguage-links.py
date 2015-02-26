#! /usr/bin/env python3

import os.path
import itertools

import mwparserfromhell

from MediaWiki import API, diff_highlighted
from MediaWiki.exceptions import *
from MediaWiki.interactive import *
from MediaWiki.diff import diff_highlighted
from ArchWiki.lang import detect_language, tag_for_langname, get_language_tags

def get_titles_in_namespace(ns):
    return [page["title"] for page in api.generator(generator="allpages", gapfilterredir="nonredirects", gapnamespace=ns, gaplimit="max")]

def group_titles_by_families(titles):
    """
    Takes list of page titles, returns an iterator (itertools object) yielding
    a tuple of 2 elements: `family_key` and `family_iter`, where `family_key`
    is the base title without the language suffix (i.e. "Some title" for
    "Some title (Česky)") and `family_iter` is an iterator yielding the titles
    of pages that belong to the family (have the same `family_key`).
    """
    _family_key = lambda title: detect_language(title)[0]
    titles = sorted(titles, key=_family_key)
    families = itertools.groupby(titles, key=_family_key)
    return families

# TODO: write some tests
# TODO: refactoring (move to the same module as get_parent_wikicode to avoid __import__)
def remove_and_squash(wikicode, obj):
    """
    Remove `obj` from `wikicode` and fix whitespace in the place it was removed from.
    """
    get_parent_wikicode = __import__("update-package-templates").get_parent_wikicode
    parent = get_parent_wikicode(wikicode, obj)
    index = parent.index(obj)
    parent.remove(obj)

    def _get_text(index):
        try:
            node = parent.get(index)
            if not isinstance(node, mwparserfromhell.nodes.text.Text):
                return None
            return node
        except IndexError:
            return None

    prev = _get_text(index - 1)
    next_ = _get_text(index)

    if prev is None and next_ is not None:
        if next_.startswith(" "):
            parent.replace(next_, next_.lstrip(" "))
        elif next_.startswith("\n"):
            parent.replace(next_, next_.lstrip("\n"))
    elif prev is not None and next_ is None:
        if prev.endswith(" "):
            parent.replace(prev, prev.rstrip(" "))
        elif prev.endswith("\n"):
            parent.replace(prev, prev.rstrip("\n"))
    elif prev is not None and next_ is not None:
        if prev.endswith(" ") and next_.startswith(" "):
            parent.replace(prev, prev.rstrip(" "))
            parent.replace(next_, " " + next_.lstrip(" "))
        elif prev.endswith("\n") and next_.startswith("\n"):
            if not prev[:-1].endswith("\n") and not next_[1:].startswith("\n"):
                parent.replace(prev, prev.rstrip("\n"))
            parent.replace(next_, next_.replace("\n", "", 1))
        elif prev.endswith("\n"):
            parent.replace(next_, next_.lstrip(" "))
        elif next_.startswith("\n"):
            parent.replace(prev, prev.rstrip(" "))

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
        return title.split(":", 1)[0]

    def _add_to_magics(template):
        remove_and_squash(wikicode, template)
        if not any(magic.get(0).name.matches(template.name) for magic in magics):
            magics.append(mwparserfromhell.utils.parse_anything(template))

    def _add_to_cats(catlink):
        # TODO: top-level "typos" are still ignored -- is this important enough to handle it?
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
        if not any(_prefix(link.get(0).title) == _prefix(interlink.title) for link in interlinks):
            interlinks.append(mwparserfromhell.utils.parse_anything(interlink))

    # all of magic words, catlinks and interlinks have effect even when nested
    # in other nodes, but let's ignore this case for now
    for template in wikicode.filter_templates(recursive=False):
        if template.name.matches("Lowercase title") or _prefix(template.name) == "DISPLAYTITLE":
            _add_to_magics(template)

    for link in wikicode.filter_wikilinks(recursive=False):
        prefix = _prefix(link.title)
        if prefix.lower() == "category":
            _add_to_cats(link)
        elif prefix in get_language_tags():
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

def update_interlanguage_links(text, title, family_titles):
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
        pure, lang = detect_language(title)
        tag = tag_for_langname(lang)
        return "[[{}:{}]]".format(tag, pure)

    interlinks = sorted(_transform_title(title) for title in family_titles)

    wikicode = mwparserfromhell.parse(text)
    magics, cats, interlinks = extract_header_parts(wikicode, interlinks=interlinks)
    # TODO: check if the interlinks are valid, handle redirects etc.
    build_header(wikicode, magics, cats, interlinks)
    return wikicode

def update_page(title, family_titles):
    result = api.call(action="query", prop="revisions", rvprop="content|timestamp", titles=title)
    page = list(result["pages"].values())[0]
    text_old = page["revisions"][0]["*"]
    timestamp = page["revisions"][0]["timestamp"]

    text_new = update_interlanguage_links(text_old, title, family_titles)

    if text_old != text_new:
#        edit_interactive(api, page["pageid"], text_old, text_new, timestamp, "updated interlanguage links", bot="")
        print(diff_highlighted(text_old, text_new))
        input()

# TODO: def update_allpages
# TODO: fix headers with separate edit summary before any interlanguage links synchronizing !!!

if __name__ == "__main__":
#    api_url = "https://wiki.archlinux.org/api.php"
#    cookie_path = os.path.expanduser("~/.cache/ArchWiki.bot.cookie")

#    api = API(api_url, cookie_file=cookie_path, ssl_verify=True)

#    titles = get_titles_in_namespace(0)
#    families = group_titles_by_families(titles)
#    for family, titles in families:
#        titles = set(titles)
#        print(family)
#        print("   ", titles)
#        for title in titles:
#            update_page(title, titles - {title})


    snippet = """
__TOC__

Some text with [[it:interlink]] inside.

[[Category:foo]]
This [[category:foo|catlink]] is a typo.
[[en:bar]]

Some other text
[[category:bar]]
[[cs:some page]]

{{DISPLAYTITLE:lowercase title}}
{{Lowercase title}}
"""
    wikicode = mwparserfromhell.parse(snippet)
    fix_header(wikicode)
    print(snippet, end="")
    print("=" * 42)
    print(wikicode, end="")
