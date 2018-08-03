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

    def add_props(self, s, tail, prop):
        pr = self.db.page_restrictions

        s.append_column(pr.c.pr_type)
        s.append_column(pr.c.pr_level)
        s.append_column(pr.c.pr_cascade)
        s.append_column(pr.c.pr_expiry)

        return s, tail

    # TODO: should be grouped per page
    @classmethod
    def db_to_api(klass, row):
        flags = {
            # TODO: check what MediaWiki produces
            "pr_type": "protectiontype",
            "pr_level": "protectionlevel",
            "pr_cascade": "cascade",
            "pr_expiry": "expiry",
            "page_id": "pageid",
            "page_namespace": "ns",
        }
        bool_flags = set("pr_cascade")
        # subset of flags for which 0 should be used instead of None
        zeroable_flags = set()

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

        # add special values
        if row["nss_name"]:
            api_entry["title"] = "{}:{}".format(row["nss_name"], row["page_title"])
        else:
            api_entry["title"] = row["page_title"]

        return api_entry
