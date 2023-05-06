#! /usr/bin/env python3

import datetime

import mwparserfromhell
import sqlalchemy as sa

from ws.client import API
from ws.db.database import Database
from ws.checkers import ExtlinkStatusChecker, LinkCheck
from ws.pageupdater import PageUpdater

class Updater(PageUpdater):
    force_interactive = True

    # enable threading to overlap HTTP requests (NOTE: highly unreliable)
#    threads_update_page = 10

if __name__ == "__main__":
    import ws.config
    from ws.interactive import InteractiveQuit

    argparser = ws.config.getArgParser(description="Check the status of external links on the wiki")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)
    #Updater.set_argparser(argparser)
    # checkers don't have their own set_argparser method at the moment,
    # they just reuse API's and PageUpdater's options

    args = ws.config.parse_args(argparser)

    # create API and Database objects
    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    checker = ExtlinkStatusChecker(db, timeout=args.connection_timeout, max_retries=args.connection_max_retries)
    checker.transfer_urls_from_parser_cache()

    s = sa.select(LinkCheck).where(
        LinkCheck.last_check.is_(None)
        | (LinkCheck.last_check < datetime.datetime.utcnow() - datetime.timedelta(days=7))
        | LinkCheck.http_status.in_({406, 429})
    )
    checker.check(s)

    # create updater and add checkers
    #updater = Updater.from_argparser(args, api, db)
    #checker = ExtlinkStatusUpdater(api, db, timeout=args.connection_timeout, max_retries=args.connection_max_retries)
    #updater.add_checker(mwparserfromhell.nodes.ExternalLink, checker)


#    try:
#        updater.run()
#    except (InteractiveQuit, KeyboardInterrupt):
#        pass
