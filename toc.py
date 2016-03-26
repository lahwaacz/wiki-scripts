#! /usr/bin/env python3

import copy
from collections import Iterable
import datetime
import logging

import mwparserfromhell

from ws.core import API
from ws.interactive import require_login
from ws.parser_helpers.title import canonicalize, Title
import ws.ArchWiki.lang as lang
from ws.utils import parse_date


logger = logging.getLogger(__name__)


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


class LowercaseDict(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        return super().__getitem__(key.lower())

    def __setitem__(self, key, value):
        super().__setitem__(key.lower(), value)

    def __contains__(self, key):
        return super().__contains__(key.lower())

    def get(self, key, default=None):
        return super().get(key.lower(), default)

    def setdefault(self, key, default=None):
        return super().setdefault(key.lower(), default)

    def update(self, other):
        for key, value in other.items():
            super().__setitem__(key.lower(), value)

    def pop(self, key, default=None):
        return super().pop(key.lower(), default)


class CategoryGraph:

    def __init__(self, api):
        self.api = api

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
            # empty categories don't have the "categoryinfo" field
            i = info.setdefault(page["title"], {"files": 0, "pages": 0, "subcats": 0, "size": 0})
            if "categoryinfo" in page:
                i.update(page["categoryinfo"])
        return graph_parents, graph_subcats, info

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


class BaseFormatter:
    def __init__(self, parents, info, category_names, alsoin=None):
        self.parents = parents
        self.info = info
        self.category_names = category_names
        if alsoin is None:
            alsoin = {}
        alsoin.setdefault("en", "also in")
        self.alsoin = alsoin

    def format_also_in(self, parents, lang_tag):
        alsoin = self.alsoin.get(lang_tag, self.alsoin["en"])
        return " ({alsoin} {categories})".format(alsoin=alsoin, categories=", ".join(sorted(parents)))

    def localize(self, category):
        default = lang.detect_language(category.split(":", 1)[1])[0]
        return self.category_names.get(category, default)


class PlainFormatter(BaseFormatter):

    def __init__(self, parents, info, category_names, alsoin=None):
        super().__init__(parents, info, category_names, alsoin)
        self.text = ""

    def format_root(self, title):
        if isinstance(title, str):
            self.text += "{} ({})\n".format(title, self.info[title]["pages"])
        elif isinstance(title, Iterable):
            # title is a tuple of titles
            for t in title:
                self.format_root(t)
            if len(title) > 1:
                self.text += "----\n"

    def format_cell(self, title, parent, levels):
        lang_tag = lang.tag_for_langname(lang.detect_language(title)[1])
        # indent
        output = " " * len(levels) * 4
        # level
        output += ".".join(str(x + 1) for x in levels)
        # title, number of subpages
        output += " {} ({})".format(self.localize(title), self.info[title]["pages"])
        # "also in" suffix
        parents = set(self.parents[title]) - {parent}
        if parents:
            parents = [self.localize(cat) for cat in parents]
            output += self.format_also_in(parents, lang_tag)
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


class MediaWikiFormatter(BaseFormatter):

    cell_format = "<span style=\"margin-left:{margin:.3}em;\"><small>{levels}</small> {catlink} <small>{info}</small></span>"

    def __init__(self, parents, info, category_names, alsoin=None, include_opening_closing_tokens=True):
        super().__init__(parents, info, category_names, alsoin)
        self.include_opening_closing_tokens = include_opening_closing_tokens
        self.text = ""

    def catlink(self, title):
        catlink = "[[:{}|{}]]".format(title, self.localize(title))
        if lang.is_rtl_language(lang.detect_language(title)[1]):
            catlink += "&lrm;"
        return catlink

    def format_root(self, title):
        if isinstance(title, str):
            self.text += "| {} <small>({})</small>\n".format(self.catlink(title), self.info[title]["pages"])
            self.text += "|-\n"
        elif isinstance(title, Iterable):
            # title is a tuple of titles
            for t in title:
                self.text += "| {} <small>({})</small>\n".format(self.catlink(t), self.info[t]["pages"])
            self.text += "|-\n"

    def format_cell(self, title, parent, levels):
        lang_tag = lang.tag_for_langname(lang.detect_language(title)[1])
        margin = 1.6 * len(levels)
        lev = ".".join(str(x + 1) for x in levels) + "."
        info = "({})".format(self.info[title]["pages"])
        # "also in" suffix
        parents = set(self.parents[title]) - {parent}
        if parents:
            parents = [self.catlink(cat) for cat in parents]
            info += self.format_also_in(parents, lang_tag)
        return self.cell_format.format(margin=margin, levels=lev, catlink=self.catlink(title), info=info)

    def format_row(self, *columns):
        for col in columns:
            if isinstance(col, Iterable) and not isinstance(col, str):
                self.text += "| " + self.format_cell(*col) + "\n"
            elif col:
                self.text += "| " + str(col) + "\n"
            else:
                self.text += "|\n"
        self.text += "|-\n"

    def __str__(self):
        if self.include_opening_closing_tokens is True:
            out = "{|\n" + self.text
            if out.endswith("\n"):
                out += "|}"
            else:
                out += "\n|}"
            return out
        return self.text


class TableOfContents:

    def __init__(self, api, cliargs):
        self.api = api
        self.cliargs = cliargs

        if self.cliargs.save is False and self.cliargs.print is False:
            self.cliargs.print = True

        if len(self.cliargs.toc_languages) == 1 and self.cliargs.toc_languages[0] == "all":
            self.cliargs.toc_languages = lang.get_internal_tags()
        # strip "(Language)" suffix
        self.cliargs.toc_page = lang.detect_language(canonicalize(self.cliargs.toc_page))[0]

        # detect page titles
        self.titles = []
        for ln in sorted(self.cliargs.toc_languages):
            if ln == lang.tag_for_langname(lang.get_local_language()):
                self.titles.append(self.cliargs.toc_page)
            else:
                self.titles.append("{} ({})".format(self.cliargs.toc_page, lang.langname_for_tag(ln)))

    @staticmethod
    def set_argparser(argparser):
        import ws.config

        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)

        output = argparser.add_argument_group(title="output mode")
        _g = output.add_mutually_exclusive_group()
        # TODO: maybe leave only the short option to forbid configurability in config file
        _g.add_argument("-s", "--save", action="store_true",
                help="try to save the page (requires being logged in)")
        _g.add_argument("-p", "--print", action="store_true",
                help="print the updated text in the standard output (this is the default output method)")

        group = argparser.add_argument_group(title="script parameters")
        group.add_argument("-a", "--anonymous", action="store_true",
                help="do not require logging in: queries may be limited to a lower rate")
        # TODO: maybe leave only the short option to forbid configurability in config file
        group.add_argument("-f", "--force", action="store_true",
                help="try to update the page even if it was last saved in the same UTC day")
        group.add_argument("--toc-languages", default="all", type=ws.config.argtype_comma_list_choices(["all"] + lang.get_internal_tags()),
                help="a comma-separated list of language tags whose ToC pages should be updated (default: %(default)s)")
        group.add_argument("--toc-page", default="Table of contents",
                help="the page name on the wiki to fetch and update (the language suffix "
                     "is added automatically as necessary) (default: %(default)s)")
        # TODO: no idea how to forbid setting this globally in the config...
        group.add_argument("--summary", default="automatic update",
                help="the edit summary to use when saving the page (default: %(default)s)")

    @classmethod
    def from_argparser(klass, args, api=None):
        if api is None:
            api = API.from_argparser(args)
        return klass(api, args)

    def get_pages_contents(self, titles):
        contents = {}
        timestamps = {}
        pageids = {}

        result = self.api.call_api(action="query", prop="revisions", rvprop="content|timestamp", titles="|".join(titles))
        for page in result["pages"].values():
            if "revisions" in page:
                title = page["title"]
                revision = page["revisions"][0]
                text = revision["*"]
                contents[title] = text
                timestamps[title] = revision["timestamp"]
                pageids[title] = page["pageid"]

        titles = set(titles)
        retrieved = set(contents.keys())
        if retrieved != titles:
            logger.error("unable to retrieve content of all pages: pages {} are missing, retrieved {}".format(titles - retrieved, retrieved))

        return contents, timestamps, pageids

    def parse_toc_table(self, title, wikicode):
        toc_table = None
        # default format is one column in the title's language
        columns = [lang.tag_for_langname(lang.detect_language(title)[1])]
        category_names = LowercaseDict()
        alsoin = {}

        for table in wikicode.ifilter_tags(matches=lambda node: node.tag == "table"):
            if table.has("id"):
                id_ = table.get("id")
                if id_.value == "wiki-scripts-toc-table":
                    toc_table = table
                    break

        if toc_table is not None:
            # parse data-toc-languages attribute
            try:
                _languages = str(toc_table.get("data-toc-languages").value)
                columns = _languages.split(",")
            except ValueError:
                toc_table.add("data-toc-languages", value=",".join(columns))

            # parse data-toc-alsoin attribute
            if toc_table.has("data-toc-alsoin"):
                alsoin = self.parse_alsoin(title, str(toc_table.get("data-toc-alsoin").value))
            elif columns != ["en"]:
                logger.warning("Page '{}': missing 'also in' translations".format(title))

            # extract localized category names (useful even for PlainFormatter)
            category_names = self.extract_translations(toc_table.contents)

        return toc_table, columns, category_names, alsoin

    def parse_alsoin(self, title, value):
        alsoin = {}
        for item in value.split(","):
            item = item.strip()
            try:
                tag, translation = item.split(":", maxsplit=1)
                tag = tag.strip()
                translation = translation.strip()
                if not lang.is_language_tag(tag):
                    raise ValueError
            except ValueError:
                tag = lang.tag_for_langname(lang.detect_language(title)[1])
                translation = item
            alsoin[tag] = translation
        logger.debug("Page '{}': parsed data-toc-alsoin = {}".format(title, alsoin))
        return alsoin

    def extract_translations(self, wikicode):
        dictionary = LowercaseDict()
        for wikilink in wikicode.ifilter_wikilinks(recursive=True):
            # skip catlinks without leading colon
            if not wikilink.title.startswith(":"):
                continue
            title = Title(self.api, wikilink.title)
            if title.namespace == "Category" and wikilink.text:
                # skip trivial cases to apply our defaults
                pure, _ = lang.detect_language(title.pagename)
                if wikilink.text.lower() != title.pagename.lower() and wikilink.text.lower() != pure.lower():
                    dictionary[str(title)] = str(wikilink.text).strip()
        return dictionary

    def save_page(self, title, pageid, text_old, text_new, timestamp):
        if not self.cliargs.force and datetime.datetime.utcnow().date() <= parse_date(timestamp).date():
            logger.info("The page '{}' has already been updated this UTC day.".format(title))
            return

        if text_old != text_new:
            try:
                if "bot" in self.api.user_rights:
                    self.api.edit(title, pageid, text_new, timestamp, self.cliargs.summary, bot="1")
                else:
                    self.api.edit(title, pageid, text_new, timestamp, self.cliargs.summary, minor="1")
            except APIError as e:
                pass
        else:
            logger.info("Page '{}' is already up to date.".format(title))

    def run(self):
        if not self.cliargs.anonymous:
            require_login(self.api)

        # build category graph
        category_graph = CategoryGraph(self.api)
        graph_parents, graph_subcats, info = category_graph.build_graph()

        # detect target pages, fetch content at once
        contents, timestamps, pageids = self.get_pages_contents(self.titles)

        for title in self.titles:
            if title not in contents:
                continue

            wikicode = mwparserfromhell.parse(contents[title])
            toc_table, columns, category_names, alsoin = self.parse_toc_table(title, wikicode)

            if toc_table is None:
                if self.cliargs.save is True:
                    logger.error(
                            "The wiki page '{}' does not contain the ToC table. "
                            "Create the following entry point manually:\n"
                            "{{| id=\"wiki-scripts-toc-table\"\n...\n|}}".format(title))
                    continue
                else:
                    logger.warning(
                            "The wiki page '{}' does not contain the ToC table, "
                            "so there will be no translations.".format(title))

            if self.cliargs.print:
                ff = PlainFormatter(graph_parents, info, category_names, alsoin)
            elif self.cliargs.save:
                ff = MediaWikiFormatter(graph_parents, info, category_names, alsoin, include_opening_closing_tokens=False)
            else:
                raise NotImplementedError("unknown output action: {}".format(self.cliargs.save))

            roots = ["Category:{}".format(lang.langname_for_tag(c)) for c in columns]
            ff.format_root(roots)
            if len(roots) == 1:
                for item in category_graph.walk(graph_subcats, roots[0]):
                    ff.format_row(item)
            elif len(roots) == 2:
                for result in category_graph.compare_components(graph_subcats, *roots):
                    ff.format_row(*result)
            else:
                logger.error("Cannot compare more than 2 languages at once. Requested: {}".format(columns))
                continue

            if self.cliargs.print:
                print("== {} ==\n".format(title))
                print(ff)
            elif self.cliargs.save:
                toc_table.contents = str(ff)
                self.save_page(title, pageids[title], contents[title], str(wikicode), timestamps[title])


if __name__ == "__main__":
    import ws.config
    toc = ws.config.object_from_argparser(TableOfContents, description="Build a presentation of the wiki's table of contents")
    toc.run()
