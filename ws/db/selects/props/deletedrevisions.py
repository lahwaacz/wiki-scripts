#!/usr/bin/env python3

import sqlalchemy as sa

import ws.db.mw_constants as mwconst

from ..SelectBase import SelectBase

__all__ = ["DeletedRevisions"]

class DeletedRevisions(SelectBase):

    API_PREFIX = "drv"
    DB_PREFIX = "ar_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("dir", "older")
        params.setdefault("prop", {"timestamp", "ids", "flags", "comment", "user"})

    # shared with lists.AllDeletedRevisions
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
        assert set(params) <= {"start", "end", "dir", "user", "excludeuser", "prop", "limit", "continue",
                               "section", "generatetitles", "slots", "tag"}
        klass.sanitize_common_params(params)

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        ar = self.db.archive
        page = self.db.page
        return ar.outerjoin(pageset, (ar.c.ar_namespace == page.c.page_namespace) &
                                     (ar.c.ar_title == page.c.page_title))

    def get_select_prop(self, s, tail, params):
        ar = self.db.archive

        prop = params["prop"]
        if "user" in prop:
            s = s.column(ar.c.ar_user_text)
        if "userid" in prop:
            s = s.column(ar.c.ar_user)
        if "comment" in prop:
            s = s.column(ar.c.ar_comment)
        if "flags" in prop:
            s = s.column(ar.c.ar_minor_edit)
        if "timestamp" in prop:
            s = s.column(ar.c.ar_timestamp)
        if "ids" in prop:
            s = s.column(ar.c.ar_rev_id)
            s = s.column(ar.c.ar_parent_id)
        if "size" in prop:
            s = s.column(ar.c.ar_len)
        if "sha1" in prop:
            s = s.column(ar.c.ar_sha1)
        if "contentmodel" in prop:
            s = s.column(ar.c.ar_content_model)
            s = s.column(ar.c.ar_content_format)

        # joins
        if "content" in prop:
            tail = tail.outerjoin(self.db.text, ar.c.ar_text_id == self.db.text.c.old_id)
            s = s.column(self.db.text.c.old_text)
        if "tags" in prop:
            tag = self.db.tag
            tgar = self.db.tagged_archived_revision
            # aggregate all tag names corresponding to the same revision into an array
            # (basically 'SELECT tgar_rev_id, array_agg(tag_name) FROM tag JOIN tagged_recentchange GROUP BY tgar_rev_id')
            # TODO: make a materialized view for this
            tag_names = sa.select(tgar.c.tgar_rev_id,
                                  sa.func.array_agg(tag.c.tag_name).label("tag_names")) \
                            .select_from(tag.join(tgar, tag.c.tag_id == tgar.c.tgar_tag_id)) \
                            .group_by(tgar.c.tgar_rev_id) \
                            .cte("tag_names")
            tail = tail.outerjoin(tag_names, ar.c.ar_rev_id == tag_names.c.tgar_rev_id)
            s = s.column(tag_names.c.tag_names)
        if "tag" in params:
            tag = self.db.tag
            tgar = self.db.tagged_archived_revision
            tail = tail.join(tgar, ar.c.ar_rev_id == tgar.c.tgar_rev_id)
            s = s.where(tgar.c.tgar_tag_id == sa.select(tag.c.tag_id).where(tag.c.tag_name == params["tag"]))

        # restrictions
        if params["dir"] == "older":
            newest = params.get("start")
            oldest = params.get("end")
        else:
            newest = params.get("end")
            oldest = params.get("start")
        if newest:
            s = s.where(ar.c.ar_timestamp <= newest)
        if oldest:
            s = s.where(ar.c.ar_timestamp >= oldest)
        if "from" in params:
            s = s.where(ar.c.ar_title >= params["from"])
        if "to" in params:
            s = s.where(ar.c.ar_title <= params["to"])
        if params.get("user"):
            s = s.where(ar.c.ar_user_text == params.get("user"))
        if params.get("excludeuser"):
            s = s.where(ar.c.ar_user_text != params.get("excludeuser"))

        # order by
        if params["dir"] == "older":
            s = s.order_by(ar.c.ar_timestamp.desc(), ar.c.ar_rev_id.desc())
        else:
            s = s.order_by(ar.c.ar_timestamp.asc(), ar.c.ar_rev_id.asc())

        return s, tail

    @classmethod
    def db_to_api(klass, row):
        flags = {
            "ar_rev_id": "revid",
            "ar_parent_id": "parentid",
            "ar_timestamp": "timestamp",
            "ar_user": "userid",
            "ar_user_text": "user",
            "ar_comment": "comment",
            "ar_sha1": "sha1",
            "ar_len": "size",
            # pageid is not taken from ar_page_id, but from the existing page which might have
            # been created without undeleting previous revisions
            "page_id": "pageid",
            "ar_namespace": "ns",
        }
        slot_flags = {
            "ar_content_model": "contentmodel",
            "ar_content_format": "contentformat",
            "old_text": "*",
        }
        bool_flags = {
            "ar_minor_edit": "minor",
        }
        # subset of flags for which 0 should be used instead of None
        zeroable_flags = {"ar_user", "ar_parent_id", "page_id"}

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
            api_entry["title"] = "{}:{}".format(row["nss_name"], row["ar_title"])
        else:
            api_entry["title"] = row["ar_title"]
        if api_entry.get("userid") == 0:
            api_entry["anon"] = ""
        # parse ar_deleted
        if row["ar_deleted"] & mwconst.DELETED_TEXT:
            api_entry["sha1hidden"] = ""
        if row["ar_deleted"] & mwconst.DELETED_COMMENT:
            api_entry["commenthidden"] = ""
        if row["ar_deleted"] & mwconst.DELETED_USER:
            api_entry["userhidden"] = ""
        if row["ar_deleted"] & mwconst.DELETED_RESTRICTED:
            api_entry["suppressed"] = ""
        # set tags to [] instead of None
        if "tag_names" in row:
            api_entry["tags"] = row["tag_names"] or []
            api_entry["tags"].sort()

        return api_entry

    @classmethod
    def db_to_api_subentry(klass, page, row):
        subentries = page.setdefault("deletedrevisions", [])
        api_entry = klass.db_to_api(row)
        del api_entry["pageid"]
        del api_entry["ns"]
        del api_entry["title"]
        subentries.append(api_entry)
