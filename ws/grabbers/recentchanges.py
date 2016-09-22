#!/usr/bin/env python3

import random
import logging

from sqlalchemy import bindparam

import ws.utils
from ws.parser_helpers.title import Title
from ws.client.api import ShortRecentChangesError

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
            # TODO: delete too-old rows
#            ("delete", "recentchanges"):
        }

        self.rc_params = {
            "list": "recentchanges",
            "rcprop": "title|ids|user|userid|flags|patrolled|timestamp|comment|sizes|loginfo",
            "rclimit": "max",
        }

    def gen_inserts_from_rc(self, rc):
        title = Title(self.api, rc["title"])

        db_entry = {
            "rc_id": rc["rcid"],
            "rc_timestamp": rc["timestamp"],
            "rc_user": rc["userid"],
            "rc_user_text": rc["user"],
            "rc_namespace": rc["ns"],
            # title is stored without the namespace prefix
            "rc_title": title.pagename,
            "rc_comment": rc["comment"],
            "rc_minor": "minor" in rc,
            "rc_bot": "bot" in rc,
            "rc_new": "new" in rc,
            "rc_cur_id": rc["pageid"],
            "rc_this_oldid": rc["revid"],
            "rc_last_oldid": rc["old_revid"],
            "rc_type": rc["type"],
            "rc_patrolled": "patrolled" in rc,
            "rc_old_len": rc["oldlen"],
            "rc_new_len": rc["newlen"],
            # TODO: combine "userhidden" in rc, "commenthidden" in rc, "actionhidden" in rc
            # FIXME: we can't know if the revision text is deleted from list=recentchanges
#            "rc_deleted":
            "rc_logid": rc.get("logid"),
            "rc_log_type": rc.get("logtype"),
            "rc_log_action": rc.get("logaction"),
            # TODO: has to be serialized
#            "rc_params": rc.get("logparams"),
        }
        yield self.sql["insert", "recentchanges"], db_entry

    def gen_insert(self):
        for rc in self.api.list(self.rc_params):
            yield from self.gen_inserts_from_rc(rc)

    def gen_update(self, since):
        since_f = ws.utils.format_date(since)
        params = self.rc_params.copy()
        params["rcdir"] = "newer"
        params["rcstart"] = since_f

        for rc in self.api.list(params):
            yield from self.gen_inserts_from_rc(rc)

        # TODO: go through the new logevents and update previous patrolled changes etc.
        # TODO: issue DELETE to purge too-old rows
