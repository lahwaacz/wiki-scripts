#!/usr/bin/env python3

"""
Note that MediaWiki provides protection information in the ``prop=info``
module, which is not suitable for wiki-scripts because except for protection
information it contains only duplicated (displaytitle) or computed (url,
talkid, subjectid) or inapplicable (watchers etc.) values. Therefore, we
implement just ``prop=protection`` for simplicity.
"""

from ..SelectBase import SelectBase

__all__ = ["Info"]

class Info(SelectBase):

    API_PREFIX = "in"
    DB_PREFIX = "pr_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("prop", set())

    @classmethod
    def sanitize_params(klass, params):
        assert set(params) <= {"prop"}
        if "prop" in params:
            # MW incompatibility: unsupported props: watched, watchers, visitingwatchers,
            # notificationtimestamp, readable, preload, varianttitles
            # TODO: investigate what varianttitles means
            assert params["prop"] <= {"protection", "url", "talkid", "subjectid", "displaytitle"}

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        page = self.db.page
        pr = self.db.page_restrictions
        pp = self.db.page_props

        # omnipresent info
        s = s.column(page.c.page_is_redirect)
        s = s.column(page.c.page_is_new)
        s = s.column(page.c.page_touched)
        s = s.column(page.c.page_len)
        s = s.column(page.c.page_latest)
        s = s.column(page.c.page_content_model)
        s = s.column(page.c.page_lang)

        prop = params["prop"]
        if "protection" in prop:
            tail = tail.outerjoin(pr, page.c.page_id == pr.c.pr_page)
            s = s.column(pr.c.pr_type)
            s = s.column(pr.c.pr_level)
            s = s.column(pr.c.pr_cascade)
            s = s.column(pr.c.pr_expiry)
        if "displaytitle" in prop:
            # Note: nested select is needed because ppprop=invalid should not hide
            # rows with non-NULL in the pp_propname column.
            nested_sel = pp.select().where(pp.c.pp_propname == "displaytitle")
            nested_sel = nested_sel.alias("requested_page_props")
            tail = tail.outerjoin(nested_sel, page.c.page_id == nested_sel.c.pp_page)
            s = s.column(nested_sel.c.pp_value)
        if "url" in prop or "talkid" in prop or "subjectid" in prop:
            raise NotImplementedError("inprop=url, inprop=talkid and inprop=subjectid parameters are not implemented yet")

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if row["page_is_redirect"]:
            page["redirect"] = ""
        if row["page_is_new"]:
            page["new"] = ""
        page["touched"] = row["page_touched"]
        page["length"] = row["page_len"]
        page["lastrevid"] = row["page_latest"]
        page["contentmodel"] = row["page_content_model"]
        page["pagelanguage"] = row["page_lang"]
        # TODO: refactor and complete language properties
        htmlcodes = {
            "zh-hans": "zh-Hans",
            "zh-hant": "zh-Hant",
        }
        page["pagelanguagehtmlcode"] = htmlcodes.get(page["pagelanguage"]) or page["pagelanguage"]
        rtl = {"ar", "he"}
        page["pagelanguagedir"] = "rtl" if page["pagelanguage"] in rtl else "ltr"

        if "pr_type" in row:
            # info about possible restriction types is always present in MediaWiki results
            # TODO: it should not be hardcoded here...
            page.setdefault("restrictiontypes", ["edit", "move"])

            protection = page.setdefault("protection", [])
            if row["pr_type"] is not None:
                pr = {
                    "type": row["pr_type"],
                    "level": row["pr_level"],
                }
                if row["pr_cascade"]:
                    pr["cascade"] = ""
                if row["pr_expiry"] is None:
                    pr["expiry"] = "indefinite"
                else:
                    pr["expiry"] = row["pr_expiry"]
                protection.append(pr)

        if "pp_value" in row:
            if row["pp_value"]:
                page["displaytitle"] = row["pp_value"]
            else:
                page["displaytitle"] = page["title"]
