#!/usr/bin/env python3

import random
import logging

import sqlalchemy as sa

import ws.utils
from ws.parser_helpers.title import Title
from ws.client.api import ShortRecentChangesError
from ws.db.selects import recentchanges, logevents

from . import Grabber

logger = logging.getLogger(__name__)

class GrabberPages(Grabber):

    INSERT_PREDELETE_TABLES = ["page", "page_props", "page_restrictions"]

    def __init__(self, api, db):
        super().__init__(api, db)

        self.sql = {
            ("insert", "page"):
                db.page.insert(
                    on_conflict_constraint=[db.page.c.page_id],
                    on_conflict_update=[
                        db.page.c.page_namespace,
                        db.page.c.page_title,
                        db.page.c.page_is_redirect,
                        db.page.c.page_is_new,
                        db.page.c.page_random,
                        db.page.c.page_touched,
                        db.page.c.page_links_updated,
                        db.page.c.page_latest,
                        db.page.c.page_len,
                        db.page.c.page_content_model,
                        db.page.c.page_lang,
                    ]),
            ("insert", "page_props"):
                db.page_props.insert(
                    on_conflict_constraint=[
                        db.page_props.c.pp_page,
                        db.page_props.c.pp_propname,
                    ],
                    on_conflict_update=[
                        db.page_props.c.pp_value,
                    ]),
            ("insert", "page_restrictions"):
                db.page_restrictions.insert(
                    on_conflict_constraint=[
                        db.page_restrictions.c.pr_page,
                        db.page_restrictions.c.pr_type,
                    ],
                    on_conflict_update=[
                        db.page_restrictions.c.pr_level,
                        db.page_restrictions.c.pr_cascade,
                        db.page_restrictions.c.pr_user,
                        db.page_restrictions.c.pr_expiry,
                    ]),
            ("delete", "page"):
                db.page.delete().where(db.page.c.page_id == sa.bindparam("b_page_id")),
            ("delete-but-one", "page_props"):
                db.page_props.delete().where(
                    (db.page_props.c.pp_page == sa.bindparam("b_pp_page")) &
                    (db.page_props.c.pp_propname != sa.bindparam("b_pp_propname"))),
            ("delete-all", "page_props"):
                db.page_props.delete().where(
                    db.page_props.c.pp_page == sa.bindparam("b_pp_page")),
            ("delete-but-one", "page_restrictions"):
                db.page_restrictions.delete().where(
                    (db.page_restrictions.c.pr_page == sa.bindparam("b_pr_page")) &
                    (db.page_restrictions.c.pr_type != sa.bindparam("b_pr_type"))),
            ("delete-all", "page_restrictions"):
                db.page_restrictions.delete().where(
                    db.page_restrictions.c.pr_page == sa.bindparam("b_pr_page")),
        }

        # build query to move data from the revision table into archive
        deleted_revisions = self.db.revision.delete() \
            .where(self.db.revision.c.rev_page == sa.bindparam("b_rev_page")) \
            .returning(*self.db.revision.c._all_columns) \
            .cte("deleted_revisions")
        columns = [
                self.db.page.c.page_namespace,
                self.db.page.c.page_title,
                deleted_revisions.c.rev_id,
                deleted_revisions.c.rev_page,
                deleted_revisions.c.rev_text_id,
                deleted_revisions.c.rev_comment,
                deleted_revisions.c.rev_user,
                deleted_revisions.c.rev_user_text,
                deleted_revisions.c.rev_timestamp,
                deleted_revisions.c.rev_minor_edit,
                deleted_revisions.c.rev_deleted,
                deleted_revisions.c.rev_len,
                deleted_revisions.c.rev_parent_id,
                deleted_revisions.c.rev_sha1,
                deleted_revisions.c.rev_content_model,
                deleted_revisions.c.rev_content_format,
            ]
        select = sa.select(columns).select_from(
                deleted_revisions.join(self.db.page, deleted_revisions.c.rev_page == self.db.page.c.page_id)
            )
        insert = self.db.archive.insert().from_select(
            # populate all columns except ar_id
            self.db.archive.c._all_columns[1:],
            select
        )
        self.sql["move", "revision"] = insert


    def gen_inserts_from_page(self, page):
        if "missing" in page:
            raise StopIteration

        title = Title(self.api, page["title"])

        # items for page table
        db_entry = {
            "page_id": page["pageid"],
            "page_namespace": page["ns"],
            "page_title": title.dbtitle(page["ns"]),
            "page_is_redirect": "redirect" in page,
            # Note that this is unrelated to marking pages in Special:NewPages as "patrolled",
            # this field means that the page has only one revision or has not been edited since
            # being restored - see https://www.mediawiki.org/wiki/Manual:Page_table#page_is_new
            "page_is_new": "new" in page,
            "page_random": random.random(),
            "page_touched": page["touched"],
            "page_links_updated": None,
            "page_latest": page["lastrevid"],
            "page_len": page["length"],
            "page_content_model": page["contentmodel"],
            "page_lang": page["pagelanguage"],
        }
        yield self.sql["insert", "page"], db_entry

        # items for page_props table
        for propname, value in page.get("pageprops", {}).items():
            db_entry = {
                "pp_page": page["pageid"],
                "pp_propname": propname,
                "pp_value": value,
                # TODO: how should this be populated?
#                "pp_sortkey":
            }
            yield self.sql["insert", "page_props"], db_entry

        # items for page_restrictions table
        for pr in page["protection"]:
            # drop entries caused by cascading protection
            if "source" not in pr:
                db_entry = {
                    "pr_page": page["pageid"],
                    "pr_type": pr["type"],
                    "pr_level": pr["level"],
                    "pr_cascade": "cascade" in pr,
                    "pr_user": None,    # unused
                    "pr_expiry": pr["expiry"],
                }
                yield self.sql["insert", "page_restrictions"], db_entry


    def gen_deletes_from_page(self, page):
        if "missing" in page:
            # move relevant revisions from the revision table into archive
            yield self.sql["move", "revision"], {"b_rev_page": page["pageid"]}

            # deleted page - this will cause cascade deletion in
            # page_props and page_restrictions tables
            yield self.sql["delete", "page"], {"b_page_id": page["pageid"]}
        else:
            # delete outdated props
            props = set(page.get("pageprops", {}))
            if props:
                if len(props) == 1:
                    # optimized query using != instead of notin_
                    yield self.sql["delete-but-one", "page_props"], {"b_pp_page": page["pageid"], "b_pp_propname": props.pop()}
                else:
                    # we need to check a tuple of arbitrary length (i.e. the props to keep),
                    # so the queries can't be grouped
                    yield self.db.page_props.delete().where(
                            (self.db.page_props.c.pp_page == page["pageid"]) &
                            self.db.page_props.c.pp_propname.notin_(props))
            else:
                # no props present - delete all rows with the pageid
                yield self.sql["delete-all", "page_props"], {"b_pp_page": page["pageid"]}

            # delete outdated restrictions
            applied = set(pr["type"] for pr in page["protection"])
            if applied:
                if len(applied) == 1:
                    # optimized query using != instead of notin_
                    yield self.sql["delete-but-one", "page_restrictions"], {"b_pr_page": page["pageid"], "b_pr_type": applied.pop()}
                else:
                    # we need to check a tuple of arbitrary length (i.e. the restrictions
                    # to keep), so the queries can't be grouped
                    yield self.db.page_restrictions.delete().where(
                            (self.db.page_restrictions.c.pr_page == page["pageid"]) &
                            self.db.page_restrictions.c.pr_type.notin_(applied))
            else:
                # no restrictions applied - delete all rows with the pageid
                yield self.sql["delete-all", "page_restrictions"], {"b_pr_page": page["pageid"]}


    def gen_insert(self):
        params = {
            "generator": "allpages",
            "gaplimit": "max",
            "prop": "info|pageprops",
            "inprop": "protection",
        }
        for ns in self.api.site.namespaces.keys():
            if ns < 0:
                continue
            params["gapnamespace"] = ns
            for page in self.api.generator(params):
                yield from self.gen_inserts_from_page(page)


    def gen_update(self, since):
        # Items in the recentchanges table are periodically purged according to
        # http://www.mediawiki.org/wiki/Manual:$wgRCMaxAge
        # By default the max age is 13 weeks: if a larger timespan is requested
        # here, we need to look into the logging table instead of recentchanges.
        rc_oldest = recentchanges.oldest_recent_change(self.db)
        if rc_oldest > since:
            pages = self.get_logpages(since)
        else:
            pages = self.get_rcpages(since)

        if pages:
            logger.info("Fetching properties of {} modified pages...".format(len(pages)))
            for chunk in ws.utils.iter_chunks(pages, self.api.max_ids_per_query):
                params = {
                    "action": "query",
                    "pageids": "|".join(str(pageid) for pageid in chunk),
                    "prop": "info|pageprops",
                    "inprop": "protection",
                }
                for page in self.api.call_api(params)["pages"].values():
                    yield from self.gen_inserts_from_page(page)
                    yield from self.gen_deletes_from_page(page)

        # get_logpages does not include normal edits, so we need to go through list=allpages again
        if rc_oldest > since:
            yield from self.gen_insert()


    def get_rcpages(self, since):
        since_f = ws.utils.format_date(since)
        rcpages = set()

        rc_params = {
            "type": {"edit", "new", "log"},
            "prop": {"ids"},
            "dir": "newer",
            "start": since_f,
        }
        for change in recentchanges.list(self.db, rc_params):
            # add pageid for edits, new pages and target pages of log events
            # (this implicitly handles all move, protect, delete actions)
            rcpages.add(change["pageid"])

            # TODO: examine logs (needs rcprop=loginfo)
            #   merge       (revision - or maybe page too?)
            #   import      (everything?)
            #   suppress    (everything?)
#            if change["type"] == "log":
#                if change["logtype"] == "merge":
#                    ...

        return rcpages

    def get_logpages(self, since):
        since_f = ws.utils.format_date(since)
        modified = set()

        le_params = {
            "prop": {"type", "details", "ids"},
            "dir": "newer",
            "start": since_f,
        }
        for le in logevents.list(self.db, le_params):
            if le["type"] in {"delete", "protect", "move"}:
                modified.add(le["logpage"])

        return modified
