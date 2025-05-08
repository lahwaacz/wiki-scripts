#!/usr/bin/env python3

import sqlalchemy as sa

import ws.db.selects as selects
import ws.utils

from .GrabberBase import GrabberBase


class GrabberPages(GrabberBase):

    INSERT_PREDELETE_TABLES = ["page", "page_props", "page_restrictions"]

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_page = sa.dialects.postgresql.insert(db.page)
        ins_page_props = sa.dialects.postgresql.insert(db.page_props)
        ins_page_restrictions = sa.dialects.postgresql.insert(db.page_restrictions)

        self.sql = {
            ("insert", "page"):
                ins_page.on_conflict_do_update(
                    constraint=db.page.primary_key,
                    set_={
                        "page_namespace":     ins_page.excluded.page_namespace,
                        "page_title":         ins_page.excluded.page_title,
                        "page_is_redirect":   ins_page.excluded.page_is_redirect,
                        "page_is_new":        ins_page.excluded.page_is_new,
                        "page_touched":       ins_page.excluded.page_touched,
                        "page_links_updated": ins_page.excluded.page_links_updated,
                        "page_latest":        ins_page.excluded.page_latest,
                        "page_len":           ins_page.excluded.page_len,
                        "page_content_model": ins_page.excluded.page_content_model,
                        "page_lang":          ins_page.excluded.page_lang,
                    }),
            ("insert", "page_props"):
                ins_page_props.on_conflict_do_update(
                    index_elements=[
                        db.page_props.c.pp_page,
                        db.page_props.c.pp_propname,
                    ],
                    set_={
                        "pp_value": ins_page_props.excluded.pp_value,
                    }),
            ("insert", "page_restrictions"):
                ins_page_restrictions.on_conflict_do_update(
                    index_elements=[
                        db.page_restrictions.c.pr_page,
                        db.page_restrictions.c.pr_type,
                    ],
                    set_={
                        "pr_level":   ins_page_restrictions.excluded.pr_level,
                        "pr_cascade": ins_page_restrictions.excluded.pr_cascade,
                        "pr_user":    ins_page_restrictions.excluded.pr_user,
                        "pr_expiry":  ins_page_restrictions.excluded.pr_expiry,
                    }),
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
            ("delete", "deleted_recentchanges"):
                db.recentchanges.delete().where(
                    sa.and_(db.recentchanges.c.rc_logid.is_(None),
                            db.recentchanges.c.rc_cur_id.notin_(sa.select(db.page.c.page_id).scalar_subquery())
                    )),
            ("update", "page_name"):
                db.page.update().where(
                        db.page.c.page_id == sa.bindparam("b_page_id")
                    ).values(
                        page_namespace=sa.bindparam("b_new_namespace"),
                        page_title=sa.bindparam("b_new_title"),
                    ),
        }

        # build query to move data from the revision table into archive
        deleted_revision = db.revision.delete() \
            .where(db.revision.c.rev_page == sa.bindparam("b_rev_page")) \
            .returning(*db.revision.c._all_columns) \
            .cte("deleted_revision")
        columns = [
            db.page.c.page_namespace,
            db.page.c.page_title,
            deleted_revision.c.rev_id,
            deleted_revision.c.rev_page,
            deleted_revision.c.rev_text_id,
            deleted_revision.c.rev_comment,
            deleted_revision.c.rev_user,
            deleted_revision.c.rev_user_text,
            deleted_revision.c.rev_timestamp,
            deleted_revision.c.rev_minor_edit,
            deleted_revision.c.rev_deleted,
            deleted_revision.c.rev_len,
            deleted_revision.c.rev_parent_id,
            deleted_revision.c.rev_sha1,
            deleted_revision.c.rev_content_model,
            deleted_revision.c.rev_content_format,
        ]
        select = sa.select(*columns).select_from(
            deleted_revision.join(db.page, deleted_revision.c.rev_page == db.page.c.page_id)
        )
        insert = db.archive.insert().from_select(
            # populate all columns except ar_id
            db.archive.c._all_columns[1:],
            select
        )
        self.sql["move", "revision"] = insert

        # build query to move data from the tagged_revision table into tagged_archived_revision
        deleted_tagged_revision = db.tagged_revision.delete() \
            .where(db.tagged_revision.c.tgrev_rev_id.in_(
                        sa.select(db.revision.c.rev_id)
                            .select_from(db.revision)
                            .where(db.revision.c.rev_page == sa.bindparam("b_rev_page"))
                    )
                ) \
            .returning(*db.tagged_revision.c._all_columns) \
            .cte("deleted_tagged_revision")
        insert = db.tagged_archived_revision.insert().from_select(
            db.tagged_archived_revision.c._all_columns,
            deleted_tagged_revision.select()
        )
        self.sql["move", "tagged_revision"] = insert


    def gen_inserts_from_page(self, page):
        if "missing" in page:
            return

        title = self.db.Title(page["title"])

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
            # "missing" pages don't even have pageid, so there is nothing to do
            return

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
        # By default the max age is 90 days: if a larger timespan is requested
        # here, we need to look into the logging table instead of recentchanges.
        rc_oldest = selects.oldest_rc_timestamp(self.db)
        # if rc_oldest is None or rc_oldest > since:
        #     delete_early, moved, pages = self.get_logpages(since)
        # else:
        #     delete_early, moved, pages = self.get_rcpages(since)

        # some log events such as suppress/delete are not recorded in the
        # recentchanges table, fetching from logging is bulletproof
        delete_early, moved, pages = self.get_logpages(since)
        if rc_oldest is not None and rc_oldest <= since:
            pages |= self.get_rcpages(since)[2]

        keys = list(pages.keys())

        # Always delete beforehand, otherwise inserts might violate the
        # page_namespace_title unique constraint (for example when an automatic
        # or manual move-over-redirect has been made).
        for pageid in delete_early:
            # move tags first
            yield self.sql["move", "tagged_revision"], {"b_rev_page": pageid}
            # move relevant revisions from the revision table into archive
            yield self.sql["move", "revision"], {"b_rev_page": pageid}
            # deleted page - this will cause cascade deletion in
            # page_props and page_restrictions tables
            yield self.sql["delete", "page"], {"b_page_id": pageid}

        # Update all moved page titles beforehand, exactly in the order they
        # happened on the wiki, otherwise inserts might violate the
        # page_namespace_title unique constraint (for example when a page has
        # been moved multiple times since the last sync).
        for pageid, params in moved:
            title = self.db.Title(params["target_title"])
            yield self.sql["update", "page_name"], {
                    "b_page_id": pageid,
                    "b_new_namespace": params["target_ns"],
                    "b_new_title": title.dbtitle(params["target_ns"]),
                }

        if pages:
            for chunk in ws.utils.iter_chunks(pages, self.api.max_ids_per_query):
                params = {
                    "action": "query",
                    "pageids": "|".join(str(pageid) for pageid in chunk),
                    "prop": "info|pageprops",
                    "inprop": "protection",
                }
                pages = list(self.api.call_api(params)["pages"].values())

                # ordering of SQL inserts is important for moved pages, but MediaWiki does
                # not return ordered results for the pageids= parameter
                pages.sort(key=lambda page: keys.index(page["pageid"]))

                for page in pages:
                    # deletes first, otherwise edit + move over redirect would fail
                    yield from self.gen_deletes_from_page(page)
                    yield from self.gen_inserts_from_page(page)

        # get_logpages does not include normal edits, so we need to go through list=allpages again
        if rc_oldest is None or rc_oldest > since:
            yield from self.gen_insert()

        # delete recent changes whose pages were deleted
        yield self.sql["delete", "deleted_recentchanges"]

    def get_rcpages(self, since):
        deleted_pageids = set()
        moved = []
        # Using a dict rather than set to maintain insertion order (all values are None)
        rcpages = {}
        # Using a dict rather than set to maintain insertion order (all values are None)
        rctitles = {}

        rc_params = {
            "list": "recentchanges",
            "rctype": {"edit", "new", "log"},
            "rcprop": {"ids", "loginfo", "title"},
            "rcdir": "newer",
            "rcstart": since,
        }
        for change in self.db.query(rc_params):
            # add pageid for edits, new pages and target pages of log events
            # (this implicitly handles all protect, delete, import actions)
            if change["pageid"] > 0:
                rcpages[change["pageid"]] = None

            if change["type"] == "log":
                # Moving a page creates a "move" log event, but not a "new" log event for the
                # redirect, so we have to extract the new page ID manually.
                if change["logtype"] == "move":
                    rctitles[change["title"]] = None
                    moved.append((change["pageid"], change["logparams"]))
                elif change["logaction"] in {"delete_redir", "delete"}:
                    # note that pageid in recentchanges corresponds to log_page
                    deleted_pageids.add(change["pageid"])

        # resolve titles to IDs (we actually need to call the API, see above)
        if rctitles:
            for chunk in ws.utils.iter_chunks(rctitles.keys(), self.api.max_ids_per_query):
                params = {
                    "action": "query",
                    "titles": "|".join(chunk),
                }
                result = self.api.call_api(params)
                pages = list(result["pages"].values())

                # build a title normalization mapping - we need to be able to
                # map normalized titles to their original stored in rctitles
                normalized = {}
                for item in result.get("normalized", []):
                    normalized[item["to"]] = item["from"]

                # ordering of SQL inserts is important for moved pages, but MediaWiki does
                # not return ordered results for the titles= parameter
                keys = list(rctitles.keys())
                pages.sort(key=lambda page: keys.index(normalized.get(page["title"], page["title"])))

                for page in pages:
                    # skip missing pages (we don't detect "move without leaving a redirect" until here)
                    if "pageid" in page:
                        rcpages[page["pageid"]] = None

        return deleted_pageids, moved, rcpages

    def get_logpages(self, since):
        deleted_pageids = set()
        moved = []
        # Using a dict rather than set to maintain insertion order (all values are None)
        modified = {}

        le_params = {
            "list": "logevents",
            "leprop": {"type", "details", "ids"},
            "ledir": "newer",
            "lestart": since,
        }
        for le in self.db.query(le_params):
            if le["type"] in {"delete", "protect", "move", "import"}:
                if le["action"] in {"delete_redir", "delete"}:
                    deleted_pageids.add(le["logpage"])
                else:
                    modified[le["logpage"]] = None
                    if le["action"] in {"move", "move_redir"}:
                        moved.append((le["logpage"], le["params"]))
            elif le["type"] == "suppress" and le["action"] == "delete":
                deleted_pageids.add(le["logpage"])

        return deleted_pageids, moved, modified
