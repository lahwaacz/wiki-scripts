#! /usr/bin/env python3

from pprint import pprint
import copy

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
        roots = ["Category:English"]

        def format_plain(title, parent=None, levels=None):
            if levels is None:
                # root
                print("{} ({})".format(title, info[title]["pages"]))
            else:
                # indent
                output = " " * (len(levels) - 1) * 4
                # level
                output += ".".join(str(x + 1) for x in levels)
                # title, number of subpages
                output += " {} ({})".format(title, info[title]["pages"])
                # "also in" suffix
                parents = set(graph_parents[title]) - {parent}
                if parents:
                    output += " (also in: {})".format(", ".join(sorted(parents)))
                print(output)

        def format_html(title, parent=None, levels=None):
            pass

        ff = format_plain
#        for title in roots:
#            ff(title)
#            for item in self.walk(graph_subcats, title):
#                ff(*item)

        print("====")
        for title in roots:
            for a, b in self.compare_trees(graph_subcats, title, "Category:Magyar"):
                if a:
                    ff(*a)
                else:
                    print(a)
                if b:
                    ff(*b)
                else:
                    print(b)
                print("----")

if __name__ == "__main__":
    import ws.config
    toc = ws.config.object_from_argparser(TableOfContents, description="Build a presentation of the wiki's table of contents")
    toc.run()
