#! /usr/bin/env python3

import logging

import mwparserfromhell

from ws.checkers import get_edit_summary_tracker, CheckerBase
from ws.pageupdater import PageUpdater
import ws.ArchWiki.lang as lang
from ws.parser_helpers.title import InvalidTitleCharError
from ws.parser_helpers.wikicode import ensure_flagged_by_template, ensure_unflagged_by_template

logger = logging.getLogger(__name__)

ARCHIVE_TITLE = "ArchWiki:Archive"


class ArchivedLinkChecker(CheckerBase):

    def __init__(self, api, db, **kwargs):
        super().__init__(api, db, **kwargs)

    def update_wikilink(self, wikicode, wikilink, src_title, summary_parts):
        title = self.api.Title(wikilink.title)

        # interwiki links are never archived
        if title.iwprefix:
            return

        if title.fullpagename in self.api.redirects.map:
            target_title = self.api.Title(self.api.redirects.resolve(title.fullpagename))
            if target_title.fullpagename == ARCHIVE_TITLE:
                summary = get_edit_summary_tracker(wikicode, summary_parts)
                with summary("mark links to archived pages"):
                    # first unflag to remove any translated version of the flag
                    ensure_unflagged_by_template(wikicode, wikilink, "Archived page", match_only_prefix=True)
                    # flag with the correct translated template
                    src_lang = lang.detect_language(src_title)[1]
                    flag = self.get_localized_template("Archived page", src_lang)
                    ensure_flagged_by_template(wikicode, wikilink, flag)

    def handle_node(self, src_title, wikicode, node, summary_parts):
        if isinstance(node, mwparserfromhell.nodes.Wikilink):
            try:
                self.update_wikilink(wikicode, node, src_title, summary_parts)
            # this can happen, e.g. due to [[{{TALKPAGENAME}}]]
            except InvalidTitleCharError:
                pass


class Updater(PageUpdater):
    force_interactive = True

    def generate_pages(self):
        # handle the trivial case first
        if self.title is not None:
            result = self.api.call_api(action="query", prop="revisions", rvprop="content|timestamp", rvslots="main", titles=self.title)
            yield list(result["pages"].values())[0]
            return

        namespaces = "|".join(str(ns) for ns in self.namespaces)

        for page in self.api.generator(generator="backlinks", gbltitle=ARCHIVE_TITLE, gbllimit="200", gblnamespace=namespaces, gblfilterredir="nonredirects", gblredirect="1",
                                       prop="revisions", rvprop="content|timestamp", rvslots="main"):
            # if the user is not logged in, the limit for revisions may be lower than gaplimit,
            # in which case the generator will yield some pages multiple times without revisions
            # before the query-continuation kicks in
            if "revisions" not in page:
                continue

            # skip pages that are redirects (MediaWiki includes them because of blredirects=1)
            if page["title"] in self.api.redirects.map:
                continue

            yield page


if __name__ == "__main__":
    import ws.config
    from ws.interactive import InteractiveQuit

    argparser = ws.config.getArgParser(description="Mark links to archived pages")
    Updater.set_argparser(argparser)
    # checkers don't have their own set_argparser method at the moment,
    # they just reuse API's and PageUpdater's options

    args = ws.config.parse_args(argparser)

    # create updater and add checkers
    updater = Updater.from_argparser(args)
    checker = ArchivedLinkChecker(updater.api, None)
    updater.add_checker(mwparserfromhell.nodes.Wikilink, checker)

    try:
        updater.run()
    except (InteractiveQuit, KeyboardInterrupt):
        pass
