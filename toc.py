#! /usr/bin/env python3

import argparse
import datetime
import logging
from collections.abc import Iterable, Sequence
from typing import Self

from mwparserfromhell.nodes import Tag
from mwparserfromhell.wikicode import Wikicode

import ws.ArchWiki.lang as lang
from ws.autopage import AutoPage
from ws.client import API, APIError
from ws.config import ConfigurableObject
from ws.interactive import require_login
from ws.interlanguage.Categorization import Categorization
from ws.interlanguage.CategoryGraph import CategoryGraph
from ws.interlanguage.Decategorization import Decategorization
from ws.parser_helpers.title import canonicalize

logger = logging.getLogger(__name__)


class LowercaseDict(dict[str, str]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getitem__(self, key: str) -> str:
        return super().__getitem__(key.lower())

    def __setitem__(self, key: str, value: str) -> None:
        super().__setitem__(key.lower(), value)

    def __contains__(self, key: str) -> bool:  # type: ignore[override]
        return super().__contains__(key.lower())

    def get(self, key: str, default: str | None = None) -> str | None:  # type: ignore[override]
        return super().get(key.lower(), default)

    def setdefault(self, key: str, default: str) -> str:
        return super().setdefault(key.lower(), default)

    def update(self, other: dict[str, str]) -> None:  # type: ignore[override]
        for key, value in other.items():
            super().__setitem__(key.lower(), value)

    def pop(self, key: str, default: str | None = None) -> str | None:  # type: ignore[override]
        return super().pop(key.lower(), default)


class BaseFormatter:
    def __init__(
        self,
        parents: dict[str, list[str]],
        info: dict[str, dict],
        category_names: dict[str, str],
        alsoin: dict[str, str] | None = None,
    ):
        self.parents = parents
        self.info = info
        self.category_names = category_names
        if alsoin is None:
            alsoin = {}
        alsoin.setdefault("en", "also in")
        self.alsoin = alsoin

    def format_also_in(self, parents: Iterable[str], lang_tag: str) -> str:
        alsoin = self.alsoin.get(lang_tag, self.alsoin["en"])
        return " ({alsoin} {categories})".format(
            alsoin=alsoin, categories=", ".join(sorted(parents))
        )

    def localize(self, category: str) -> str:
        default = lang.detect_language(category.split(":", 1)[1])[0]
        return self.category_names.get(category, default)

    def format_root(self, title: str | Sequence[str]) -> None:
        raise NotImplementedError

    def format_cell(self, title: str, parent: str, levels: Sequence[int]) -> str:
        raise NotImplementedError

    def format_row(self, *columns: tuple[str, str, Sequence[int]] | str | None) -> None:
        raise NotImplementedError


class PlainFormatter(BaseFormatter):
    def __init__(
        self,
        parents: dict[str, list[str]],
        info: dict[str, dict],
        category_names: dict[str, str],
        alsoin: dict[str, str] | None = None,
    ):
        super().__init__(parents, info, category_names, alsoin)
        self.text = ""

    def format_root(self, title: str | Sequence[str]) -> None:
        if isinstance(title, str):
            self.text += "{} ({})\n".format(title, self.info[title]["pages"])
        elif isinstance(title, Sequence):
            # title is a tuple of titles
            for t in title:
                self.format_root(t)
            if len(title) > 1:
                self.text += "----\n"

    def format_cell(self, title: str, parent: str, levels: Sequence[int]) -> str:
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
            localized_parents = [self.localize(cat) for cat in parents]
            output += self.format_also_in(localized_parents, lang_tag)
        return output

    def format_row(self, *columns: tuple[str, str, Sequence[int]] | str | None) -> None:
        for col in columns:
            if isinstance(col, tuple):
                self.text += self.format_cell(*col) + "\n"
            elif col:
                self.text += str(col) + "\n"
            else:
                self.text += "\n"
        if len(columns) > 1:
            self.text += "----\n"

    def __str__(self) -> str:
        return self.text


class MediaWikiFormatter(BaseFormatter):

    cell_format = '<span style="margin-left:{margin:.3}em;"><small>{levels}</small> {catlink} <small>{info}</small></span>'

    def __init__(
        self,
        parents: dict[str, list[str]],
        info: dict[str, dict],
        category_names: dict[str, str],
        alsoin: dict[str, str] | None = None,
        include_opening_closing_tokens: bool = True,
    ):
        super().__init__(parents, info, category_names, alsoin)
        self.include_opening_closing_tokens = include_opening_closing_tokens
        self.text = ""

    def catlink(self, title: str) -> str:
        catlink = "[[:{}|{}]]".format(title, self.localize(title))
        if lang.is_rtl_language(lang.detect_language(title)[1]):
            catlink += "&lrm;"
        return catlink

    def format_root(self, title: str | Iterable[str]) -> None:
        if isinstance(title, str):
            self.text += "| {} <small>({})</small>\n".format(
                self.catlink(title), self.info[title]["pages"]
            )
            self.text += "|-\n"
        elif isinstance(title, Iterable):
            # title is a tuple of titles
            for t in title:
                self.text += "| {} <small>({})</small>\n".format(
                    self.catlink(t), self.info[t]["pages"]
                )
            self.text += "|-\n"

    def format_cell(self, title: str, parent: str, levels: Sequence[int]) -> str:
        lang_tag = lang.tag_for_langname(lang.detect_language(title)[1])
        margin = 1.6 * len(levels)
        lev = ".".join(str(x + 1) for x in levels) + "."
        info = "({})".format(self.info[title]["pages"])
        # "also in" suffix
        parents = set(self.parents[title]) - {parent}
        if parents:
            cat_parents = [self.catlink(cat) for cat in parents]
            info += self.format_also_in(cat_parents, lang_tag)
        return self.cell_format.format(
            margin=margin, levels=lev, catlink=self.catlink(title), info=info
        )

    def format_row(self, *columns: tuple[str, str, Sequence[int]] | str | None) -> None:
        for col in columns:
            if isinstance(col, tuple):
                self.text += "| " + self.format_cell(*col) + "\n"
            elif col:
                self.text += "| " + str(col) + "\n"
            else:
                self.text += "|\n"
        self.text += "|-\n"

    def __str__(self) -> str:
        if self.include_opening_closing_tokens is True:
            out = "{|\n" + self.text
            if out.endswith("\n"):
                out += "|}"
            else:
                out += "\n|}"
            return out
        return self.text


class TableOfContents(ConfigurableObject):

    def __init__(self, api: API, cliargs: argparse.Namespace):
        self.api = api
        self.cliargs = cliargs

        if self.cliargs.save is False and self.cliargs.print is False:
            self.cliargs.print = True

        if self.cliargs.toc_languages == ["all"]:
            self.cliargs.toc_languages = lang.get_internal_tags()
        # strip "(Language)" suffix
        self.cliargs.toc_page = lang.detect_language(
            canonicalize(self.cliargs.toc_page)
        )[0]

        # detect page titles
        self.titles = []
        for ln in sorted(self.cliargs.toc_languages):
            if ln == lang.tag_for_langname(lang.get_local_language()):
                self.titles.append(self.cliargs.toc_page)
            else:
                self.titles.append(
                    "{} ({})".format(self.cliargs.toc_page, lang.langname_for_tag(ln))
                )

    @staticmethod
    def set_argparser(argparser: argparse.ArgumentParser) -> None:

        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)

        output = argparser.add_argument_group(title="output mode")
        _g = output.add_mutually_exclusive_group()
        # TODO: maybe leave only the short option to forbid configurability in config file
        _g.add_argument(
            "-s",
            "--save",
            action="store_true",
            help="try to save the page (requires being logged in)",
        )
        _g.add_argument(
            "-p",
            "--print",
            action="store_true",
            help="print the updated text in the standard output (this is the default output method)",
        )

        group = argparser.add_argument_group(title="script parameters")
        group.add_argument(
            "-a",
            "--anonymous",
            action="store_true",
            help="do not require logging in: queries may be limited to a lower rate",
        )
        # TODO: maybe leave only the short option to forbid configurability in config file
        group.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="try to update the page even if it was last saved in the same UTC day",
        )
        group.add_argument(
            "--toc-languages",
            metavar="LANG",
            default=["all"],
            nargs="+",
            choices=["all"] + lang.get_internal_tags(),
            help="a list of language tags whose ToC pages should be updated (options: {}, default: %(default)s)".format(
                lang.get_internal_tags()
            ),
        )
        group.add_argument(
            "--toc-page",
            default="Table of contents",
            help="the page name on the wiki to fetch and update (the language suffix "
            "is added automatically as necessary) (default: %(default)s)",
        )
        # TODO: no idea how to forbid setting this globally in the config...
        group.add_argument(
            "--summary",
            default="automatic update",
            help="the edit summary to use when saving the page (default: %(default)s)",
        )

    @classmethod
    def from_argparser(
        cls: type[Self], args: argparse.Namespace, api: API | None = None
    ) -> Self:
        if api is None:
            api = API.from_argparser(args)
        return cls(api, args)

    def parse_toc_table(
        self, title: str, toc_table: Tag | None
    ) -> tuple[list[str], dict[str, str], dict[str, str]]:
        # default format is one column in the title's language
        columns = [lang.tag_for_langname(lang.detect_language(title)[1])]
        category_names: dict[str, str] = LowercaseDict()
        alsoin = {}

        if toc_table is not None:
            # parse data-toc-languages attribute
            try:
                _languages = str(toc_table.get("data-toc-languages").value)
                columns = _languages.split(",")
            except ValueError:
                toc_table.add("data-toc-languages", value=",".join(columns))

            # parse data-toc-alsoin attribute
            if toc_table.has("data-toc-alsoin"):
                alsoin = self.parse_alsoin(
                    title, str(toc_table.get("data-toc-alsoin").value)
                )
            elif columns != ["en"]:
                logger.warning(
                    "Page [[{}]]: missing 'also in' translations".format(title)
                )

            # extract localized category names (useful even for PlainFormatter)
            category_names = self.extract_translations(toc_table.contents)

        return columns, category_names, alsoin

    def parse_alsoin(self, title: str, value: str) -> dict[str, str]:
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
        logger.debug("Page [[{}]]: parsed data-toc-alsoin = {}".format(title, alsoin))
        return alsoin

    def extract_translations(self, wikicode: Wikicode) -> dict[str, str]:
        dictionary = LowercaseDict()
        for wikilink in wikicode.ifilter_wikilinks(recursive=True):
            # skip catlinks without leading colon
            if not wikilink.title.startswith(":"):
                continue
            title = self.api.Title(wikilink.title)
            if title.namespace == "Category" and wikilink.text:
                # skip trivial cases to apply our defaults
                pure, _ = lang.detect_language(title.pagename)
                if (
                    wikilink.text.lower() != title.pagename.lower()
                    and wikilink.text.lower() != pure.lower()
                ):
                    dictionary[str(title)] = str(wikilink.text).strip()
        return dictionary

    def run(self) -> None:
        if not self.cliargs.anonymous:
            require_login(self.api)

        # if we are going to save, make sure that the categories are correct first
        if self.cliargs.save is True:
            cat = Categorization(self.api)
            cat.fix_allpages()
            decat = Decategorization(self.api)
            decat.fix_allpages()

        # build category graph
        graph = CategoryGraph(self.api)

        # if we are going to save, init wanted categories
        if self.cliargs.save is True:
            graph.init_wanted_categories()

        # detect target pages, fetch content at once
        page = AutoPage(self.api, fetch_titles=self.titles)

        for title in self.titles:
            try:
                page.set_title(title)
            except ValueError:
                # page not fetched
                continue

            toc_table = page.get_tag_by_id(tag="table", id="wiki-scripts-toc-table")
            columns, category_names, alsoin = self.parse_toc_table(title, toc_table)

            if toc_table is None:
                if self.cliargs.save is True:
                    logger.error(
                        "The wiki page [[{}]] does not contain the ToC table. "
                        "Create the following entry point manually:\n"
                        '{{| id="wiki-scripts-toc-table"\n...\n|}}'.format(title)
                    )
                    continue
                else:
                    logger.warning(
                        "The wiki page [[{}]] does not contain the ToC table, "
                        "so there will be no translations.".format(title)
                    )

            ff: BaseFormatter
            if self.cliargs.print:
                ff = PlainFormatter(graph.parents, graph.info, category_names, alsoin)
            elif self.cliargs.save:
                ff = MediaWikiFormatter(
                    graph.parents,
                    graph.info,
                    category_names,
                    alsoin,
                    include_opening_closing_tokens=False,
                )
            else:
                raise NotImplementedError(
                    "unknown output action: {}".format(self.cliargs.save)
                )

            roots = ["Category:{}".format(lang.langname_for_tag(c)) for c in columns]
            ff.format_root(roots)
            if len(roots) == 1:
                for item in graph.walk(graph.subcats, roots[0]):
                    ff.format_row(item)
            elif len(roots) == 2:
                for result in graph.compare_components(graph.subcats, *roots):
                    ff.format_row(*result)
            else:
                logger.error(
                    "Cannot compare more than 2 languages at once. Requested: {}".format(
                        columns
                    )
                )
                continue

            if self.cliargs.print:
                print("== {} ==\n".format(title))
                print(ff)
            elif self.cliargs.save:
                # (mwparserfromhell does not have getters and setters next to each other,
                # so mypy thinks the property is read-only)
                toc_table.contents = str(ff)  # type: ignore
                if self.cliargs.force or page.is_old_enough(
                    min_interval=datetime.timedelta(days=1), strip_time=True
                ):
                    try:
                        page.save(self.cliargs.summary)
                    except APIError:
                        pass
                else:
                    logger.info(
                        "The page [[{}]] has already been updated this UTC day.".format(
                            title
                        )
                    )


if __name__ == "__main__":
    import ws.config

    toc = ws.config.object_from_argparser(
        TableOfContents,
        description="Build a presentation of the wiki's table of contents",
    )
    toc.run()
