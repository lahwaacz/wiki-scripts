#!/usr/bin/env python3

import datetime
import logging

import ws.utils
from ws.client.api import ShortRecentChangesError

logger = logging.getLogger(__name__)

# FIXME: keep all MediaWiki constants in one place
implicit_groups = {"*", "user"}


def gen(api, list_params):
    for user in api.list(list_params):
        # skip invalid users (the logs might point to non-existing users)
        if "invalid" in user or "missing" in user:
            # TODO: issue DELETE or at least warning, since this should never happen
            continue

        db_entry = {
            "user_id": user["userid"],
            "user_name": user["name"],
            "user_registration": user["registration"],
            "user_editcount": user["editcount"],
        }
        yield db_entry

        extra_groups = set(user["groups"]) - implicit_groups
        for group in extra_groups:
            db_entry = {
                "ug_user": user["userid"], 
                "ug_group": group,
            }
            yield db_entry


def gen_insert(api):
    list_params = {
        "list": "allusers",
        "aulimit": "max",
        "auprop": "groups|editcount|registration",
    }
    yield from gen(api, list_params)


def gen_update(api, rcusers):
    logger.info("Fetching properties of {} possibly modified user accounts...".format(len(rcusers)))
    for chunk in ws.utils.iter_chunks(rcusers, api.max_ids_per_query):
        list_params = {
            "list": "users",
            "ususers": "|".join(chunk),
            "usprop": "groups|editcount|registration",
        }
        yield from gen(api, list_params)


def gen_rcusers(api, since):
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
    if api.oldest_recent_change > since:
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
    for change in api.list(rc_params):
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


def db_execute(db, gen):
    user_ins = db.user.insert(mysql_on_duplicate_key_update=[
                                db.user.c.user_name,
                                db.user.c.user_registration,
                                db.user.c.user_editcount,
                            ])
    # it would have been fine to use INSERT IGNORE here (also probably specific
    # to MySQL), but it generates a warning for every discarded row
    ug_ins = db.user_groups.insert(mysql_on_duplicate_key_update=[
                                db.user_groups.c.ug_group
                            ])

    for chunk in ws.utils.iter_chunks(gen, db.chunk_size):
        # separate according to target table
        user_entries = []
        user_groups_entries = []
        for entry in chunk:
            if "user_id" in entry:
                user_entries.append(entry)
            elif "ug_user" in entry:
                user_groups_entries.append(entry)
            else:  # pragma: no cover
                raise Exception

        with db.engine.begin() as conn:
            if user_entries:
                conn.execute(user_ins, user_entries)
            if user_groups_entries:
                conn.execute(ug_ins, user_groups_entries)


def insert(api, db):
    sync_timestamp = datetime.datetime.utcnow()

    gen = gen_insert(api)
    db_execute(db, gen)

    db.set_sync_timestamp(db.user, sync_timestamp)


def update(api, db):
    sync_timestamp = datetime.datetime.utcnow()
    since = db.get_sync_timestamp(db.user)
    if since is None:
        insert(api, db)
        return

    try:
        rcusers = set(gen_rcusers(api, since))
    except ShortRecentChangesError:
        logger.warning("The recent changes table on the wiki has been recently purged, starting from scratch.")
        insert(api, db)
        return

    if len(rcusers) > 0:
        gen = gen_update(api, rcusers)
        db_execute(db, gen)

        db.set_sync_timestamp(db.user, sync_timestamp)
