#! /usr/bin/env python3

from pprint import pprint

from ws.core import API
import ws.ArchWiki.lang as lang


def build_graph(api):
    # `graph_parents` maps category names to the list of their parents
    graph_parents = {}
    # `graph_subcats` maps category names to the list of their subcategories
    graph_subcats = {}
    # a mapping of category names to the corresponding "categoryinfo" dictionary
    info = {}
    for page in api.generator(generator="allpages", gaplimit="max", gapnamespace=14, prop="categories|categoryinfo", cllimit="max", clshow="!hidden", clprop="hidden"):
        if "categories" in page:
            graph_parents.setdefault(page["title"], []).extend([cat["title"] for cat in page["categories"]])
            for cat in page["categories"]:
                graph_subcats.setdefault(cat["title"], []).append(page["title"])
        if "categoryinfo" in page:
            info.setdefault(page["title"], {}).update(page["categoryinfo"])
    return graph_parents, graph_subcats, info

def main(api):
    graph_parents, graph_subcats, info = build_graph(api)
    roots = ["Category:English"]

    levels = []

    def print_info(title, parent=None, levels=None):
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

    def walk(root):
        nodes = graph_subcats.get(root, [])
        for i, title in enumerate(sorted(nodes)):
            levels.append(i)
            print_info(title, root, levels)
            walk(title)
            levels.pop(-1)

    for title in roots:
        print_info(title)
        walk(title)

if __name__ == "__main__":
    import ws.config
    api = ws.config.object_from_argparser(API)
    main(api)
