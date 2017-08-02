#!/usr/bin/env python3

import logging

from sqlalchemy import bindparam

from ws.utils import value_or_none
from ws.parser_helpers.title import Title
import ws.db.mw_constants as mwconst

from . import Grabber

logger = logging.getLogger(__name__)

class GrabberLogging(Grabber):

    def __init__(self, api, db):
        super().__init__(api, db)

        self.sql = {
            ("insert", "logging"):
                db.logging.insert(
                    on_conflict_constraint=[db.logging.c.log_id],
                    on_conflict_update=[
                        # this should be the only column that may change in the table
                        db.logging.c.log_deleted,
                    ]),
        }

        self.le_params = {
            "list": "logevents",
            "leprop": "title|ids|type|user|userid|timestamp|comment|details",
            "lelimit": "max",
        }

    def gen_inserts_from_logevent(self, logevent):
        title = Title(self.api, logevent["title"])

        log_deleted = 0
        if "actionhidden" in logevent:
            log_deleted |= mwconst.DELETED_ACTION
        if "commenthidden" in logevent:
            log_deleted |= mwconst.DELETED_COMMENT
        if "userhidden" in logevent:
            log_deleted |= mwconst.DELETED_USER
        if "suppressed" in logevent:
            log_deleted |= mwconst.DELETED_RESTRICTED

        db_entry = {
            "log_id": logevent["logid"],
            "log_type": logevent["type"],
            "log_action": logevent["action"],
            "log_timestamp": logevent["timestamp"],
            # This assumes that anonymous users can't create log events, so all "0" from the API are from deleted users
            "log_user": value_or_none(logevent["userid"]),
            "log_user_text": logevent["user"],
            "log_namespace": logevent["ns"],
            "log_title": title.dbtitle(logevent["ns"]),
            # 'logpage' can be different from 'pageid', e.g. if the page was deleted
            # in an old MediaWiki that did not preserve pageid and then restored
            "log_page": value_or_none(logevent["logpage"]),
            "log_comment": logevent["comment"],
            "log_params": logevent["params"],
            "log_deleted": log_deleted,
        }
        yield self.sql["insert", "logging"], db_entry

    def gen_insert(self):
        for logevent in self.api.list(self.le_params):
            yield from self.gen_inserts_from_logevent(logevent)

    def gen_update(self, since):
        params = self.le_params.copy()
        params["ledir"] = "newer"
        params["lestart"] = since

        for logevent in self.api.list(params):
            yield from self.gen_inserts_from_logevent(logevent)

        # TODO: go through the new logevents and update log_deleted of previous logevents
