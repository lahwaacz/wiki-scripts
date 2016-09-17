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

        if "blockid" in user:
            db_entry = {
                "ipb_id": user["blockid"],
                "ipb_user": user["userid"],
                "ipb_by": user["blockedbyid"],
                "ipb_by_text": user["blockedby"],
                "ipb_reason": user["blockreason"],
                "ipb_timestamp": user["blockedtimestamp"],
                "ipb_expiry": user["blockexpiry"],
            }
            yield db_entry


def gen_insert(api):
    list_params = {
        "list": "allusers",
        "aulimit": "max",
        "auprop": "blockinfo|groups|editcount|registration",
    }
    yield from gen(api, list_params)


def gen_update(api, rcusers):
    logger.info("Fetching properties of {} possibly modified user accounts...".format(len(rcusers)))
    for chunk in ws.utils.iter_chunks(rcusers, api.max_ids_per_query):
        list_params = {
            "list": "users",
            "ususers": "|".join(chunk),
            "usprop": "blockinfo|groups|editcount|registration",
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

    # also add the performer of any log entry
    for change in api.list(action="query", list="recentchanges", rctype="edit|log", rcprop="user|timestamp", rclimit="max", rcdir="newer", rcstart=since_f):
        rcusers.add(change["user"])

    # also examine log entries and add target user
    # (this is not available in recentchanges - although there is rctype=log
    # parameter, rcprop=loginfo provides only user IDs, which can't be used
    # in list=users)
    # there should be only three log event types that might change other users:
    #  - newusers (if user A creates account for user B, recent changes list
    #    only user A)
    #  - rights
    #  - block
    for letype in ["newusers", "rights", "block"]:
        for user in api.list(list="logevents", letype=letype, lelimit="max", ledir="newer", lestart=since_f):
            # extract target user name
            username = user["title"].split(":", maxsplit=1)[1]
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
    ipb_ins = db.ipblocks.insert(mysql_on_duplicate_key_update=[
                                db.ipblocks.c.ipb_user,
                                db.ipblocks.c.ipb_by,
                                db.ipblocks.c.ipb_by_text,
                                db.ipblocks.c.ipb_reason,
                                db.ipblocks.c.ipb_timestamp,
                                db.ipblocks.c.ipb_expiry,
                            ])

    # must be catch-all because it may reference users that were not added yet
    # (API sorts by name, not ID...)
    ipblocks_entries = []

    for chunk in ws.utils.iter_chunks(gen, db.chunk_size):
        # separate according to target table
        user_entries = []
        user_groups_entries = []
        for entry in chunk:
            if "user_id" in entry:
                user_entries.append(entry)
            elif "ug_user" in entry:
                user_groups_entries.append(entry)
            elif "ipb_user" in entry:
                ipblocks_entries.append(entry)
            else:  # pragma: no cover
                raise Exception

        with db.engine.begin() as conn:
            if user_entries:
                conn.execute(user_ins, user_entries)
            if user_groups_entries:
                conn.execute(ug_ins, user_groups_entries)

    with db.engine.begin() as conn:
        if ipblocks_entries:
            conn.execute(ipb_ins, ipblocks_entries)


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
        rcusers = list(gen_rcusers(api, since))
    except ShortRecentChangesError:
        logger.warning("The recent changes table on the wiki has been recently purged, starting from scratch. The recent edit count will not be available.")
        insert(api, db)
        return

    if len(rcusers) > 0:
        gen = gen_update(api, rcusers)
        db_execute(db, gen)

        db.set_sync_timestamp(db.user, sync_timestamp)
