#!/usr/bin/env python3

import sqlalchemy as sa

from ws.utils import value_or_none
from ws.parser_helpers.title import Title
import ws.db.mw_constants as mwconst

from . import Grabber

class GrabberLogging(Grabber):

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_logging = sa.dialects.postgresql.insert(db.logging)
        ins_tgle = sa.dialects.postgresql.insert(db.tagged_logevent)

        self.sql = {
            ("insert", "logging"):
                ins_logging.on_conflict_do_update(
                    index_elements=[db.logging.c.log_id],
                    set_={
                        # this should be the only column that may change in the table
                        "log_deleted": ins_logging.excluded.log_deleted,
                    }),
            ("insert", "tagged_logevent"):
                ins_tgle.values(
                    tgle_log_id=sa.bindparam("b_log_id"),
                    tgle_tag_id=sa.select([db.tag.c.tag_id]) \
                                    .select_from(db.tag) \
                                    .where(db.tag.c.tag_name == sa.bindparam("b_tag_name"))) \
                    .on_conflict_do_nothing(),
            ("update", "log_deleted"):
                db.logging.update() \
                    .where(db.logging.c.log_id == sa.bindparam("b_logid")),
        }

        self.le_params = {
            "list": "logevents",
            "leprop": "title|ids|type|user|userid|timestamp|comment|details|tags",
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

        for tag_name in logevent.get("tags", []):
            db_entry = {
                "b_log_id": logevent["logid"],
                "b_tag_name": tag_name,
            }
            yield self.sql["insert", "tagged_logevent"], db_entry

    def gen_insert(self):
        for logevent in self.api.list(self.le_params):
            yield from self.gen_inserts_from_logevent(logevent)

    def gen_update(self, since):
        params = self.le_params.copy()
        params["ledir"] = "newer"
        params["lestart"] = since

        deleted_logevents = {}

        for le in self.api.list(params):
            yield from self.gen_inserts_from_logevent(le)

            # save new deleted logevents
            if le["type"] == "delete" and le["action"] == "event":
                assert le["params"]["type"] == "logging"
                for logid in le["params"]["ids"]:
                    deleted_logevents[logid] = le["params"]["new"]["bitmask"]

        # update log_deleted
        for logid, bitmask in deleted_logevents.items():
            yield self.sql["update", "log_deleted"], {"b_logid": logid, "log_deleted": bitmask}
