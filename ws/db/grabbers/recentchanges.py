#!/usr/bin/env python3

import logging

import sqlalchemy as sa

from ws.utils import value_or_none
import ws.db.mw_constants as mwconst
import ws.db.selects as selects

from .GrabberBase import GrabberBase

logger = logging.getLogger(__name__)

class GrabberRecentChanges(GrabberBase):

    INSERT_PREDELETE_TABLES = ["recentchanges"]

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_rc = sa.dialects.postgresql.insert(db.recentchanges)
        ins_tgrc = sa.dialects.postgresql.insert(db.tagged_recentchange)

        self.sql = {
            ("insert", "recentchanges"):
                # updates are handled separately
                ins_rc.on_conflict_do_nothing(),
            ("update", "rc_patrolled"):
                db.recentchanges.update() \
                        .values(rc_patrolled=True) \
                        .where(db.recentchanges.c.rc_this_oldid == sa.bindparam("b_rev_id")),
            ("update", "rc_deleted-b_revid"):
                db.recentchanges.update() \
                    .where(db.recentchanges.c.rc_this_oldid == sa.bindparam("b_rev_id")),
            ("update", "rc_deleted-b_logid"):
                db.recentchanges.update() \
                    .where(db.recentchanges.c.rc_logid == sa.bindparam("b_log_id")),
            ("delete", "recentchanges"):
                db.recentchanges.delete().where(
                    db.recentchanges.c.rc_timestamp < sa.bindparam("rc_cutoff_timestamp")),
            ("insert", "tagged_recentchange"):
                ins_tgrc.values(
                    tgrc_rc_id=sa.bindparam("b_rc_id"),
                    tgrc_tag_id=sa.select([db.tag.c.tag_id]).scalar_subquery() \
                                    .where(db.tag.c.tag_name == sa.bindparam("b_tag_name"))) \
                    .on_conflict_do_nothing(),
        }

        self.rc_params = {
            "list": "recentchanges",
            "rcprop": "title|ids|user|userid|flags|timestamp|comment|sizes|loginfo|sha1|tags",
            "rclimit": "max",
        }

        if "patrol" in self.api.user.rights:
            self.rc_params["rcprop"] += "|patrolled"
        else:
            logger.warning("You need the 'patrol' right to request the patrolled flag. "
                           "Skipping it, but the sync will be incomplete.")

    def gen_inserts_from_rc(self, rc):
        title = self.db.Title(rc["title"])

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

        rc_title = title.dbtitle(rc["ns"])
        # Hack for the introduction of a new namespace (if the namespace numbers
        # don't match, use rc["title"] verbatim).
        if rc["ns"] == 0 and title.namespacenumber != 0:
            rc_title = rc["title"]

        db_entry = {
            "rc_id": rc["rcid"],
            "rc_timestamp": rc["timestamp"],
            "rc_user": rc.get("userid"),  # may be hidden due to rc_deleted
            "rc_user_text": rc["user"],  # may be hidden due to rc_deleted
            "rc_namespace": rc["ns"],
            "rc_title": rc_title,
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

        # check logevents and and update rc_deleted of the past changes,
        # including the DELETED_TEXT value (which is a MW incompatibility)
        if rc.get("logtype") == "delete":
            if rc.get("logaction") == "revision":
                for revid in rc["logparams"]["ids"]:
                    yield self.sql["update", "rc_deleted-b_revid"], {"b_rev_id": revid, "rc_deleted": rc["logparams"]["new"]["bitmask"]}
            elif rc.get("logaction") == "event":
                for logid in rc["logparams"]["ids"]:
                    yield self.sql["update", "rc_deleted-b_logid"], {"b_log_id": logid, "rc_deleted": rc["logparams"]["new"]["bitmask"]}

    def gen_updates_from_le(self, logevent):
        if logevent["type"] == "patrol" and logevent["action"] == "patrol":
            yield self.sql["update", "rc_patrolled"], {"b_rev_id": logevent["params"]["curid"]}

    def gen_insert(self):
        for rc in self.api.list(self.rc_params):
            yield from self.gen_inserts_from_rc(rc)

    def needs_update(self):
        """
        Returns ``True`` iff there are some recent changes to be fetched from the wiki.
        """
        db_newest_rc_timestamp = selects.newest_rc_timestamp(self.db)
        if db_newest_rc_timestamp is None:
            return True
        return self.api.newest_rc_timestamp > db_newest_rc_timestamp

    def gen_update(self, since):
        params = self.rc_params.copy()
        params["rcdir"] = "newer"
        params["rcstart"] = since

        for rc in self.api.list(params):
            yield from self.gen_inserts_from_rc(rc)

        # patrol logs are not recorded in the recentchanges table, so we need to
        # go through logging via the API, because it has not been synced yet
        params = {
            "list": "logevents",
            "leaction": "patrol/patrol",
            "leprop": "type|details",
            "lelimit": "max",
            "ledir": "newer",
            "lestart": since,
        }
        for le in self.api.list(params):
            yield from self.gen_updates_from_le(le)

        # tag/update events are not recorded in the recentchanges table, so we
        # would need to go through list=logevents API query. But tags are not
        # necessary for the synchronization, so we tag the recent changes from
        # the logging and revision grabbers.

        # purge too-old rows
        yield self.sql["delete", "recentchanges"], {"rc_cutoff_timestamp": self.api.oldest_rc_timestamp}

        # FIXME: rolled-back edits are automatically patrolled, but there does not seem to be any way to detect this
