#! /usr/bin/env python3

import mwparserfromhell

from . import lang
from ws.parser_helpers.wikicode import remove_and_squash, get_parent_wikicode
from ws.parser_helpers.title import canonicalize

__all__ = ["HeaderError", "get_header_parts", "build_header", "fix_header"]

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
        _pure, _ = lang.detect_language(str(template.name))
        if canonicalize(template.name) == "Lowercase title" or _prefix(template.name) == "DISPLAYTITLE" or _pure in ["Template", "Template:Template"]:
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
    # first strip blank lines if there is some text
    if len(wikicode.nodes) > 0:
        node = parent.get(0)
        if isinstance(node, mwparserfromhell.nodes.text.Text):
            if node.value:
                firstline = node.value.splitlines(keepends=True)[0]
                while firstline.strip() == "":
                    node.value = node.value.replace(firstline, "", 1)
                    if node.value == "":
                        break
                    firstline = node.value.splitlines(keepends=True)[0]

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
