#! /usr/bin/env python3

import contextlib
import threading

import mwparserfromhell

import ws.ArchWiki.lang as lang
from ws.utils import LazyProperty
from ws.parser_helpers.title import canonicalize
from ws.parser_helpers.wikicode import get_parent_wikicode, get_adjacent_node

__all__ = ["get_edit_summary_tracker", "localize_flag", "CheckerBase"]


# WARNING: using the context manager is not thread-safe
def get_edit_summary_tracker(wikicode, summary_parts):
    @contextlib.contextmanager
    def checker(summary):
        text = str(wikicode)
        try:
            yield
        finally:
            if text != str(wikicode):
                summary_parts.append(summary)
    return checker


def localize_flag(wikicode, node, template_name):
    """
    If a ``node`` in ``wikicode`` is followed by a template with the same base
    name as ``template_name``, this function changes the adjacent template's
    name to ``template_name``.

    :param wikicode: a :py:class:`mwparserfromhell.wikicode.Wikicode` object
    :param node: a :py:class:`mwparserfromhell.nodes.Node` object
    :param str template_name: the name of the template flag, potentially
                              including a language name
    """
    parent = get_parent_wikicode(wikicode, node)
    adjacent = get_adjacent_node(parent, node, ignore_whitespace=True)

    if isinstance(adjacent, mwparserfromhell.nodes.Template):
        adjname = lang.detect_language(str(adjacent.name))[0]
        basename = lang.detect_language(template_name)[0]
        if canonicalize(adjname) == canonicalize(basename):
            adjacent.name = template_name


class CheckerBase:
    def __init__(self, api, db, *, interactive=False, **kwargs):
        self.api = api
        self.db = db
        self.interactive = interactive

        # lock used for synchronizing access to the wikicode AST
        # FIXME: the lock should not be an attribute of the checker, but of the wikicode
        # maybe we can create a wrapper class (e.g. ThreadSafeWikicode) which would transparently synchronize all method calls: https://stackoverflow.com/a/17494777
        # (we would still have to manually lock for wrapper functions and longer parts in the checkers)
        self.lock_wikicode = threading.RLock()

    @LazyProperty
    def _alltemplates(self):
        result = self.api.generator(generator="allpages", gapnamespace=10, gaplimit="max", gapfilterredir="nonredirects")
        return {page["title"].split(":", maxsplit=1)[1] for page in result}

    def get_localized_template(self, template, language="English"):
        assert(canonicalize(template) in self._alltemplates)
        localized = lang.format_title(template, language)
        if canonicalize(localized) in self._alltemplates:
            return localized
        # fall back to English
        return template

    def handle_node(self, src_title, wikicode, node, summary_parts):
        raise NotImplementedError("the handle_node method was not implemented in the derived class")
