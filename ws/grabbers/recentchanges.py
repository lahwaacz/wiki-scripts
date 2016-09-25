#!/usr/bin/env python3

import logging

from sqlalchemy import bindparam

from ws.utils import format_date, value_or_none
from ws.parser_helpers.title import Title
import ws.db.mw_constants as mwconst

from . import Grabber

logger = logging.getLogger(__name__)

class GrabberRecentChanges(Grabber):

    TARGET_TABLES = ["recentchanges"]

    def __init__(self, api, db):
        super().__init__(api, db)

        self.sql = {
            ("insert", "recentchanges"):
                db.recentchanges.insert(mysql_on_duplicate_key_update=[
                    # this should be the only columns that may change in the table
                    db.recentchanges.c.rc_new,
                    db.recentchanges.c.rc_patrolled,
                    db.recentchanges.c.rc_deleted,
                ]),
            ("delete", "recentchanges"):
                db.recentchanges.delete().where(
                    db.recentchanges.c.rc_timestamp < bindparam("rc_cutoff_timestamp"))
        }

        self.rc_params = {
            "list": "recentchanges",
            "rcprop": "title|ids|user|userid|flags|timestamp|comment|sizes|loginfo|sha1",
            "rclimit": "max",
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
        if "userhidden" in rc:
            rc_deleted |= mwconst.DELETED_USER
        if "suppressed" in rc:
            rc_deleted |= mwconst.DELETED_RESTRICTED

        db_entry = {
            "rc_id": rc["rcid"],
            "rc_timestamp": rc["timestamp"],
            "rc_user": value_or_none(rc["userid"]),
            "rc_user_text": rc["user"],
            "rc_namespace": rc["ns"],
            "rc_title": title.dbtitle(rc["ns"]),
            "rc_comment": rc["comment"],
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

    def gen_insert(self):
        for rc in self.api.list(self.rc_params):
            yield from self.gen_inserts_from_rc(rc)

    def gen_update(self, since):
        since_f = format_date(since)
        params = self.rc_params.copy()
        params["rcdir"] = "newer"
        params["rcstart"] = since_f

        for rc in self.api.list(params):
            yield from self.gen_inserts_from_rc(rc)

        # TODO: go through the new logevents and update previous patrolled changes etc.
        # and also the rc_deleted, including the DELETED_TEXT value (which will be a MW incompatibility)

        # purge too-old rows
        yield self.sql["delete", "recentchanges"], {"rc_cutoff_timestamp": format_date(self.api.oldest_recent_change)}
