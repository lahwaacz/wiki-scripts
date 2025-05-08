#!/usr/bin/env python3

import sqlalchemy as sa

import ws.db.mw_constants as mwconst

from .GrabberBase import GrabberBase


class GrabberLogging(GrabberBase):

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_logging = sa.dialects.postgresql.insert(db.logging)
        ins_tgle = sa.dialects.postgresql.insert(db.tagged_logevent)
        ins_tgrc = sa.dialects.postgresql.insert(db.tagged_recentchange)

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
                    tgle_tag_id=sa.select(db.tag.c.tag_id).scalar_subquery() \
                                    .where(db.tag.c.tag_name == sa.bindparam("b_tag_name"))) \
                    .on_conflict_do_nothing(),
            ("insert", "tagged_recentchange"):
                ins_tgrc.values(
                    tgrc_rc_id=sa.select(db.recentchanges.c.rc_id).scalar_subquery() \
                                    .where(db.recentchanges.c.rc_logid == sa.bindparam("b_log_id")),
                    tgrc_tag_id=sa.select(db.tag.c.tag_id).scalar_subquery() \
                                    .where(db.tag.c.tag_name == sa.bindparam("b_tag_name"))) \
                    .on_conflict_do_nothing(),
            ("delete", "tagged_logevent"):
                db.tagged_logevent.delete() \
                    .where(sa.and_(db.tagged_logevent.c.tgle_log_id == sa.bindparam("b_log_id"),
                                   db.tagged_logevent.c.tgle_tag_id == sa.select(db.tag.c.tag_id).scalar_subquery() \
                                            .where(db.tag.c.tag_name == sa.bindparam("b_tag_name")))),
            ("delete", "tagged_recentchange"):
                db.tagged_recentchange.delete() \
                    .where(sa.and_(db.tagged_recentchange.c.tgrc_rc_id == sa.select(db.recentchanges.c.rc_id).scalar_subquery() \
                                            .where(db.recentchanges.c.rc_logid == sa.bindparam("b_log_id")),
                                   db.tagged_recentchange.c.tgrc_tag_id == sa.select(db.tag.c.tag_id).scalar_subquery() \
                                            .where(db.tag.c.tag_name == sa.bindparam("b_tag_name")))),
            ("update", "log_deleted"):
                db.logging.update() \
                    .where(db.logging.c.log_id == sa.bindparam("b_log_id")),
        }

        self.le_params = {
            "list": "logevents",
            "leprop": "title|ids|type|user|userid|timestamp|comment|details|tags",
            "lelimit": "max",
        }

    def gen_inserts_from_logevent(self, logevent):
        title = self.db.Title(logevent["title"])

        log_deleted = 0
        if "actionhidden" in logevent:
            log_deleted |= mwconst.DELETED_ACTION
        if "commenthidden" in logevent:
            log_deleted |= mwconst.DELETED_COMMENT
        if "userhidden" in logevent:
            log_deleted |= mwconst.DELETED_USER
        if "suppressed" in logevent:
            log_deleted |= mwconst.DELETED_RESTRICTED

        # Do not use title.dbtitle:
        #   - Interwiki prefix has to be included due to old log entries from
        #     times when the current interwiki prefixes were not in place.
        #   - Section anchor has to be included due to old log entries,
        #     apparently MediaWiki allowed ``#`` in user names at some point.
        log_title = title.format(iwprefix=True, namespace=False, sectionname=True)
        # Hack for the introduction of a new namespace (if the namespace numbers
        # don't match, use logevent["title"] verbatim).
        if logevent["ns"] == 0 and title.namespacenumber != 0:
            log_title = logevent["title"]
        # it's not an interwiki prefix -> capitalize first letter
        log_title = log_title[0].upper() + log_title[1:]

        db_entry = {
            "log_id": logevent["logid"],
            "log_type": logevent["type"],
            "log_action": logevent["action"],
            "log_timestamp": logevent["timestamp"],
            # This assumes that anonymous users can't create log events, so all "0" from the API are from deleted users
            "log_user": logevent["userid"] or None,
            "log_user_text": logevent["user"],
            "log_namespace": logevent["ns"],
            "log_title": log_title,
            # 'logpage' can be different from 'pageid', e.g. if the page was deleted
            # in an old MediaWiki that did not preserve pageid and then restored
            "log_page": logevent["logpage"] or None,
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
        added_tags = {}
        removed_tags = {}

        for le in self.api.list(params):
            yield from self.gen_inserts_from_logevent(le)

            # save new deleted logevents
            if le["type"] == "delete" and le["action"] == "event":
                assert le["params"]["type"] == "logging"
                for logid in le["params"]["ids"]:
                    deleted_logevents[logid] = le["params"]["new"]["bitmask"]
            # save added/removed tags
            elif le["type"] == "tag" and le["action"] == "update":
                # skip tags for revisions
                if "logid" in le["params"]:
                    # Note: the type of logid is inconsistent, MW 1.42 started to return string instead of int
                    _logid = int(le["params"]["logid"])
                    _added = set(le["params"]["tagsAdded"])
                    _removed = set(le["params"]["tagsRemoved"])
                    assert _added & _removed == set()
                    for _tag in _added:
                        if _tag in removed_tags.get(_logid, set()):
                            removed_tags[_logid].remove(_tag)
                        # always keep the last action
                        added_tags.setdefault(_logid, set())
                        added_tags[_logid].add(_tag)
                    for _tag in _removed:
                        if _tag in added_tags.get(_logid, set()):
                            added_tags[_logid].remove(_tag)
                        # always keep the last action
                        removed_tags.setdefault(_logid, set())
                        removed_tags[_logid].add(_tag)

        # update log_deleted
        for logid, bitmask in deleted_logevents.items():
            yield self.sql["update", "log_deleted"], {"b_log_id": logid, "log_deleted": bitmask}

        # update tags
        for logid, added in added_tags.items():
            for tag in added:
                db_entry = {
                    "b_log_id": logid,
                    "b_tag_name": tag,
                }
                yield self.sql["insert", "tagged_logevent"], db_entry
                # check if it is a recent change and tag it as well
                with self.db.engine.connect() as conn:
                    result = conn.execute(sa.select(
                                sa.exists().where(self.db.recentchanges.c.rc_logid == logid)
                            ))
                    if result.fetchone()[0]:
                        yield self.sql["insert", "tagged_recentchange"], db_entry
        for logid, removed in removed_tags.items():
            for tag in removed:
                db_entry = {
                    "b_log_id": logid,
                    "b_tag_name": tag,
                }
                yield self.sql["delete", "tagged_logevent"], db_entry
                yield self.sql["delete", "tagged_recentchange"], db_entry
