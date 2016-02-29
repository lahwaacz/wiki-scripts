#! /usr/bin/env python3

from pprint import pprint

from ws.core import API
import ws.ArchWiki.lang as lang


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

    def run(self):
        graph_parents, graph_subcats, info = self.build_graph()
        roots = ["Category:English"]

        levels = []

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

        def walk(root):
            nodes = graph_subcats.get(root, [])
            for i, title in enumerate(sorted(nodes)):
                levels.append(i)
                yield title, root, levels
                yield from walk(title)
                levels.pop(-1)

        ff = format_plain
        for title in roots:
            ff(title)
            for item in walk(title):
                ff(*item)

if __name__ == "__main__":
    import ws.config
    toc = ws.config.object_from_argparser(TableOfContents, description="Build a presentation of the wiki's table of contents")
    toc.run()
