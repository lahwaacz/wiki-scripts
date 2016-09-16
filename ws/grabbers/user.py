#!/usr/bin/env python3

import ws.utils

# FIXME: keep all MediaWiki constants in one place
implicit_groups = {"*", "user"}

def gen_init(api):
    blocks = set()
    for user in api.list(
                list="allusers",
                aulimit="max",
                auprop="blockinfo|groups|editcount|registration",
            ):

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


def insert(api, db):
    user_ins = db.user.insert()
    ug_ins = db.user_groups.insert()
    ipb_ins = db.ipblocks.insert()

    # must be catch-all because it may reference users that were not added yet
    # (API sorts by name, not ID...)
    ipblocks_entries = []

    for chunk in ws.utils.iter_chunks(gen_init(api), db.chunk_size):
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
            conn.execute(user_ins, user_entries)
            conn.execute(ug_ins, user_groups_entries)

    with db.engine.begin() as conn:
        conn.execute(ipb_ins, ipblocks_entries)
