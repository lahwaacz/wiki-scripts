#!/usr/bin/env python3

import datetime

import sqlalchemy as sa

import ws.utils

from .GrabberBase import GrabberBase


class GrabberIPBlocks(GrabberBase):

    INSERT_PREDELETE_TABLES = ["ipblocks"]

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_ipblocks = sa.dialects.postgresql.insert(db.ipblocks)

        self.sql = {
            ("insert", "ipblocks"):
                ins_ipblocks.on_conflict_do_update(
                    constraint=db.ipblocks.primary_key,
                    set_={
                        "ipb_address":          ins_ipblocks.excluded.ipb_address,
                        "ipb_user":             ins_ipblocks.excluded.ipb_user,
                        "ipb_by":               ins_ipblocks.excluded.ipb_by,
                        "ipb_by_text":          ins_ipblocks.excluded.ipb_by_text,
                        "ipb_reason":           ins_ipblocks.excluded.ipb_reason,
                        "ipb_timestamp":        ins_ipblocks.excluded.ipb_timestamp,
                        "ipb_auto":             ins_ipblocks.excluded.ipb_auto,
                        "ipb_anon_only":        ins_ipblocks.excluded.ipb_anon_only,
                        "ipb_create_account":   ins_ipblocks.excluded.ipb_create_account,
                        "ipb_enable_autoblock": ins_ipblocks.excluded.ipb_enable_autoblock,
                        "ipb_expiry":           ins_ipblocks.excluded.ipb_expiry,
                        "ipb_range_start":      ins_ipblocks.excluded.ipb_range_start,
                        "ipb_range_end":        ins_ipblocks.excluded.ipb_range_end,
                        "ipb_deleted":          ins_ipblocks.excluded.ipb_deleted,
                        "ipb_block_email":      ins_ipblocks.excluded.ipb_block_email,
                        "ipb_allow_usertalk":   ins_ipblocks.excluded.ipb_allow_usertalk,
                        "ipb_parent_block_id":  ins_ipblocks.excluded.ipb_parent_block_id,
                    }),
            ("delete", "ipblocks"):
                db.ipblocks.delete().where(db.ipblocks.c.ipb_address == sa.bindparam("b_ipb_address")),
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
                # FIXME: MW defect: old per-user blocks have empty IP range populated as
                # ipb_range_start == ipb_range_end == "0.0.0.0" -> should be NULL instead
                "ipb_range_start": block.get("rangestart"),
                "ipb_range_end": block.get("rangeend"),
                "ipb_deleted": "hidden" in block,
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
        # remove expired blocks
        yield self.db.ipblocks.delete().where(self.db.ipblocks.c.ipb_expiry < datetime.datetime.utcnow())

        # new blocks since the last sync
        list_params = {
            "list": "blocks",
            "bklimit": "max",
            "bkprop": "id|user|userid|by|byid|timestamp|expiry|reason|range|flags",
            "bkdir": "newer",
            "bkstart": since,
        }
        yield from self.gen(list_params)

        # also examine the logs for possible reblocks or unblocks
        rcusers = set()
        le_params = {
            "list": "logevents",
            "letype": "block",
            "leprop": {"title"},
            "ledir": "newer",
            "lestart": since,
        }
        for logevent in self.db.query(le_params):
            # extract target user name
            username = logevent["title"].split(":", maxsplit=1)[1]
            rcusers.add(username)
        if not rcusers:
            return

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
