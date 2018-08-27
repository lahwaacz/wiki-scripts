#!/usr/bin/env python3

import sqlalchemy as sa

import ws.db.mw_constants as mwconst

from .ListBase import ListBase

__all__ = ["AllUsers"]

class AllUsers(ListBase):

    API_PREFIX = "au"
    DB_PREFIX = "user_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("dir", "ascending")
        params.setdefault("prop", set())

    @classmethod
    def sanitize_params(klass, params):
        # MW incompatibility: unsupported parameters: rights, attachedwiki
        # TODO: MediaWiki does not seem to have a "continue" parameter for this module, WTF?
        assert set(params) <= {"from", "to", "dir", "prefix", "group", "excludegroup", "prop", "witheditsonly", "activeusers", "limit", "continue"}

        # sanitize limits
        assert params["dir"] in {"ascending", "descending"}
        if params["dir"] == "ascending":
            start = params.get("from")
            end = params.get("to")
        else:
            start = params.get("to")
            end = params.get("from")
        # None is uncomparable
        if start and end:
            assert start < end

        # group and excludegroup are mutually exclusive
        assert "group" not in params or "excludegroup" not in params

        # MW incompatibility: unsupported props: implicitgroups, rights, centralids
        assert params["prop"] <= {"blockinfo", "groups", "editcount", "registration"}

    def get_select(self, params):
        if {"prefix", "continue"} & set(params):
            raise NotImplementedError
        if "limit" in params and params["limit"] != "max":
            raise NotImplementedError

        user = self.db.user
        groups = self.db.user_groups
        ipb = self.db.ipblocks

        s = sa.select([user.c.user_id, user.c.user_name])

        prop = params["prop"]
        if "editcount" in prop:
            s.append_column(user.c.user_editcount)
        if "registration" in prop:
            s.append_column(user.c.user_registration)

        # joins
        tail = user
        if "blockinfo" in prop:
            tail = tail.outerjoin(ipb, user.c.user_id == ipb.c.ipb_user)
            s.append_column(ipb.c.ipb_by)
            s.append_column(ipb.c.ipb_by_text)
            s.append_column(ipb.c.ipb_timestamp)
            s.append_column(ipb.c.ipb_expiry)
            s.append_column(ipb.c.ipb_id)
            s.append_column(ipb.c.ipb_reason)
            s.append_column(ipb.c.ipb_deleted)
        if "groups" in prop or "group" in params or "excludegroup" in params:
            tail = tail.outerjoin(groups, user.c.user_id == groups.c.ug_user)
            s = s.group_by(*s.columns.values())
            user_groups = sa.func.array_agg(groups.c.ug_group).label("user_groups")
            s.append_column(user_groups)

        s = s.select_from(tail)

        # restrictions
        s = s.where(user.c.user_id > 0)
        if params["dir"] == "ascending":
            start = params.get("from")
            end = params.get("to")
        else:
            start = params.get("to")
            end = params.get("from")
        if start:
            s = s.where(user.c.user_name >= start)
        if end:
            s = s.where(user.c.user_name <= end)
        if "group" in params:
            s = s.where(params["group"] == sa.any_(user_groups))
        if "excludegroup" in params:
            s = s.where(sa.not_(params["group"] == sa.any_(user_groups)))
        if "witheditsonly" in params:
            s = s.where( (user.c.user_editcount != None) & (user.c.user_editcount > 0) )
        # TODO
#        if "activeusers" in params:

        # order by
        if params["dir"] == "ascending":
            s = s.order_by(user.c.user_name.asc())
        else:
            s = s.order_by(user.c.user_name.desc())

        return s

    @classmethod
    def db_to_api(klass, row):
        flags = {
            "user_id": "userid",
            "user_name": "name",
            "user_editcount": "editcount",
            "user_registration": "registration",
            "user_groups": "groups",
            "ipb_id": "blockid",
            "ipb_by": "blockedbyid",
            "ipb_by_text": "blockedby",
            "ipb_timestamp": "blockedtimestamp",
            "ipb_expiry": "blockexpiry",
            "ipb_reason": "blockreason",
        }
        bool_flags = {"ipb_deleted": "hidden"}
        # subset of flags for which 0 should be used instead of None
        zeroable_flags = {"user_editcount"}

        api_entry = {}
        for key, value in row.items():
            if key in flags:
                api_key = flags[key]
                # normal keys are not added if the value is None
                if value is not None:
                    api_entry[api_key] = value
                # some keys produce 0 instead of None
                elif key in zeroable_flags:
                    api_entry[api_key] = 0
            elif key in bool_flags:
                if value:
                    api_key = bool_flags[key]
                    api_entry[api_key] = ""

        if "user_groups" in row:
            groups = api_entry["groups"]
            # "null::array" in SQL is converted to "[None]" in Python
            if groups == [None]:
                groups.pop()
            # add some implicit groups
            # TODO: depends on site configuration
            groups += ["*", "user"]

        # make sure that even empty registration is returned
        api_entry.setdefault("registration", None)

        return api_entry
