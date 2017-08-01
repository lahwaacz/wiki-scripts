#!/usr/bin/env python3

import logging

import sqlalchemy
from sqlalchemy.sql import func

import ws.utils
from ws.utils import format_date, value_or_none
from ws.parser_helpers.title import Title
from ws.db.selects import logevents

from . import Grabber

logger = logging.getLogger(__name__)

# TODO: allow syncing content independently from revisions
# TODO: are truncated results due to PHP cache reflected by changing the query-continuation parameter accordingly or do we actually lose some revisions?
class GrabberRevisions(Grabber):

    def __init__(self, api, db, with_content=False):
        super().__init__(api, db)
        self.with_content = with_content

        self.sql = {
            ("insert", "text"):
                db.text.insert(
                    on_conflict_constraint=[db.text.c.old_id],
                    on_conflict_update=[
                        db.text.c.old_text,
                        db.text.c.old_flags,
                    ]),
            ("insert", "revision"):
                db.revision.insert(
                    on_conflict_constraint=[db.revision.c.rev_id],
                    on_conflict_update=[
                        # this should be the only columns that may change in the table
                        db.revision.c.rev_deleted,
                        # TODO: merging might change rev_page and rev_parent_id
                    ]),
            ("insert", "archive"):
                db.archive.insert(
                    on_conflict_constraint=[db.archive.c.ar_rev_id],
                    on_conflict_update=[
                        # this should be the only columns that may change in the table
                        db.archive.c.ar_deleted,
                        # TODO: merging might change ar_page_id and rev_parent_id
                    ]),
        }

        props = "ids|timestamp|flags|user|userid|comment|size|sha1|contentmodel"
        if self.with_content is True:
            props += "|content"

        # TODO: tags
        self.arv_params = {
            "list": "allrevisions",
            "arvprop": props,
            "arvlimit": "max",
        }

        # TODO: tags
        self.adr_params = {
            "list": "alldeletedrevisions",
            "adrprop": props,
            "adrlimit": "max",
        }

        # TODO: check the permission to view deleted revisions
#        if "patrol" in self.api.user.rights:
#            self.rc_params["rcprop"] += "|patrolled"
#        else:
#            logger.warning("You need the 'patrol' right to request the patrolled flag. "
#                           "Skipping it, but the sync will be incomplete.")

    # TODO: text.old_id is auto-increment, but revision.rev_text_id has to be set accordingly. SQL should be able to do it automatically.
    def _get_text_id(self, conn):
        result = conn.execute(sqlalchemy.select( [func.max(self.db.text.c.old_id)] ))
        value = result.fetchone()[0]
        if value is None:
            value = 0
        while True:
            value += 1
            yield value

    def gen_text(self, rev, text_id):
        db_entry = {
            "old_id": text_id,
            "old_text": rev["*"],
            "old_flags": "utf-8",
        }
        yield self.sql["insert", "text"], db_entry

    def gen_revisions(self, page):
        for rev in page["revisions"]:
            db_entry = {
                "rev_id": rev["revid"],
                "rev_page": value_or_none(page.get("pageid")),
                "rev_comment": rev["comment"],
                "rev_user": rev["userid"],
                "rev_user_text": rev["user"],
                "rev_timestamp": rev["timestamp"],
                "rev_minor_edit": "minor" in rev,
                # TODO: rev_deleted
                "rev_len": rev["size"],
                # TODO: read on page history merging
                "rev_parent_id": rev.get("parentid"),
                "rev_sha1": rev["sha1"],
                "rev_content_model": rev["contentmodel"],
            }

            if self.with_content is True:
                text_id = next(text_id_gen)
                db_entry["rev_text_id"] = text_id
                yield from self.gen_text(rev, text_id)

            yield self.sql["insert", "revision"], db_entry

    def gen_deletedrevisions(self, page):
        title = Title(self.api, page["title"])
        for rev in page["revisions"]:
            db_entry = {
                "ar_namespace": page["ns"],
                "ar_title": title.dbtitle(page["ns"]),
                "ar_rev_id": rev["revid"],
                "ar_page_id": value_or_none(page["pageid"]),
                "ar_comment": rev["comment"],
                "ar_user": rev["userid"],
                "ar_user_text": rev["user"],
                "ar_timestamp": rev["timestamp"],
                "ar_minor_edit": "minor" in rev,
                # TODO: ar_deleted
                "ar_len": rev["size"],
                # ar_parent_id is not visible through API
                "ar_sha1": rev["sha1"],
                "ar_content_model": rev["contentmodel"],
            }

            if self.with_content is True:
                text_id = next(text_id_gen)
                db_entry["rev_text_id"] = text_id
                yield from self.gen_text(rev, text_id)

            yield self.sql["insert", "archive"], db_entry

    # TODO: write custom insert and update methods, use discontinued API queries and wrap each chunk in a separate transaction
    # TODO: generalize the above even for logging table

    def gen_insert(self):
        for page in self.api.list(self.arv_params):
            yield from self.gen_revisions(page)
        for page in self.api.list(self.adr_params):
            yield from self.gen_deletedrevisions(page)

    def gen_update(self, since):
        since_f = format_date(since)

        # TODO: make sure that the updates from the API don't create a duplicate row with a new ID in the text table

        arv_params = self.arv_params.copy()
        arv_params["arvdir"] = "newer"
        arv_params["arvstart"] = since_f
        for page in self.api.list(arv_params):
            yield from self.gen_revisions(page)

        # MW defect: it is not possible to use list=alldeletedrevisions to get all new
        # deleted revisions the same way as normal revisions, because adrstart can be
        # used only along with adruser (archive.ar_timestamp is not indexed separately).
        #
        # To work around this, we realize that new deleted revisions can appear only by
        # deleting an existing page, which creates an entry in the logging table. We
        # still need to query the API with prop=deletedrevisions to get even the
        # revisions that were created and deleted since the last sync.
        deleted_pages = set()

        le_params = {
            "type": "delete",
            "prop": {"type", "details"},
            "dir": "newer",
            "start": since_f,
        }
        for le in logevents.list(self.db, le_params):
            if logevent["type"] == "delete":
                deleted_pages.add(le["title"])

        # TODO: handle delete/undelete actions - move the rows between archive and revision tables
        # (in the archive table the rows might already be there due to the prop=deletedrevisions

        # TODO: update rev_deleted and ar_deleted
        # TODO: handle merge and unmerge
