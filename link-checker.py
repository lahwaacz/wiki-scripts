#! /usr/bin/env python3

import mwparserfromhell

from ws.client import API
from ws.db.database import Database
from ws.checkers import ExtlinkReplacements, ManTemplateChecker, WikilinkChecker
from ws.pageupdater import PageUpdater


# joining all checkers into a single object makes ExtlinkReplacements and ManTemplateChecker
# share their ExtlinkStatusChecker parent
class LinkChecker(ExtlinkReplacements, WikilinkChecker, ManTemplateChecker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def handle_node(self, src_title, wikicode, node, summary_parts):
        # dispatch calls to all parents, but return as soon as the node is handled
        # (this can be determined by the added edit summary)
        initial_length = len(summary_parts)
        for klass in [ExtlinkReplacements, WikilinkChecker, ManTemplateChecker]:
            klass.handle_node(self, src_title, wikicode, node, summary_parts)
            if len(summary_parts) != initial_length:
                return


class Updater(PageUpdater):
    skip_pages = ["Table of contents", "Help:Editing", "ArchWiki talk:Requests", "ArchWiki:Statistics"]

if __name__ == "__main__":
    import ws.config
    import ws.logging
    from ws.interactive import InteractiveQuit

    argparser = ws.config.getArgParser(description="Parse all pages on the wiki and try to fix/simplify/beautify links")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)
    Updater.set_argparser(argparser)
    # checkers don't have their own set_argparser method at the moment,
    # they just reuse API's and PageUpdater's options

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    # create updater and add checkers
    updater = Updater.from_argparser(args, api)
    checker = LinkChecker(api, db, timeout=args.connection_timeout, max_retries=args.connection_max_retries)
    updater.add_checker(mwparserfromhell.nodes.ExternalLink, checker)
    updater.add_checker(mwparserfromhell.nodes.Wikilink, checker)
    updater.add_checker(mwparserfromhell.nodes.Template, checker)

    db.sync_with_api(api)
    db.sync_revisions_content(api, mode="latest")
    db.update_parser_cache()

    try:
        updater.run()
    except (InteractiveQuit, KeyboardInterrupt):
        pass
