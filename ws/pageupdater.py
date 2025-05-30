# FIXME: space-initialized code blocks should be skipped, but mwparserfromhell does not support that
# TODO: changes rejected interactively should be logged

import argparse
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Generator, Iterable, Self

import mwparserfromhell
from mwparserfromhell.nodes import Node

import ws.ArchWiki.lang as lang
from ws.checkers import CheckerBase
from ws.client import API, APIError
from ws.config import ConfigurableObject
from ws.diff import diff_highlighted
from ws.interactive import edit_interactive, require_login
from ws.parser_helpers.title import canonicalize

logger = logging.getLogger(__name__)


class PageUpdater(ConfigurableObject):

    # subclasses can set this to True to force the interactive mode
    force_interactive = False

    interactive_only_pages = ["ArchWiki:Sandbox"]
    skip_pages: list[str] = []
    skip_templates = {"Broken package link", "Broken section link", "Dead link"}

    # either "all", "nonredirects", or "redirects"
    apfilterredir = "all"

    # number of threads to use for the update_page processing
    # WARNING: threading in update_page is not safe:
    #   - modifications to the wikicode has to be synchronized
    #     (can be hacked with a lock - see CheckerBase.lock_wikicode)
    #   - the context manager for checking changes to the wikicode and adding
    #     an edit summary (see CheckerBase.get_edit_summary_tracker) is not
    #     thread-safe - changes made by thread X might be detected by thread Y,
    #     resulting in multiple unrelated summaries for a single change
    #   - most checkers were not designed for threading so there might be other
    #     problems
    # It does not help much anyway, because of the Python's GIL. Basically only
    # handling of HTTP requests can be overlapped with threading, so it should
    # be used only in ExtlinkStatusChecker (extlink-checker.py) which uses only
    # one edit summary.
    threads_update_page = 1

    def __init__(
        self,
        api: API,
        interactive: bool = False,
        dry_run: bool = False,
        first: str | None = None,
        title: str | None = None,
        langnames: Iterable[str] | None = None,
    ):
        if not dry_run:
            # ensure that we are authenticated
            require_login(api)
        self.api = api

        self.interactive = interactive if self.force_interactive is False else True
        self.dry_run = dry_run

        # parameters for the selection of page titles
        self.first = first
        self.title = title
        self.langnames = langnames

        self.namespaces = [0, 4, 14, 3000]
        if self.interactive is True:
            self.namespaces.append(12)

        # mapping of mwparserfromhell node types to lists of checker objects
        self.checkers: dict[type[Node], list[CheckerBase]] = {}

    @classmethod
    def set_argparser(cls: type[Self], argparser: argparse.ArgumentParser) -> None:
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)

        group = argparser.add_argument_group(title="Page updater parameters")
        if cls.force_interactive is False:
            group.add_argument(
                "-i",
                "--interactive",
                action="store_true",
                help="enables interactive mode",
            )
        group.add_argument(
            "--dry-run",
            action="store_true",
            help="enables dry-run mode (changes are only shown and discarded)",
        )
        mode = group.add_mutually_exclusive_group()
        mode.add_argument(
            "--first",
            default=None,
            metavar="TITLE",
            help="the title of the first page to be processed",
        )
        mode.add_argument("--title", help="the title of the only page to be processed")
        group.add_argument(
            "--lang",
            default=None,
            help="comma-separated list of language tags to process (default: all, choices: {})".format(
                lang.get_internal_tags()
            ),
        )

    @classmethod
    def from_argparser(
        cls: type[Self], args: argparse.Namespace, api: API | None = None
    ) -> Self:
        if api is None:
            api = API.from_argparser(args)
        if args.lang:
            tags = args.lang.split(",")
            for tag in tags:
                if tag not in lang.get_internal_tags():
                    # FIXME: more elegant solution
                    raise Exception("{} is not a valid language tag".format(tag))
            langnames = {lang.langname_for_tag(tag) for tag in tags}
        else:
            langnames = set()
        interactive = args.interactive if cls.force_interactive is False else True
        return cls(
            api,
            interactive=interactive,
            dry_run=args.dry_run,
            first=args.first,
            title=args.title,
            langnames=langnames,
        )

    def add_checker(self, node_type: type[Node], checker: CheckerBase) -> None:
        """
        Register a new checker for the given node type.

        :param node_type:
            the node type for which the checker will be registered. Must be a
            subtype of :py:class:`mwparserfromhell.nodes.Node`.
        :param checker:
            the checker which will handle nodes of the given node type. Should
            be an instance of :py:class:`ws.checkers.CheckerBase`.
        """
        if not issubclass(node_type, mwparserfromhell.nodes.Node):
            raise TypeError(
                "node_type must be a subclass of `mwparserfromhell.nodes.Node`"
            )
        checker.interactive = self.interactive
        self.checkers.setdefault(node_type, []).append(checker)

    def update_page(self, src_title: str, text: str) -> tuple[str, str]:
        """
        Parse the content of the page and call various methods to update the links.

        :param str src_title: title of the page
        :param str text: content of the page
        :returns: a (text, edit_summary) tuple, where text is the updated content
            and edit_summary is the description of performed changes
        """
        if lang.detect_language(src_title)[0] in self.skip_pages:
            logger.info("Skipping blacklisted page [[{}]]".format(src_title))
            return text, ""
        if (
            lang.detect_language(src_title)[0] in self.interactive_only_pages
            and self.interactive is False
        ):
            logger.info(
                "Skipping page [[{}]] which is blacklisted for non-interactive mode".format(
                    src_title
                )
            )
            return text, ""

        logger.info("Parsing page [[{}]] ...".format(src_title))
        # FIXME: skip_style_tags=True is a partial workaround for https://github.com/earwig/mwparserfromhell/issues/40
        wikicode = mwparserfromhell.parse(text, skip_style_tags=True)
        summary_parts: list[str] = []

        def gen_nodes() -> Generator[tuple[CheckerBase, Node]]:
            for node_type, checkers in self.checkers.items():
                for node in wikicode.ifilter(recursive=True, forcetype=node_type):
                    # skip templates that may be added or removed
                    if node_type is mwparserfromhell.nodes.Template and any(
                        canonicalize(node.name).startswith(prefix)
                        for prefix in self.skip_templates
                    ):
                        continue
                    # handle the node with all registered checkers
                    for checker in checkers:
                        yield checker, node

        async def async_exec() -> None:
            # - We could use native asyncio tasks with basically the same
            #   performance (threading is limited by the GIL), but we would
            #   have to add "async" everyhwere.
            # - The default executor is also ThreadPoolExecutor, but with
            #   unspecified number of threads.
            # - The maximum number of threads does not matter much, fine-grained
            #   resource limits are enforced by managers (e.g. httpx)
            with ThreadPoolExecutor(max_workers=self.threads_update_page) as executor:
                loop = asyncio.get_event_loop()
                tasks = [
                    loop.run_in_executor(
                        executor,
                        checker.handle_node,
                        # a way to pass multiple arguments to the handle_node method
                        *(src_title, wikicode, node, summary_parts),
                    )
                    for checker, node in gen_nodes()
                ]
                for result in await asyncio.gather(*tasks):
                    pass

        if self.threads_update_page == 1:
            for checker, node in gen_nodes():
                checker.handle_node(src_title, wikicode, node, summary_parts)
        else:
            asyncio.run(async_exec())

        # deduplicate and keep order
        parts: set[str] = set()
        parts_add = parts.add
        summary_parts = [
            part for part in summary_parts if not (part in parts or parts_add(part))
        ]

        edit_summary = ", ".join(summary_parts)
        if self.force_interactive is False and self.interactive is True:
            edit_summary += " (interactive)"

        return str(wikicode), edit_summary

    def _edit(
        self,
        title: str,
        pageid: int,
        text_new: str,
        text_old: str,
        timestamp: str,
        edit_summary: str,
    ) -> None:
        if text_old == text_new:
            return

        if self.dry_run:
            diff = diff_highlighted(
                text_old,
                text_new,
                title + ".old",
                title + ".new",
                timestamp,
                "<utcnow>",
            )
            print(diff)
            print("Edit summary:  " + edit_summary)
            print("(edit discarded due to --dry-run)")
            return

        interactive = self.interactive

        # override interactive mode for edits which are very frequent and "always" correct
        if "bot" in self.api.user.rights and edit_summary == "update http to https":
            interactive = False

        try:
            if interactive is False:
                self.api.edit(title, pageid, text_new, timestamp, edit_summary, bot="")
            else:
                # print the info message
                print(
                    "\nSuggested edit for page [[{}]]. Please double-check all changes before accepting!".format(
                        title
                    )
                )

                if "bot" in self.api.user.rights:
                    edit_interactive(
                        self.api,
                        title,
                        pageid,
                        text_old,
                        text_new,
                        timestamp,
                        edit_summary,
                        bot="",
                    )
                else:
                    edit_interactive(
                        self.api,
                        title,
                        pageid,
                        text_old,
                        text_new,
                        timestamp,
                        edit_summary,
                    )
        except APIError:
            pass

    def process_page(self, page: dict[str, Any]) -> None:
        """
        :param dict page:
            the ``page`` part of the API response (must include the page title,
            pageid, and the timestamp and content of the last revision)
        """
        timestamp = page["revisions"][0]["timestamp"]
        text_old = page["revisions"][0]["slots"]["main"]["*"]
        text_new, edit_summary = self.update_page(page["title"], text_old)
        self._edit(
            page["title"], page["pageid"], text_new, text_old, timestamp, edit_summary
        )

    def generate_pages(self) -> Generator[dict[str, Any]]:
        # handle the trivial case first
        if self.title is not None:
            result = self.api.call_api(
                action="query",
                prop="revisions",
                rvprop="content|timestamp",
                rvslots="main",
                titles=self.title,
            )
            yield list(result["pages"].values())[0]
            return

        # clone the list of namespaces so that we can modify it for this method
        namespaces = self.namespaces.copy()

        # rewind to the right namespace (the API throws BadTitle error if the
        # namespace of apfrom does not match apnamespace)
        apfrom = self.first
        if apfrom is not None:
            _title = self.api.Title(apfrom)
            if _title.namespacenumber not in namespaces:
                logger.error(
                    "Valid namespaces for the --first option are {}.".format(
                        [self.api.site.namespaces[ns] for ns in namespaces]
                    )
                )
                return
            while namespaces[0] != _title.namespacenumber:
                del namespaces[0]
            # apfrom must be without namespace prefix
            apfrom = _title.pagename

        for ns in namespaces:
            for page in self.api.generator(
                generator="allpages",
                gaplimit="100",
                gapnamespace=ns,
                gapfrom=apfrom,
                gapfilterredir=self.apfilterredir,
                prop="revisions",
                rvprop="content|timestamp",
                rvslots="main",
            ):
                # if the user is not logged in, the limit for revisions may be lower than gaplimit,
                # in which case the generator will yield some pages multiple times without revisions
                # before the query-continuation kicks in
                if "revisions" not in page:
                    continue
                if (
                    self.langnames
                    and lang.detect_language(page["title"])[1] not in self.langnames
                ):
                    continue
                yield page
            # the apfrom parameter is valid only for the first namespace
            apfrom = ""

    def run(self) -> None:
        for page in self.generate_pages():
            self.process_page(page)
