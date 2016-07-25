#! /usr/bin/env python3

import copy
import logging

import ws.ArchWiki.lang as lang
from ws.parser_helpers.title import Title


logger = logging.getLogger(__name__)

__all__ = ["CategoryGraph"]


# TODO: refactoring: move the generic stuff to ws.utils and add tests

def cmp(left, right):
    if left < right:
        return -1
    elif left > right:
        return 1
    else:
        return 0


class MyIterator(object):
    """
    Wrapper around python generators that allows to explicitly check if the
    generator has been exhausted or not.
    """
    def __init__(self, iterable):
        self._iterable = iter(iterable)
        self._exhausted = False
        self._next_item = None
        self._cache_next_item()

    def _cache_next_item(self):
        try:
            self._next_item = next(self._iterable)
        except StopIteration:
            self._exhausted = True

    def __iter__(self):
        return self

    def __next__(self):
        if self._exhausted:
            raise StopIteration
        # FIXME: workaround for strange behaviour of lists inside tuples -> investigate
        next_item = copy.deepcopy(self._next_item)
        self._cache_next_item()
        return next_item

    def __bool__(self):
        return not self._exhausted


class CategoryGraph:

    def __init__(self, api):
        self.api = api

        # `parents` maps category names to the list of their parents
        self.parents = {}
        # `subcats` maps category names to the list of their subcategories
        self.subcats = {}
        # a mapping of category names to the corresponding "categoryinfo" dictionary
        self.info = {}

        self.update()

    def update(self):
        self.parents.clear()
        self.subcats.clear()
        self.info.clear()

        for page in self.api.generator(generator="allpages", gaplimit="max", gapnamespace=14, prop="categories|categoryinfo", cllimit="max", clshow="!hidden", clprop="hidden"):
            if "categories" in page:
                self.parents.setdefault(page["title"], []).extend([cat["title"] for cat in page["categories"]])
                for cat in page["categories"]:
                    self.subcats.setdefault(cat["title"], []).append(page["title"])
            # empty categories don't have the "categoryinfo" field
            i = self.info.setdefault(page["title"], {"files": 0, "pages": 0, "subcats": 0, "size": 0})
            if "categoryinfo" in page:
                i.update(page["categoryinfo"])

    @staticmethod
    def walk(graph, node, levels=None, visited=None):
        if levels is None:
            levels = []
        if visited is None:
            visited = set()
        children = graph.get(node, [])
        for i, child in enumerate(sorted(children, key=str.lower)):
            if child not in visited:
                levels.append(i)
                visited.add(child)
                yield child, node, levels
                yield from CategoryGraph.walk(graph, child, levels, visited)
                visited.remove(child)
                levels.pop(-1)

    @staticmethod
    def compare_components(graph, left, right):
        def cmp_tuples(left, right):
            if left is None and right is None:
                return 0
            elif left is None:
                return 1
            elif right is None:
                return -1
            return cmp( (-len(left[2]), lang.detect_language(left[0])[0]),
                        (-len(right[2]), lang.detect_language(right[0])[0]) )

        lgen = MyIterator(CategoryGraph.walk(graph, left))
        rgen = MyIterator(CategoryGraph.walk(graph, right))

        try:
            lval = next(lgen)
            rval = next(rgen)
        except StopIteration:
            # both empty, there is nothing to do
            return None, None

        while lgen and rgen:
            while cmp_tuples(lval, rval) < 0:
                yield lval, None
                lval = next(lgen)
            while cmp_tuples(lval, rval) == 0:
                yield lval, rval
                lval = next(lgen)
                rval = next(rgen)
            while cmp_tuples(lval, rval) > 0:
                yield None, rval
                rval = next(rgen)

        while lgen:
            while cmp_tuples(lval, rval) < 0:
                yield lval, None
                lval = next(lgen)
            while cmp_tuples(lval, rval) == 0:
                yield lval, rval
                lval = next(lgen)
                rval = None

        while rgen:
            while cmp_tuples(lval, rval) == 0:
                yield lval, rval
                lval = None
                rval = next(rgen)
            while cmp_tuples(lval, rval) > 0:
                yield None, rval
                rval = next(rgen)

        yield lval, rval

    def create_category(self, category):
        title = Title(self.api, category)
        if title.iwprefix or title.namespace != "Category":
            raise ValueError("Invalid category name: [[{}]]".format(category))
        # normalize name
        category = title.fullpagename

        # skip existing categories
        if category in self.info:
            return

        pure, langname = lang.detect_language(category)
        if langname == lang.get_local_language():
            logger.warning("Cannot automatically create {} category: [[{}]]".format(lang.get_local_language(), category))
            return

        local = lang.format_title(pure, lang.get_local_language())
        if local not in self.info:
            logger.warning("Cannot create category [[{}]]: {} category [[{}]] does not exist.".format(category, lang.get_local_language(), local))
            return

        parents = [lang.format_title(lang.detect_language(p)[0], langname) for p in self.parents[local]]
        content = "\n".join("[[{}]]".format(p) for p in parents)

        self.api.create(title=category, text=content, summary="init wanted category")
        self.update()

        for p in parents:
            self.create_category(p)

    def init_wanted_categories(self):
        for page in self.api.list(list="querypage", qppage="Wantedcategories", qplimit="max"):
            self.create_category(page["title"])
