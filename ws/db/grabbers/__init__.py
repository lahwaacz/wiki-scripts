#!/usr/bin/env python3

import logging
import time

from ws.db.grabbers.interwiki import GrabberInterwiki
from ws.db.grabbers.ipblocks import GrabberIPBlocks
from ws.db.grabbers.logging_ import GrabberLogging
from ws.db.grabbers.namespace import GrabberNamespaces
from ws.db.grabbers.page import GrabberPages
from ws.db.grabbers.protected_titles import GrabberProtectedTitles
from ws.db.grabbers.recentchanges import GrabberRecentChanges
from ws.db.grabbers.revision import GrabberRevisions
from ws.db.grabbers.tags import GrabberTags
from ws.db.grabbers.user import GrabberUsers
from ws.db.grabbers.usermerge import GrabberUserMerge

logger = logging.getLogger(__name__)

def synchronize(db, api, *, with_content=False, check_needs_update=True):
    time1 = time.time()

    # if no recent change has been added, it's safe to assume that the other tables are up to date as well
    g = GrabberRecentChanges(api, db)
    if check_needs_update is True and g.needs_update() is False:
        logger.info("No new changes since the last database synchronization.")
        return

    GrabberNamespaces(api, db).update()
    GrabberTags(api, db).update()
    GrabberRecentChanges(api, db).update()
    GrabberUsers(api, db).update()
    GrabberLogging(api, db).update()
    GrabberUserMerge(api, db).update()
    GrabberInterwiki(api, db).update()
    GrabberIPBlocks(api, db).update()
    GrabberPages(api, db).update()
    GrabberProtectedTitles(api, db).update()
    GrabberRevisions(api, db, with_content=with_content).update()

    time2 = time.time()
    logger.info("Synchronization of the database took {:.2f} seconds.".format(time2 - time1))
