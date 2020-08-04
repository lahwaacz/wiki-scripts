#! /usr/bin/env python3

import logging

import mwparserfromhell

from ws.client import API, APIError
from ws.interactive import edit_interactive, require_login, InteractiveQuit
from ws.diff import diff_highlighted
import ws.ArchWiki.lang as lang
from ws.checkers import ExtlinkReplacements

logger = logging.getLogger(__name__)


class LinkChecker(ExtlinkReplacements):

    interactive_only_pages = ["ArchWiki:Sandbox"]
#    skip_pages = ["Table of contents", "Help:Editing", "ArchWiki:Reports", "ArchWiki:Requests", "ArchWiki:Statistics"]
    skip_pages = []

    def __init__(self, api, interactive=False, dry_run=False, first=None, title=None, langnames=None, connection_timeout=30, max_retries=3):
        if not dry_run:
            # ensure that we are authenticated
            require_login(api)

        super().__init__(api, None, interactive=interactive, timeout=connection_timeout, max_retries=max_retries)

        self.dry_run = dry_run

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
#        group.add_argument("-i", "--interactive", action="store_true",
#                help="enables interactive mode")
        group.add_argument("--dry-run", action="store_true",
                help="enables dry-run mode (changes are only shown and discarded)")
        mode = group.add_mutually_exclusive_group()
        mode.add_argument("--first", default=None, metavar="TITLE",
                help="the title of the first page to be processed")
        mode.add_argument("--title",
                help="the title of the only page to be processed")
        group.add_argument("--lang", default=None,
                help="comma-separated list of language tags to process (default: all, choices: {})".format(lang.get_internal_tags()))

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
#        return klass(api, interactive=args.interactive, dry_run=args.dry_run, first=args.first, title=args.title, langnames=langnames, connection_timeout=args.connection_timeout, max_retries=args.connection_max_retries)
        return klass(api, interactive=True, dry_run=args.dry_run, first=args.first, title=args.title, langnames=langnames, connection_timeout=args.connection_timeout, max_retries=args.connection_max_retries)

    def update_page(self, src_title, text):
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
        if lang.detect_language(src_title)[0] in self.interactive_only_pages and self.interactive is False:
            logger.info("Skipping page [[{}]] which is blacklisted for non-interactive mode".format(src_title))
            return text, ""

        logger.info("Parsing page [[{}]] ...".format(src_title))
        # FIXME: skip_style_tags=True is a partial workaround for https://github.com/earwig/mwparserfromhell/issues/40
        wikicode = mwparserfromhell.parse(text, skip_style_tags=True)
        summary_parts = []

        for extlink in wikicode.ifilter_external_links(recursive=True):
            self.update_extlink(wikicode, extlink, summary_parts)

        # deduplicate and keep order
        parts = set()
        parts_add = parts.add
        summary_parts = [part for part in summary_parts if not (part in parts or parts_add(part))]

        edit_summary = ", ".join(summary_parts)
#        if self.interactive is True:
#            edit_summary += " (interactive)"

        return str(wikicode), edit_summary

    def _edit(self, title, pageid, text_new, text_old, timestamp, edit_summary):
        if text_old != text_new:
            if self.dry_run:
                diff = diff_highlighted(text_old, text_new, title + ".old", title + ".new", timestamp, "<utcnow>")
                print(diff)
                print("Edit summary:  " + edit_summary)
                print("(edit discarded due to --dry-run)")
            else:
                try:
                    if self.interactive is False:
                        self.api.edit(title, pageid, text_new, timestamp, edit_summary, bot="")
                    else:
                        edit_interactive(self.api, title, pageid, text_old, text_new, timestamp, edit_summary, bot="")
                except APIError as e:
                    pass

    def process_page(self, title):
        result = self.api.call_api(action="query", prop="revisions", rvprop="content|timestamp", rvslots="main", titles=title)
        page = list(result["pages"].values())[0]
        timestamp = page["revisions"][0]["timestamp"]
        text_old = page["revisions"][0]["slots"]["main"]["*"]
        text_new, edit_summary = self.update_page(title, text_old)
        self._edit(title, page["pageid"], text_new, text_old, timestamp, edit_summary)

    def process_allpages(self, apfrom=None, langnames=None):
#        namespaces = [0, 4, 14, 3000]
#        if self.interactive is True:
#            namespaces.append(12)
        # temporarily enable all namespaces (Arch's git URLs migration)
        namespaces = [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15, 3000, 3001]

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
                # if the user is not logged in, the limit for revisions may be lower than gaplimit,
                # in which case the generator will yield some pages multiple times without revisions
                # before the query-continuation kicks in
                if "revisions" not in page:
                    continue
                title = page["title"]
                if langnames and lang.detect_language(title)[1] not in langnames:
                    continue
                _title = self.api.Title(title)
                timestamp = page["revisions"][0]["timestamp"]
                text_old = page["revisions"][0]["slots"]["main"]["*"]
                text_new, edit_summary = self.update_page(title, text_old)
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

    checker = ws.config.object_from_argparser(LinkChecker, description="Parse all pages on the wiki and try to fix/simplify/beautify links")

    try:
        checker.run()
    except (InteractiveQuit, KeyboardInterrupt):
        pass
