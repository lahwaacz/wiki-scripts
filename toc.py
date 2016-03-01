#! /usr/bin/env python3

from pprint import pprint
import copy
from collections import Iterable

from ws.core import API
import ws.ArchWiki.lang as lang


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


class TableOfContents:

    def __init__(self, api):
        self.api = api

    @staticmethod
    def set_argparser(argparser):
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)

    @classmethod
    def from_argparser(klass, args, api=None):
        if api is None:
            api = API.from_argparser(args)
        return klass(api)

    def build_graph(self):
        # `graph_parents` maps category names to the list of their parents
        graph_parents = {}
        # `graph_subcats` maps category names to the list of their subcategories
        graph_subcats = {}
        # a mapping of category names to the corresponding "categoryinfo" dictionary
        info = {}
        for page in self.api.generator(generator="allpages", gaplimit="max", gapnamespace=14, prop="categories|categoryinfo", cllimit="max", clshow="!hidden", clprop="hidden"):
            if "categories" in page:
                graph_parents.setdefault(page["title"], []).extend([cat["title"] for cat in page["categories"]])
                for cat in page["categories"]:
                    graph_subcats.setdefault(cat["title"], []).append(page["title"])
            if "categoryinfo" in page:
                info.setdefault(page["title"], {}).update(page["categoryinfo"])
        return graph_parents, graph_subcats, info

    # TODO: works only for acyclic graphs (in general it is necessary to build a list of visited nodes to avoid infinite loop)
    @staticmethod
    def walk(graph, node, levels=None):
        if levels is None:
            levels = []
        children = graph.get(node, [])
        for i, child in enumerate(sorted(children, key=str.lower)):
            levels.append(i)
            yield child, node, levels
            if child != node:
                yield from TableOfContents.walk(graph, child, levels)
            levels.pop(-1)

    @staticmethod
    def compare_trees(graph, left, right):
        def cmp_tuples(left, right):
            if left is None and right is None:
                return 0
            elif left is None:
                return 1
            elif right is None:
                return -1
            return cmp( (-len(left[2]), lang.detect_language(left[0])[0]),
                        (-len(right[2]), lang.detect_language(right[0])[0]) )

        lgen = MyIterator(TableOfContents.walk(graph, left))
        rgen = MyIterator(TableOfContents.walk(graph, right))

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

    def run(self):
        graph_parents, graph_subcats, info = self.build_graph()
        roots = [
            "Category:English",
            ("Category:English", "Category:Česky"),
        ]

        def format_html(title, parent=None, levels=None):
            pass

        for root in roots:
            print("====")
            ff = PlainFormatter(graph_parents, info)
            ff.format_root(root)
            if isinstance(root, str):
                for item in self.walk(graph_subcats, root):
                    ff.format_row(item)
            elif isinstance(root, Iterable):
                for result in self.compare_trees(graph_subcats, *root):
                    ff.format_row(*result)
            print(ff)


class BaseFormatter:
    def __init__(self, parents, info):
        self.parents = parents
        self.info = info

    def format_also_in(self, parents, language):
        # TODO: localize
        return " (also in: {})".format(", ".join(sorted(parents)))

    def localized_category(self, category):
        # TODO: search in a dictionary
        return category


class PlainFormatter(BaseFormatter):

    column_width = 80

    def __init__(self, parents, info):
        super().__init__(parents, info)
        self.text = ""

    def format_root(self, title):
        if isinstance(title, str):
            self.text += "{} ({})\n".format(title, self.info[title]["pages"])
        elif isinstance(title, Iterable):
            # title is a tuple of titles
            for t in title:
                self.format_root(t)
            self.text += "----\n"

    def format_cell(self, title, parent, levels):
        language = lang.detect_language(title)[1]
        # indent
        output = " " * (len(levels) - 1) * 4
        # level
        output += ".".join(str(x + 1) for x in levels)
        # title, number of subpages
        output += " {} ({})".format(title, self.info[title]["pages"])
        # "also in" suffix
        parents = set(self.parents[title]) - {parent}
        if parents:
            output += self.format_also_in(parents, language)
        return output

    def format_row(self, *columns):
        for col in columns:
            if isinstance(col, Iterable) and not isinstance(col, str):
                self.text += self.format_cell(*col) + "\n"
            else:
                self.text += str(col) + "\n"
        if len(columns) > 1:
            self.text += "----\n"

    def __str__(self):
        return self.text

if __name__ == "__main__":
    import ws.config
    toc = ws.config.object_from_argparser(TableOfContents, description="Build a presentation of the wiki's table of contents")
    toc.run()
