#!/usr/bin/env python3

import logging

import ws.utils
from ws.client.api import ShortRecentChangesError

from . import Grabber

logger = logging.getLogger(__name__)

# FIXME: keep all MediaWiki constants in one place
implicit_groups = {"*", "user"}


class GrabberUsers(Grabber):

    TARGET_TABLES = ["user", "user_groups"]

    def __init__(self, api, db):
        super().__init__(api, db)

        self.sql_constructs = {
            ("insert", "user"):
                db.user.insert(mysql_on_duplicate_key_update=[
                    db.user.c.user_name,
                    db.user.c.user_registration,
                    db.user.c.user_editcount,
                ]),
            ("insert", "user_groups"):
                # It would have been fine to use INSERT IGNORE here (probably
                # also specific to MySQL), but it generates a warning for every
                # ignored row.
                db.user_groups.insert(mysql_on_duplicate_key_update=[
                    db.user_groups.c.ug_group
                ]),
        }


    def gen(self, list_params):
        for user in self.api.list(list_params):
            # skip invalid users (the logs might point to non-existing users)
            if "invalid" in user or "missing" in user:
                logger.warning(
                    "Got an invalid username '{}' from the wiki server. "
                    "The row will not be deleted locally, since this should have "
                    "never happened. Blame MediaWiki for not using foreign key "
                    "constraints in their database.".format(user["name"]))
                continue

            db_entry = {
                "user_id": user["userid"],
                "user_name": user["name"],
                "user_registration": user["registration"],
                "user_editcount": user["editcount"],
            }
            yield "insert", "user", db_entry

            extra_groups = set(user["groups"]) - implicit_groups
            for group in extra_groups:
                db_entry = {
                    "ug_user": user["userid"],
                    "ug_group": group,
                }
                yield "insert", "user_groups", db_entry


    def gen_insert(self):
        list_params = {
            "list": "allusers",
            "aulimit": "max",
            "auprop": "groups|editcount|registration",
        }
        yield from self.gen(list_params)


    def gen_update(self, since):
        rcusers = self.get_rcusers(since)
        logger.info("Fetching properties of {} possibly modified user accounts...".format(len(rcusers)))
        for chunk in ws.utils.iter_chunks(rcusers, self.api.max_ids_per_query):
            list_params = {
                "list": "users",
                "ususers": "|".join(chunk),
                "usprop": "groups|editcount|registration",
            }
            yield from self.gen(list_params)


    def get_rcusers(self, since):
        """
        Find users whose properties may have changed since the last update.

        :param datetime.datetime since: timestamp of the last update
        :returns: a set of user names
        """
        since_f = ws.utils.format_date(since)
        rcusers = set()

        # Items in the recentchanges table are periodically purged according to
        # http://www.mediawiki.org/wiki/Manual:$wgRCMaxAge
        # By default the max age is 13 weeks: if a larger timespan is requested
        # here, it's very important to warn that the changes are not available
        if self.api.oldest_recent_change > since:
            raise ShortRecentChangesError()

        rc_params = {
            "action": "query",
            "list": "recentchanges",
            "rctype": "edit|new|log",
            "rcprop": "user|title|loginfo",
            "rclimit": "max",
            "rcdir": "newer",
            "rcstart": since_f,
        }
        for change in self.api.list(rc_params):
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
