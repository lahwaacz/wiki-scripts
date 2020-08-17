#!/usr/bin/env python3

import sqlalchemy as sa

import ws.utils
from ws.client.api import ShortRecentChangesError
import ws.db.selects as selects

from .GrabberBase import GrabberBase

class GrabberProtectedTitles(GrabberBase):

    INSERT_PREDELETE_TABLES = ["protected_titles"]

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_pt = sa.dialects.postgresql.insert(db.protected_titles)

        self.sql = {
            ("insert", "protected_titles"):
                ins_pt.on_conflict_do_update(
                    index_elements=[
                        db.protected_titles.c.pt_namespace,
                        db.protected_titles.c.pt_title,
                    ],
                    set_={
                        "pt_level":  ins_pt.excluded.pt_level,
                        "pt_expiry": ins_pt.excluded.pt_expiry,
                    }),
            ("delete", "protected_titles"):
                db.protected_titles.delete().where(
                    (db.protected_titles.c.pt_namespace == sa.bindparam("b_pt_namespace")) &
                    (db.protected_titles.c.pt_title == sa.bindparam("b_pt_title"))),
        }

    def gen_inserts_from_pt_or_page(self, page):
        """
        :param page: an element from either titles=... or list=protectedtitles API query
        """
        title = self.db.Title(page["title"])

        if "protection" in page:
            # an element from titles=... query -> check if it's a protected title
            for pt in page["protection"]:
                assert pt["type"] == "create"
                db_entry = {
                    "pt_namespace": title.namespacenumber,
                    "pt_title": title.dbtitle(),
                    "pt_level": pt["level"],
                    "pt_expiry": pt["expiry"],
                }
                yield self.sql["insert", "protected_titles"], db_entry
        else:
            # an element from list=protectedtitles
            db_entry = {
                "pt_namespace": title.namespacenumber,
                "pt_title": title.dbtitle(),
                "pt_level": page["level"],
                "pt_expiry": page["expiry"],
            }
            yield self.sql["insert", "protected_titles"], db_entry

    def gen_deletes_from_page(self, page):
        # creating a page removes any corresponding rows from protected_titles
        # also delete rows for unprotected title
        if "missing" not in page or not page["protection"]:
            title = self.db.Title(page["title"])
            yield self.sql["delete", "protected_titles"], {"b_pt_namespace": title.namespacenumber, "b_pt_title": title.dbtitle()}

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
        rctitles = set()

        # Items in the recentchanges table are periodically purged according to
        # http://www.mediawiki.org/wiki/Manual:$wgRCMaxAge
        # By default the max age is 90 days: if a larger timespan is requested
        # here, it's very important to warn that the changes are not available
        if selects.oldest_rc_timestamp(self.db) > since:
            raise ShortRecentChangesError()

        rc_params = {
            "list": "recentchanges",
            "rctype": {"new", "log"},
            "rcprop": {"ids", "title", "loginfo"},
            "rcdir": "newer",
            "rcstart": since,
        }
        for change in self.db.query(rc_params):
            if change["type"] == "log":
                # note that pageid in recentchanges corresponds to log_page
                if change["logtype"] == "protect" and change["pageid"] == 0:
                    rctitles.add(change["title"])
            elif change["type"] == "new":
                rctitles.add(change["title"])

        return rctitles
