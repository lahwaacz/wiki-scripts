#!/usr/bin/env python3

import logging

from sqlalchemy import bindparam

import ws.utils
from ws.parser_helpers.title import Title
from ws.client.api import ShortRecentChangesError

from . import Grabber

logger = logging.getLogger(__name__)

class GrabberProtectedTitles(Grabber):

    TARGET_TABLES = ["protected_titles"]

    def __init__(self, api, db):
        super().__init__(api, db)

        self.sql = {
            ("insert", "protected_titles"):
                db.protected_titles.insert(mysql_on_duplicate_key_update=[
                    db.protected_titles.c.pt_level,
                    db.protected_titles.c.pt_expiry,
                ]),
            ("delete", "protected_titles"):
                db.protected_titles.delete().where(
                    (db.protected_titles.c.pt_namespace == bindparam("b_pt_namespace")) &
                    (db.protected_titles.c.pt_title == bindparam("b_pt_title"))),
        }

    def gen_inserts_from_pt_or_page(self, page):
        """
        :param page: an element from either titles=... or list=protectedtitles API query
        """
        title = Title(self.api, page["title"])

        if "protection" in page:
            # an element from titles=... query -> check if it's a protected title
            for pt in page["protection"]:
                assert pt["type"] == "create"
                db_entry = {
                    "pt_namespace": title.namespacenumber,
                    "pt_title": title.pagename,
                    "pt_level": pt["level"],
                    "pt_expiry": pt["expiry"],
                }
                yield self.sql["insert", "protected_titles"], db_entry
        else:
            # an element from list=protectedtitles
            db_entry = {
                "pt_namespace": title.namespacenumber,
                "pt_title": title.pagename,
                "pt_level": page["level"],
                "pt_expiry": page["expiry"],
            }
            yield self.sql["insert", "protected_titles"], db_entry

    def gen_deletes_from_page(self, page):
        # creating a page removes any corresponding rows from protected_titles
        # also delete rows for unprotected title
        if "missing" not in page or not page["protection"]:
            title = Title(self.api, page["title"])
            yield self.sql["delete", "protected_titles"], {"b_pt_namespace": title.namespacenumber, "b_pt_title": title.pagename}

    def gen_insert(self):
        pt_params = {
            "list": "protectedtitles",
            "ptlimit": "max",
            # MW incompatibility: we don't store the timestamp, userid, comment fields in the protected_titles database
#            "ptprop": "timestamp|userid|comment|expiry|level",
            "ptprop": "expiry|level",
        }
        for pt in self.api.list(pt_params):
            yield from self.gen_inserts_from_pt_or_page(pt)

    def gen_update(self, since):
        rctitles = self.get_rctitles(since)

        # pageids are better because all 500 fit into a single GET query, but we
        # need titles for non-existing pages. We could use POST to avoid hitting
        # the query-length limit, but POST can't be cached, so it's not
        # universal solution. Here we just assume that protecting titles is very
        # rare action so the query will always be short enough even with titles.
        # TODO: force POST only for this one query?
        if rctitles:
            logger.info("Fetching {} protected titles...".format(len(rctitles)))
            for chunk in ws.utils.iter_chunks(rctitles, self.api.max_ids_per_query):
                params = {
                    "action": "query",
                    "titles": "|".join(str(pageid) for pageid in chunk),
                    "prop": "info|pageprops",
                    "inprop": "protection",
                }
                for page in self.api.call_api(params)["pages"].values():
                    # make sure to skip inserts for existing pages
                    if "missing" in page:
                        yield from self.gen_inserts_from_pt_or_page(page)
                    yield from self.gen_deletes_from_page(page)

    def get_rctitles(self, since):
        since_f = ws.utils.format_date(since)
        rctitles = set()

        # Items in the recentchanges table are periodically purged according to
        # http://www.mediawiki.org/wiki/Manual:$wgRCMaxAge
        # By default the max age is 13 weeks: if a larger timespan is requested
        # here, it's very important to warn that the changes are not available
        if self.api.oldest_recent_change > since:
            raise ShortRecentChangesError()

        rc_params = {
            "action": "query",
            "list": "recentchanges",
            "rctype": "new|log",
            "rcprop": "ids|title|loginfo",
            "rclimit": "max",
            "rcdir": "newer",
            "rcstart": since_f,
        }
        for change in self.api.list(rc_params):
            if change["type"] == "log":
                if change["logtype"] == "protect" and change["pageid"] == 0:
                    rctitles.add(change["title"])
            elif change["type"] == "new":
                rctitles.add(change["title"])

        return rctitles
