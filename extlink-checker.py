#! /usr/bin/env python3

import mwparserfromhell

from ws.checkers import ExtlinkStatusChecker
from ws.pageupdater import PageUpdater

class Updater(PageUpdater):
    force_interactive = True

if __name__ == "__main__":
    import ws.config
    import ws.logging
    from ws.interactive import InteractiveQuit

    argparser = ws.config.getArgParser(description="Parse all pages on the wiki and check the status of external links")
    Updater.set_argparser(argparser)
    # checkers don't have their own set_argparser method at the moment,
    # they just reuse API's and PageUpdater's options

    args = argparser.parse_args()

    # set up logging
    ws.logging.init(args)

    # create updater and add checkers
    updater = Updater.from_argparser(args)
    checker = ExtlinkStatusChecker(updater.api, None, timeout=args.connection_timeout, max_retries=args.connection_max_retries)
    updater.add_checker(mwparserfromhell.nodes.ExternalLink, checker)

    try:
        updater.run()
    except (InteractiveQuit, KeyboardInterrupt):
        pass
