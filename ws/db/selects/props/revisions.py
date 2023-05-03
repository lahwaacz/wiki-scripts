#!/usr/bin/env python3

import sqlalchemy as sa

import ws.db.mw_constants as mwconst

from ..SelectBase import SelectBase

__all__ = ["Revisions"]

class Revisions(SelectBase):

    API_PREFIX = "rv"
    DB_PREFIX = "rev_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("dir", "older")
        params.setdefault("prop", {"timestamp", "ids", "flags", "comment", "user"})

    # shared with lists.AllRevisions
    @classmethod
    def sanitize_common_params(klass, params):
        # sanitize timestamp limits
        assert params["dir"] in {"newer", "older"}
        if params["dir"] == "older":
            newest = params.get("start")
            oldest = params.get("end")
        else:
            newest = params.get("end")
            oldest = params.get("start")
        # None is uncomparable
        if oldest and newest:
            assert oldest < newest

        assert "user" not in params or "excludeuser" not in params

        # MW incompatibility: "parsedcomment" and "parsetree" props are not supported
        assert params["prop"] <= {"user", "userid", "comment", "flags", "timestamp", "ids", "size", "sha1", "tags", "content", "contentmodel"}

        if "content" in params["prop"] or "contentmodel" in params["prop"]:
            assert "slots" in params and params["slots"] == "main"

    @classmethod
    def sanitize_params(klass, params):
        # MW incompatibility: parameters related to content parsing are not supported (they are deprecated anyway)
        # TODO: rvtag
        assert set(params) <= {"start", "end", "dir", "user", "excludeuser", "prop", "limit", "continue",
                               "section", "slots"}
        klass.sanitize_common_params(params)


    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset, *, enum_rev_mode=True):
        rev = self.db.revision
        page = self.db.page
        if enum_rev_mode is True:
            return rev.outerjoin(pageset, rev.c.rev_page == page.c.page_id)
        return rev.outerjoin(pageset, (rev.c.rev_page == page.c.page_id) &
                                      (rev.c.rev_id == page.c.page_latest))

    def get_select_prop(self, s, tail, params):
        rev = self.db.revision

        prop = params["prop"]
        if "user" in prop:
            s = s.column(rev.c.rev_user_text)
        if "userid" in prop:
            s = s.column(rev.c.rev_user)
        if "comment" in prop:
            s = s.column(rev.c.rev_comment)
        if "flags" in prop:
            s = s.column(rev.c.rev_minor_edit)
        if "timestamp" in prop:
            s = s.column(rev.c.rev_timestamp)
        if "ids" in prop:
            s = s.column(rev.c.rev_id)
            s = s.column(rev.c.rev_parent_id)
        if "size" in prop:
            s = s.column(rev.c.rev_len)
        if "sha1" in prop:
            s = s.column(rev.c.rev_sha1)
        if "contentmodel" in prop:
            s = s.column(rev.c.rev_content_model)
            s = s.column(rev.c.rev_content_format)

        # joins
        if "content" in prop:
            tail = tail.outerjoin(self.db.text, rev.c.rev_text_id == self.db.text.c.old_id)
            s = s.column(self.db.text.c.old_text)
        if "tags" in prop:
            tag = self.db.tag
            tgrev = self.db.tagged_revision
            # aggregate all tag names corresponding to the same revision into an array
            # (basically 'SELECT tgrev_rev_id, array_agg(tag_name) FROM tag JOIN tagged_recentchange GROUP BY tgrev_rev_id')
            # TODO: make a materialized view for this
            tag_names = sa.select([tgrev.c.tgrev_rev_id,
                                   sa.func.array_agg(tag.c.tag_name).label("tag_names")]) \
                            .select_from(tag.join(tgrev, tag.c.tag_id == tgrev.c.tgrev_tag_id)) \
                            .group_by(tgrev.c.tgrev_rev_id) \
                            .cte("tag_names")
            tail = tail.outerjoin(tag_names, rev.c.rev_id == tag_names.c.tgrev_rev_id)
            s = s.column(tag_names.c.tag_names)

        # restrictions
        if params["dir"] == "older":
            newest = params.get("start")
            oldest = params.get("end")
        else:
            newest = params.get("end")
            oldest = params.get("start")
        if newest:
            s = s.where(rev.c.rev_timestamp <= newest)
        if oldest:
            s = s.where(rev.c.rev_timestamp >= oldest)
        if params.get("user"):
            s = s.where(rev.c.rev_user_text == params.get("user"))
        if params.get("excludeuser"):
            s = s.where(rev.c.rev_user_text != params.get("excludeuser"))

        # order by
        if params["dir"] == "older":
            s = s.order_by(rev.c.rev_timestamp.desc(), rev.c.rev_id.desc())
        else:
            s = s.order_by(rev.c.rev_timestamp.asc(), rev.c.rev_id.asc())

        return s, tail

    @classmethod
    def db_to_api(klass, row):
        flags = {
            "rev_id": "revid",
            "rev_parent_id": "parentid",
            "rev_timestamp": "timestamp",
            "rev_user": "userid",
            "rev_user_text": "user",
            "rev_comment": "comment",
            "rev_sha1": "sha1",
            "rev_len": "size",
            "page_id": "pageid",
            "page_namespace": "ns",
        }
        slot_flags = {
            "rev_content_model": "contentmodel",
            "rev_content_format": "contentformat",
            "old_text": "*",
        }
        bool_flags = {
            "rev_minor_edit": "minor",
        }
        # subset of flags for which 0 should be used instead of None
        zeroable_flags = {"rev_user", "rev_parent_id"}

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
            elif key in slot_flags:
                slot = api_entry.setdefault("slots", {"main": {}})["main"]
                api_key = slot_flags[key]
                if value is not None:
                    slot[api_key] = value
            elif key in bool_flags:
                if value:
                    api_key = bool_flags[key]
                    api_entry[api_key] = ""

        # add special values
        if row["nss_name"]:
            api_entry["title"] = "{}:{}".format(row["nss_name"], row["page_title"])
        else:
            api_entry["title"] = row["page_title"]
        if api_entry.get("userid") == 0:
            api_entry["anon"] = ""
        # parse rev_deleted
        if "rev_deleted" in row:
            if row["rev_deleted"] & mwconst.DELETED_TEXT:
                api_entry["sha1hidden"] = ""
                # TODO: when should texthidden be added? only when content is requested?
#                api_entry["texthidden"] = ""
            if row["rev_deleted"] & mwconst.DELETED_COMMENT:
                api_entry["commenthidden"] = ""
            if row["rev_deleted"] & mwconst.DELETED_USER:
                api_entry["userhidden"] = ""
            if row["rev_deleted"] & mwconst.DELETED_RESTRICTED:
                api_entry["suppressed"] = ""
        # set tags to [] instead of None
        if "tag_names" in row:
            api_entry["tags"] = row["tag_names"] or []
            api_entry["tags"].sort()

        return api_entry

    @classmethod
    def db_to_api_subentry(klass, page, row):
        subentries = page.setdefault("revisions", [])
        api_entry = klass.db_to_api(row)
        del api_entry["pageid"]
        del api_entry["ns"]
        del api_entry["title"]
        subentries.append(api_entry)
