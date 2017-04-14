#!/usr/bin/env python3

from sqlalchemy import bindparam

import ws.utils

from . import Grabber

class GrabberIPBlocks(Grabber):

    INSERT_PREDELETE_TABLES = ["ipblocks"]

    def __init__(self, api, db):
        super().__init__(api, db)

        self.sql = {
            ("insert", "ipblocks"):
                db.ipblocks.insert(
                    on_conflict_constraint=[db.ipblocks.c.ipb_id],
                    on_conflict_update=[
                        db.ipblocks.c.ipb_address,
                        db.ipblocks.c.ipb_user,
                        db.ipblocks.c.ipb_by,
                        db.ipblocks.c.ipb_by_text,
                        db.ipblocks.c.ipb_reason,
                        db.ipblocks.c.ipb_timestamp,
                        db.ipblocks.c.ipb_auto,
                        db.ipblocks.c.ipb_anon_only,
                        db.ipblocks.c.ipb_create_account,
                        db.ipblocks.c.ipb_enable_autoblock,
                        db.ipblocks.c.ipb_expiry,
                        db.ipblocks.c.ipb_range_start,
                        db.ipblocks.c.ipb_range_end,
                        db.ipblocks.c.ipb_deleted,
                        db.ipblocks.c.ipb_block_email,
                        db.ipblocks.c.ipb_allow_usertalk,
                        db.ipblocks.c.ipb_parent_block_id,
                    ]),
            ("delete", "ipblocks"):
                db.ipblocks.delete().where(db.ipblocks.c.ipb_address == bindparam("b_ipb_address")),
        }


    def gen(self, list_params):
        for block in self.api.list(list_params):
            # skip autoblocks
            if "automatic" in block:
                continue

            db_entry = {
                "ipb_id": block["id"],
                # this is actually the username (or IP for anonymous users)
                "ipb_address": block["user"],
                # this is the user ID
                "ipb_user": block["userid"] if block["userid"] else None,
                "ipb_by": block["byid"],
                "ipb_by_text": block["by"],
                "ipb_reason": block["reason"],
                "ipb_timestamp": block["timestamp"],
                "ipb_auto": "automatic" in block,
                "ipb_anon_only": "anononly" in block,
                "ipb_create_account": "nocreate" in block,
                "ipb_enable_autoblock": "autoblock" in block,
                "ipb_expiry": block["expiry"],
                # FIXME: MW defect: per-user blocks have empty IP range populated as
                # ipb_range_start == ipb_range_end == "0.0.0.0" -> should be NULL instead
                "ipb_range_start": block["rangestart"],
                "ipb_range_end": block["rangeend"],
                # TODO: this does not seem to be available from the API nor webui
                "ipb_deleted": 0,
                "ipb_block_email": "noemail" in block,
                "ipb_allow_usertalk": "allowusertalk" in block,
                # not available via the API (and set only by autoblocks anyway)
                "ipb_parent_block_id": None,
            }
            yield self.sql["insert", "ipblocks"], db_entry


    def gen_insert(self):
        list_params = {
            "list": "blocks",
            "bklimit": "max",
            "bkprop": "id|user|userid|by|byid|timestamp|expiry|reason|range|flags",
        }
        yield from self.gen(list_params)


    def gen_update(self, since):
        since_f = ws.utils.format_date(since)

        # new blocks since the last sync
        list_params = {
            "list": "blocks",
            "bklimit": "max",
            "bkprop": "id|user|userid|by|byid|timestamp|expiry|reason|range|flags",
            "bkdir": "newer",
            "bkstart": since_f,
        }
        yield from self.gen(list_params)

        # also examine the logs for possible reblocks or unblocks
        # TODO: this could be done after the logs are synced in the local database
        rcusers = set()
        for logevent in self.api.list(list="logevents", letype="block", leprop="title", lelimit="max", ledir="newer", lestart=since_f):
            # extract target user name
            username = logevent["title"].split(":", maxsplit=1)[1]
            rcusers.add(username)
        if not rcusers:
            raise StopIteration

        # a mapping of ipb_address to set of ipb_id keys
        rcblocks = {}

        del list_params["bkdir"]
        del list_params["bkstart"]
        for chunk in ws.utils.iter_chunks(rcusers, self.api.max_ids_per_query):
            list_params["bkusers"] = "|".join(chunk)

            # introspect the db_entry to handle unblocks
            for stmt, db_entry in self.gen(list_params):
                rcblocks.setdefault(db_entry["ipb_address"], set())
                rcblocks[db_entry["ipb_address"]].add(db_entry["ipb_id"])
                yield stmt, db_entry

        # delete blocks for users that were not present in the bkusers= list
        blocked_rcusers = set(rcblocks)
        for user in rcusers - blocked_rcusers:
            yield self.sql["delete", "ipblocks"], {"b_ipb_address": user}

        # handle partial unblocks (there is composite unique key)
        for user, ipb_ids in rcblocks.items():
            # we need to check a tuple of arbitrary length (i.e. the blocks
            # to keep), so the queries can't be grouped
            yield self.db.ipblocks.delete().where(
                    (self.db.ipblocks.c.ipb_address == user) &
                    self.db.ipblocks.c.ipb_id.notin_(ipb_ids))
