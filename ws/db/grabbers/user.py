#!/usr/bin/env python3

import datetime
import logging

import sqlalchemy as sa

import ws.db.selects as selects
import ws.utils
from ws.client.api import ShortRecentChangesError
from ws.db.mw_constants import implicit_groups

from .GrabberBase import GrabberBase

logger = logging.getLogger(__name__)

class GrabberUsers(GrabberBase):

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
            ("update", "user"):
                db.user.update()
                    .where(db.user.c.user_name == sa.bindparam("b_olduser")),
            ("insert", "user_groups"):
                ins_user_groups.on_conflict_do_nothing(),
            ("delete", "user_groups"):
                db.user_groups.delete().where(
                    db.user_groups.c.ug_user == sa.bindparam("b_ug_user")),
            ("update", "logging"):
                db.logging.update()
                    .where(db.logging.c.log_user_text == sa.bindparam("b_olduser")),
            ("update", "ipb"):
                db.ipblocks.update()
                    .where(db.ipblocks.c.ipb_by_text == sa.bindparam("b_olduser")),
            ("update", "archive"):
                db.archive.update()
                    .where(db.archive.c.ar_user_text == sa.bindparam("b_olduser")),
            ("update", "revision"):
                db.revision.update()
                    .where(db.revision.c.rev_user_text == sa.bindparam("b_olduser")),
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
            # FIXME: list=allusers does not have a groupmemberships parameter: https://phabricator.wikimedia.org/T218489
            if "groupmemberships" in user:
                expirations = dict((gm["group"], gm["expiry"]) for gm in user["groupmemberships"])
            else:
                expirations = dict()
            for group in extra_groups:
                expiry = expirations.get(group)
                if expiry == datetime.datetime.max.replace(tzinfo=datetime.UTC):
                    expiry = None
                db_entry = {
                    "ug_user": user["userid"],
                    "ug_group": group,
                    "ug_expiry": expiry,
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
        # create a user with user_id=0 to satisfy FK contraints (used for
        # anonymous edits, log events etc.)
        dummy = {
            "user_id": 0,
            "user_name": "Anonymous",
            # IMPORTANT: Make sure to specify `None`s here, because the used
            # columns are determined from the first value in a bulk insert. So
            # if they were not specified here, server default would apply even
            # if the following rows specified these columns.
            "user_registration": None,
            "user_editcount": None,
        }
        yield self.sql["insert", "user"], dummy

        list_params = {
            "list": "allusers",
            "aulimit": "max",
            # "groups" is needed just to catch autoconfirmed
            "auprop": "groups|groupmemberships|editcount|registration",
        }
        for user in self.api.list(list_params):
            yield from self.gen_inserts_from_user(user)


    def gen_update(self, since):
        # Items in the recentchanges table are periodically purged according to
        # http://www.mediawiki.org/wiki/Manual:$wgRCMaxAge
        # By default the max age is 90 days: if a larger timespan is requested
        # here, it's very important to warn that the changes are not available
        if selects.oldest_rc_timestamp(self.db) > since:
            raise ShortRecentChangesError()

        # users whose properties may have changed since the last update
        rcusers = set()
        # mapping of renamed users
        # (we rely on dict keeping the insertion order, this is a Python 3.7
        # feature: https://stackoverflow.com/a/39980744 )
        renamed_users = {}

        rc_params = {
            "list": "recentchanges",
            "rctype": {"edit", "new", "log"},
            "rcprop": {"user", "title", "loginfo"},
            "rcdir": "newer",
            "rcstart": since,
        }
        for change in self.db.query(rc_params):
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
            # collect renamed users
            elif change["type"] == "log" and change["logtype"] == "renameuser":
                olduser = change["logparams"]["olduser"]
                newuser = change["logparams"]["newuser"]
                renamed_users[olduser] = newuser

        # rename before handling rcusers
        for olduser, newuser in renamed_users.items():
            yield self.sql["update", "user"], {"b_olduser": olduser, "user_name": newuser}
            if olduser in rcusers:
                rcusers.remove(olduser)
            rcusers.add(newuser)

            # rename user in other tables
            # TODO: check if matching by user name rather than ID is robust enough
            yield self.sql["update", "logging"], {"b_olduser": olduser, "log_user_text": newuser}
            yield self.sql["update", "ipb"], {"b_olduser": olduser, "ipb_by_text": newuser}
            yield self.sql["update", "archive"], {"b_olduser": olduser, "ar_user_text": newuser}
            yield self.sql["update", "revision"], {"b_olduser": olduser, "rev_user_text": newuser}

        if rcusers:
            for chunk in ws.utils.iter_chunks(rcusers, self.api.max_ids_per_query):
                list_params = {
                    "list": "users",
                    "ususers": "|".join(chunk),
                    # "groups" is needed just to catch autoconfirmed
                    "usprop": "groups|groupmemberships|editcount|registration",
                }
                for user in self.api.list(list_params):
                    yield from self.gen_inserts_from_user(user)
                    yield from self.gen_deletes_from_user(user)

        # delete expired group memberships
        yield self.db.user_groups.delete().where(
                        self.db.user_groups.c.ug_expiry < datetime.datetime.now(datetime.UTC)
                    )
