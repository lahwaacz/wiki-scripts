#! /usr/bin/env python3

import mwparserfromhell

from ws.checkers import ExtlinkReplacements
from ws.pageupdater import PageUpdater

class Updater(PageUpdater):
    force_interactive = True
    skip_pages = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # temporarily enable all namespaces (Arch's git URLs migration)
        #self.namespaces = [0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15, 3000, 3001]

if __name__ == "__main__":
    import ws.config
    import ws.logging
    from ws.interactive import InteractiveQuit

    argparser = ws.config.getArgParser(description="Parse all pages on the wiki and replace URLs")
    Updater.set_argparser(argparser)
    # checkers don't have their own set_argparser method at the moment,
    # they just reuse API's and PageUpdater's options

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    # create updater and add checkers
    updater = Updater.from_argparser(args)
    checker = ExtlinkReplacements(updater.api, None, timeout=args.connection_timeout, max_retries=args.connection_max_retries)
    updater.add_checker(mwparserfromhell.nodes.ExternalLink, checker)

    try:
        updater.run()
    except (InteractiveQuit, KeyboardInterrupt):
        pass
