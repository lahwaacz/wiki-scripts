#!/usr/bin/env python3

from ws.db.grabbers.namespace import GrabberNamespaces
from ws.db.grabbers.tags import GrabberTags
from ws.db.grabbers.interwiki import GrabberInterwiki
from ws.db.grabbers.recentchanges import GrabberRecentChanges
from ws.db.grabbers.user import GrabberUsers
from ws.db.grabbers.ipblocks import GrabberIPBlocks
from ws.db.grabbers.page import GrabberPages
from ws.db.grabbers.protected_titles import GrabberProtectedTitles
from ws.db.grabbers.revision import GrabberRevisions
from ws.db.grabbers.logging import GrabberLogging

def synchronize(db, api, *, with_content=False):
    # if no recent change has been added, it's safe to assume that the other tables are up to date as well
    g = GrabberRecentChanges(api, db)
    if g.needs_update() is False:
        print("No changes are needed according to the recentchanges table.")
        return

    GrabberNamespaces(api, db).update()
    GrabberTags(api, db).update()
    GrabberRecentChanges(api, db).update()
    GrabberUsers(api, db).update()
    GrabberLogging(api, db).update()
    GrabberInterwiki(api, db).update()
    GrabberIPBlocks(api, db).update()
    GrabberPages(api, db).update()
    GrabberProtectedTitles(api, db).update()
    GrabberRevisions(api, db, with_content=with_content).update()
