#!/usr/bin/env python3

import logging

import sqlalchemy as sa

import ws.utils
from ws.client.api import ShortRecentChangesError
from ws.db.mw_constants import implicit_groups
import ws.db.selects.recentchanges as rc

from . import Grabber

logger = logging.getLogger(__name__)

class GrabberUsers(Grabber):

    # We never delete from the user table, otherwise FK constraints might kick in.
    # If we find out that MediaWiki sometimes deletes from the user table, it
    # should be handled differently.
    INSERT_PREDELETE_TABLES = ["user_groups"]

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_user = sa.dialects.postgresql.insert(db.user)
        ins_user_groups = sa.dialects.postgresql.insert(db.user_groups)

        self.sql = {
            ("insert", "user"):
                ins_user.on_conflict_do_update(
                    index_elements=[db.user.c.user_id],
                    set_={
                        "user_name":         ins_user.excluded.user_name,
                        "user_registration": ins_user.excluded.user_registration,
                        "user_editcount":    ins_user.excluded.user_editcount,
                    }),
            ("insert", "user_groups"):
                ins_user_groups.on_conflict_do_nothing(),
            ("delete", "user_groups"):
                db.user_groups.delete().where(
                    db.user_groups.c.ug_user == sa.bindparam("b_ug_user")),
        }


    def gen_inserts_from_user(self, user):
        # skip invalid users (the logs might point to non-existing users)
        if "invalid" in user or "missing" in user:
            logger.warning(
                "Got an invalid username '{}' from the wiki server. "
                "Skipping INSERT.".format(user["name"]))
        else:
            db_entry = {
                "user_id": user["userid"],
                "user_name": user["name"],
                "user_registration": user["registration"],
                "user_editcount": user["editcount"],
            }
            yield self.sql["insert", "user"], db_entry

            extra_groups = set(user["groups"]) - implicit_groups
            for group in extra_groups:
                db_entry = {
                    "ug_user": user["userid"],
                    "ug_group": group,
                }
                yield self.sql["insert", "user_groups"], db_entry


    def gen_deletes_from_user(self, user):
        # skip invalid users (the logs might point to non-existing users)
        if "invalid" in user or "missing" in user:
            logger.warning(
                "Got an invalid username '{}' from the wiki server. "
                "The row will not be deleted locally, since this should have "
                "never happened. Blame MediaWiki for not using foreign key "
                "constraints in their database.".format(user["name"]))
        else:
            extra_groups = set(user["groups"]) - implicit_groups
            if extra_groups:
                # we need to check a tuple of arbitrary length (i.e. the groups
                # to keep), so the queries can't be grouped
                yield self.db.user_groups.delete().where(
                        (self.db.user_groups.c.ug_user == user["userid"]) &
                        self.db.user_groups.c.ug_group.notin_(extra_groups))
            else:
                # no groups - delete all rows with the userid
                yield self.sql["delete", "user_groups"], {"b_ug_user": user["userid"]}


    def gen_insert(self):
        # Create a dummy user to satisfy FK contraints, especially with revisions
        dummy = {
            "user_id": 0,
            "user_name": "__wiki_scripts_dummy_user__",
        }
        yield self.sql["insert", "user"], dummy

        list_params = {
            "list": "allusers",
            "aulimit": "max",
            "auprop": "groups|editcount|registration",
        }
        for user in self.api.list(list_params):
            yield from self.gen_inserts_from_user(user)


    def gen_update(self, since):
        rcusers = self.get_rcusers(since)
        if rcusers:
            logger.info("Fetching properties of {} possibly modified user accounts...".format(len(rcusers)))
            for chunk in ws.utils.iter_chunks(rcusers, self.api.max_ids_per_query):
                list_params = {
                    "list": "users",
                    "ususers": "|".join(chunk),
                    "usprop": "groups|editcount|registration",
                }
                for user in self.api.list(list_params):
                    yield from self.gen_inserts_from_user(user)


    def get_rcusers(self, since):
        """
        Find users whose properties may have changed since the last update.

        :param datetime.datetime since: timestamp of the last update
        :returns: a set of user names
        """
        rcusers = set()

        # Items in the recentchanges table are periodically purged according to
        # http://www.mediawiki.org/wiki/Manual:$wgRCMaxAge
        # By default the max age is 13 weeks: if a larger timespan is requested
        # here, it's very important to warn that the changes are not available
        if rc.oldest_rc_timestamp(self.db) > since:
            raise ShortRecentChangesError()

        rc_params = {
            "type": {"edit", "new", "log"},
            "prop": {"user", "title", "loginfo"},
            "dir": "newer",
            "start": since,
        }
        for change in rc.list(self.db, rc_params):
            # add the performer of the edit, newpage or log entry
            rcusers.add(change["user"])

            # also examine log entries and add target user
            # there should be only three log event types that might change other users:
            #  - newusers (if user A creates account for user B, recent changes list
            #    only user A)
            #  - rights
            if change["type"] == "log" and change["logtype"] in ["newusers", "rights"]:
                # extract target user name
                username = change["title"].split(":", maxsplit=1)[1]
                rcusers.add(username)

        return rcusers
