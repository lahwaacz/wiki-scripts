#!/usr/bin/env python3

"""
Note that MediaWiki provides protection information in the ``prop=info``
module, which is not suitable for wiki-scripts because except for protection
information it contains only duplicated (displaytitle) or computed (url,
talkid, subjectid) or inapplicable (watchers etc.) values. Therefore, we
implement just ``prop=protection`` for simplicity.
"""

from ..SelectBase import SelectBase

__all__ = ["Protection"]

class Protection(SelectBase):

    API_PREFIX = "pr"
    DB_PREFIX = "pr_"

    @classmethod
    def set_defaults(klass, params):
        # for coherence with other prop modules
        params.setdefault("prop", set())

    @classmethod
    def sanitize_params(klass, params):
        assert set(params) <= {"prop"}
        if "prop" in params:
            assert params["prop"] == set()

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        pr = self.db.page_restrictions
        page = self.db.page
        return pageset.outerjoin(pr, page.c.page_id == pr.c.pr_page)

    def get_select_prop(self, s, tail, params):
        pr = self.db.page_restrictions

        s.append_column(pr.c.pr_type)
        s.append_column(pr.c.pr_level)
        s.append_column(pr.c.pr_cascade)
        s.append_column(pr.c.pr_expiry)

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
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
