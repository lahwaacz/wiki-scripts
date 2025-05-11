import contextlib
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, ContextManager, Generator

from mwparserfromhell.nodes import Node, Template
from mwparserfromhell.wikicode import Wikicode

import ws.ArchWiki.lang as lang
from ws.client.api import API
from ws.db.database import Database
from ws.parser_helpers.title import canonicalize
from ws.parser_helpers.wikicode import get_adjacent_node, get_parent_wikicode
from ws.utils import LazyProperty

__all__ = ["get_edit_summary_tracker", "localize_flag", "CheckerBase"]


# WARNING: using the context manager is not thread-safe
def get_edit_summary_tracker(
    wikicode: Wikicode, summary_parts: list[str]
) -> Callable[[str], ContextManager[None]]:
    @contextlib.contextmanager
    def checker(summary: str) -> Generator[None]:
        text = str(wikicode)
        try:
            yield
        finally:
            if text != str(wikicode):
                summary_parts.append(summary)

    return checker


def localize_flag(wikicode: Wikicode, node: Node, template_name: str) -> None:
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

    if isinstance(adjacent, Template):
        adjname = lang.detect_language(str(adjacent.name))[0]
        basename = lang.detect_language(template_name)[0]
        if canonicalize(adjname) == canonicalize(basename):
            # (mwparserfromhell does not have getters and setters next to each other,
            # so mypy thinks the property is read-only)
            adjacent.name = template_name  # type: ignore


class CheckerBase(ABC):
    def __init__(
        self, api: API, db: Database | None = None, *, interactive: bool = False, **kwargs: Any
    ):
        self.api = api
        self.db = db
        self.interactive = interactive

        # lock used for synchronizing access to the wikicode AST
        # FIXME: the lock should not be an attribute of the checker, but of the wikicode
        # maybe we can create a wrapper class (e.g. ThreadSafeWikicode) which would transparently synchronize all method calls: https://stackoverflow.com/a/17494777
        # (we would still have to manually lock for wrapper functions and longer parts in the checkers)
        self.lock_wikicode = threading.RLock()

        # forward all unused arguments to the next parent of the instance
        # (note that although CheckerBase does not have any real parent, it is
        # designed for multiple inheritance and super() selects the next class
        # in the method-resolution-order of the *instance*)
        super().__init__(**kwargs)

    @LazyProperty
    def _alltemplates(self) -> set[str]:
        result = self.api.generator(
            generator="allpages",
            gapnamespace=10,
            gaplimit="max",
            gapfilterredir="nonredirects",
        )
        return {page["title"].split(":", maxsplit=1)[1] for page in result}

    def get_localized_template(self, template: str, language: str = "English") -> str:
        assert canonicalize(template) in self._alltemplates
        localized = lang.format_title(template, language)
        if canonicalize(localized) in self._alltemplates:
            return localized
        # fall back to English
        return template

    @abstractmethod
    def handle_node(
        self, src_title: str, wikicode: Wikicode, node: Node, summary_parts: list[str]
    ) -> None:
        raise NotImplementedError(
            "the handle_node method was not implemented in the derived class"
        )
