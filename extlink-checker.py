#! /usr/bin/env python3

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

import mwparserfromhell

from ws.client import API, APIError
from ws.interactive import edit_interactive, require_login, InteractiveQuit
import ws.ArchWiki.lang as lang
from ws.checkers import ExtlinkStatusChecker

logger = logging.getLogger(__name__)


class Checker(ExtlinkStatusChecker):
    def __init__(self, api, first=None, title=None, langnames=None, connection_timeout=60, max_retries=3):
        # ensure that we are authenticated
        require_login(api)

        super().__init__(api, None, timeout=connection_timeout, max_retries=max_retries)

        # parameters for self.run()
        self.first = first
        self.title = title
        self.langnames = langnames

    @staticmethod
    def set_argparser(argparser):
        # first try to set options for objects we depend on
        present_groups = [group.title for group in argparser._action_groups]
        if "Connection parameters" not in present_groups:
            API.set_argparser(argparser)

        group = argparser.add_argument_group(title="script parameters")
        mode = group.add_mutually_exclusive_group()
        mode.add_argument("--first", default=None, metavar="TITLE",
                help="the title of the first page to be processed")
        mode.add_argument("--title",
                help="the title of the only page to be processed")
        group.add_argument("--lang", default="en",
                help="comma-separated list of language tags to process (default: en, choices: {})".format(lang.get_internal_tags()))

    @classmethod
    def from_argparser(klass, args, api=None):
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
        return klass(api, first=args.first, title=args.title, langnames=langnames, connection_timeout=args.connection_timeout, max_retries=args.connection_max_retries)

    async def update_page(self, src_title, text):
        """
        Parse the content of the page and call various methods to update the links.

        :param str src_title: title of the page
        :param str text: content of the page
        :returns: a (text, edit_summary) tuple, where text is the updated content
            and edit_summary is the description of performed changes
        """
        logger.info("Parsing page [[{}]] ...".format(src_title))
        # FIXME: skip_style_tags=True is a partial workaround for https://github.com/earwig/mwparserfromhell/issues/40
        wikicode = mwparserfromhell.parse(text, skip_style_tags=True)

        # We could use the default single-threaded executor with basically the same performance
        # (because of Python's GIL), but the ThreadPoolExecutor allows to limit the maximum number
        # of workers and thus the maximum number of concurrent connections.
        with ThreadPoolExecutor(max_workers=10) as executor:
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(
                    executor,
                    self.check_extlink_status,
                    # a way to pass multiple arguments to the check_extlink_status method
                    *(wikicode, extlink, src_title)
                )
                for extlink in wikicode.ifilter_external_links(recursive=True)
            ]
            for result in await asyncio.gather(*tasks):
                pass

        edit_summary = "update status of external links (interactive)"
        return str(wikicode), edit_summary

    def _edit(self, title, pageid, text_new, text_old, timestamp, edit_summary):
        if text_old != text_new:
            # print the info message
            print("\nSuggested edit for page [[{}]]. Please double-check all changes before accepting!".format(title))

            try:
                if "bot" in self.api.user.rights:
                    edit_interactive(self.api, title, pageid, text_old, text_new, timestamp, edit_summary, bot="")
                else:
                    edit_interactive(self.api, title, pageid, text_old, text_new, timestamp, edit_summary)
            except APIError as e:
                pass

    def process_page(self, title):
        result = self.api.call_api(action="query", prop="revisions", rvprop="content|timestamp", rvslots="main", titles=title)
        page = list(result["pages"].values())[0]
        timestamp = page["revisions"][0]["timestamp"]
        text_old = page["revisions"][0]["slots"]["main"]["*"]
        text_new, edit_summary = asyncio.run(self.update_page(title, text_old))
        self._edit(title, page["pageid"], text_new, text_old, timestamp, edit_summary)

    def process_allpages(self, apfrom=None, langnames=None):
        namespaces = [0, 4, 12, 14]

        # rewind to the right namespace (the API throws BadTitle error if the
        # namespace of apfrom does not match apnamespace)
        if apfrom is not None:
            _title = self.api.Title(apfrom)
            if _title.namespacenumber not in namespaces:
                logger.error("Valid namespaces for the --first option are {}.".format([self.api.site.namespaces[ns] for ns in namespaces]))
                return
            while namespaces[0] != _title.namespacenumber:
                del namespaces[0]
            # apfrom must be without namespace prefix
            apfrom = _title.pagename

        for ns in namespaces:
            for page in self.api.generator(generator="allpages", gaplimit="100", gapfilterredir="nonredirects", gapnamespace=ns, gapfrom=apfrom,
                                           prop="revisions", rvprop="content|timestamp", rvslots="main"):
                title = page["title"]
                if langnames and lang.detect_language(title)[1] not in langnames:
                    continue
                _title = self.api.Title(title)
                timestamp = page["revisions"][0]["timestamp"]
                text_old = page["revisions"][0]["slots"]["main"]["*"]
                text_new, edit_summary = asyncio.run(self.update_page(title, text_old))
                self._edit(title, page["pageid"], text_new, text_old, timestamp, edit_summary)
            # the apfrom parameter is valid only for the first namespace
            apfrom = ""

    def run(self):
        if self.title is not None:
            checker.process_page(self.title)
        else:
            checker.process_allpages(apfrom=self.first, langnames=self.langnames)


if __name__ == "__main__":
    import ws.config

    checker = ws.config.object_from_argparser(Checker, description="Parse all pages on the wiki and try to fix/simplify/beautify links")

    try:
        checker.run()
    except (InteractiveQuit, KeyboardInterrupt):
        pass
