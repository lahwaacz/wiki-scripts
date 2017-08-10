#!/usr/bin/env python3

import logging

import sqlalchemy as sa

from ws.utils import value_or_none
from ws.parser_helpers.title import Title
import ws.db.mw_constants as mwconst
import ws.db.selects.recentchanges as rcsel

from . import Grabber

logger = logging.getLogger(__name__)

class GrabberRecentChanges(Grabber):

    INSERT_PREDELETE_TABLES = ["recentchanges"]

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_rc = sa.dialects.postgresql.insert(db.recentchanges)
        ins_tgrc = sa.dialects.postgresql.insert(db.tagged_recentchange)

        self.sql = {
            ("insert", "recentchanges"):
                # updates are handled separately
                ins_rc.on_conflict_do_nothing(),
            ("update-patrolled", "recentchanges"):
                db.recentchanges.update() \
                        .values(rc_patrolled=True) \
                        .where(db.recentchanges.c.rc_this_oldid == sa.bindparam("_revid")),
            ("delete", "recentchanges"):
                db.recentchanges.delete().where(
                    db.recentchanges.c.rc_timestamp < sa.bindparam("rc_cutoff_timestamp")),
            ("insert", "tagged_recentchange"):
                ins_tgrc.values(
                    tgrc_rc_id=sa.bindparam("b_rc_id"),
                    tgrc_tag_id=sa.select([db.tag.c.tag_id]) \
                                    .select_from(db.tag) \
                                    .where(db.tag.c.tag_name == sa.bindparam("b_tag_name"))) \
                    .on_conflict_do_nothing(),
        }

        self.rc_params = {
            "list": "recentchanges",
            "rcprop": "title|ids|user|userid|flags|timestamp|comment|sizes|loginfo|sha1|tags",
            "rclimit": "max",
        }

        # patrol logs have to be fetched from the logevents list
        self.le_params = {
            "list": "logevents",
            "leaction": "patrol/patrol",
            "leprop": "type|details",
            "lelimit": "max",
        }

        if "patrol" in self.api.user.rights:
            self.rc_params["rcprop"] += "|patrolled"
        else:
            logger.warning("You need the 'patrol' right to request the patrolled flag. "
                           "Skipping it, but the sync will be incomplete.")

    def gen_inserts_from_rc(self, rc):
        title = Title(self.api, rc["title"])

        rc_deleted = 0
        if "sha1hidden" in rc:
            rc_deleted |= mwconst.DELETED_TEXT
        if "actionhidden" in rc:
            rc_deleted |= mwconst.DELETED_ACTION
        if "commenthidden" in rc:
            rc_deleted |= mwconst.DELETED_COMMENT
            # FIXME: either this or make the column nullable or require the "viewsuppressed" right for syncing
            rc.setdefault("comment", "")
        if "userhidden" in rc:
            rc_deleted |= mwconst.DELETED_USER
            # FIXME: either this or make the column nullable or require the "viewsuppressed" right for syncing
            rc.setdefault("user", "")
        if "suppressed" in rc:
            rc_deleted |= mwconst.DELETED_RESTRICTED

        db_entry = {
            "rc_id": rc["rcid"],
            "rc_timestamp": rc["timestamp"],
            "rc_user": rc.get("userid"),  # may be hidden due to rc_deleted
            "rc_user_text": rc["user"],  # may be hidden due to rc_deleted
            "rc_namespace": rc["ns"],
            "rc_title": title.dbtitle(rc["ns"]),
            "rc_comment": rc["comment"],  # may be hidden due to rc_deleted
            "rc_minor": "minor" in rc,
            "rc_bot": "bot" in rc,
            "rc_new": "new" in rc,
            "rc_cur_id": value_or_none(rc["pageid"]),
            "rc_this_oldid": value_or_none(rc["revid"]),
            "rc_last_oldid": value_or_none(rc["old_revid"]),
            "rc_type": rc["type"],
            "rc_patrolled": "patrolled" in rc,
            "rc_old_len": rc["oldlen"],
            "rc_new_len": rc["newlen"],
            "rc_deleted": rc_deleted,
            "rc_logid": rc.get("logid"),
            "rc_log_type": rc.get("logtype"),
            "rc_log_action": rc.get("logaction"),
            "rc_params": rc.get("logparams"),
        }
        yield self.sql["insert", "recentchanges"], db_entry

        for tag_name in rc.get("tags", []):
            db_entry = {
                "b_rc_id": rc["rcid"],
                "b_tag_name": tag_name,
            }
            yield self.sql["insert", "tagged_recentchange"], db_entry

    def gen_updates_from_le(self, logevent):
        if logevent["type"] == "patrol" and logevent["action"] == "patrol":
            db_entry = {
                "_revid": logevent["params"]["curid"],
            }
            yield self.sql["update-patrolled", "recentchanges"], db_entry

    def gen_insert(self):
        for rc in self.api.list(self.rc_params):
            yield from self.gen_inserts_from_rc(rc)

    def needs_update(self):
        """
        Returns ``True`` iff there are some recent changes to be fetched from the wiki.
        """
        return self.api.get_newest_rc_timestamp() > rcsel.newest_rc_timestamp(self.db)

    def gen_update(self, since):
        params = self.rc_params.copy()
        params["rcdir"] = "newer"
        params["rcstart"] = since

        for rc in self.api.list(params):
            yield from self.gen_inserts_from_rc(rc)

        # patrol logs are not recorded in the recentchanges table, so we need to
        # go through logging via the API, because it has not been synced yet
        params = self.le_params.copy()
        params["ledir"] = "newer"
        params["lestart"] = since

        for le in self.api.list(params):
            yield from self.gen_updates_from_le(le)

        # TODO: go through the new logevents in the local recentchanges table and update rc_deleted,
        # including the DELETED_TEXT value (which will be a MW incompatibility)

        # purge too-old rows
        yield self.sql["delete", "recentchanges"], {"rc_cutoff_timestamp": self.api.oldest_rc_timestamp}

        # FIXME: rolled-back edits are automatically patrolled, but there does not seem to be any way to detect this
