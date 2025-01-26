#! /usr/bin/env python3

import datetime

import mwparserfromhell
import sqlalchemy as sa

from ws.client import API
from ws.interactive import require_login
from ws.db.database import Database
from ws.checkers import ExtlinkStatusUpdater, ExtlinkStatusChecker, LinkCheck, Domain
from ws.pageupdater import PageUpdater

class Updater(PageUpdater):
    force_interactive = True

def check(args, api, db):
    # synchronize changes from the wiki and update the parser cache
    require_login(api)
    db.sync_with_api(api)
    db.sync_revisions_content(api, mode="latest")
    db.update_parser_cache()

    # create the checker
    checker = ExtlinkStatusChecker(db, timeout=args.connection_timeout, max_retries=args.connection_max_retries)

    # copy URLs from the externallinks table to the ws_link_check table
    checker.transfer_urls_from_parser_cache()

    # select links to update
    s = sa.select(LinkCheck).join(Domain).where(
        LinkCheck.last_check.is_(None)
        | (LinkCheck.last_check < datetime.datetime.utcnow() - datetime.timedelta(days=7))
        | LinkCheck.http_status.in_({406, 429})
#        | Domain.resolved.is_(False)
    )
    checker.check(s)

def update(args, api, db):
    # create updater and add checkers
    updater = Updater.from_argparser(args, api)
    checker = ExtlinkStatusUpdater(api, db, timeout=args.connection_timeout, max_retries=args.connection_max_retries)
    updater.add_checker(mwparserfromhell.nodes.ExternalLink, checker)

    try:
        updater.run()
    except (InteractiveQuit, KeyboardInterrupt):
        pass

if __name__ == "__main__":
    import ws.config
    from ws.interactive import InteractiveQuit

    argparser = ws.config.getArgParser(description="Check the status of external links on the wiki")
    API.set_argparser(argparser)
    Database.set_argparser(argparser)
    Updater.set_argparser(argparser)
    # checkers don't have their own set_argparser method at the moment,
    # they just reuse API's and PageUpdater's options

    # add parameter for the two modes of the script
    group = argparser.add_argument_group(title="Script parameters")
    group.add_argument("--mode", choices=["check", "update"], required=True,
        help="which mode to run: 1. 'check' takes URLs from the database and "
             "checks their status, 2. 'update' takes the check results from "
             "the database and applies them on the wiki")

    args = ws.config.parse_args(argparser)

    # create API and Database objects
    api = API.from_argparser(args)
    db = Database.from_argparser(args)

    if args.mode == "check":
        check(args, api, db)
    elif args.mode == "update":
        update(args, api, db)
