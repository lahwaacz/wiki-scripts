#!/usr/bin/env python3

from ..SelectBase import SelectBase

__all__ = ["InterwikiLinks"]

class InterwikiLinks(SelectBase):
    """
    Returns all interwiki links from the given pages.
    """

    API_PREFIX = "iw"
    DB_PREFIX = "iwl_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("dir", "ascending")

    @classmethod
    def sanitize_params(klass, params):
        # MW incompatibility: unsupported parameters: prop, url
        assert set(params) <= {"prefix", "title", "dir", "continue", "limit"}
        assert params["dir"] in {"ascending", "descending"}
        # MW incompatibility: prefix and title can be used separately and they can be sets
        if "prefix" in params:
            assert isinstance(params["prefix"], (str, set))
        if "title" in params:
            assert isinstance(params["title"], (str, set))

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        iwl = self.db.iwlinks
        page = self.db.page

        tail = tail.outerjoin(iwl, page.c.page_id == iwl.c.iwl_from)

        s = s.column(iwl.c.iwl_prefix)
        s = s.column(iwl.c.iwl_title)

        # restrictions
        if "prefix" in params:
            prefix = params["prefix"]
            if not isinstance(prefix, set):
                prefix = {prefix}
            s = s.where(iwl.c.iwl_prefix.in_(prefix))
        if "title" in params:
            title = params["title"]
            if not isinstance(title, set):
                title = {title}
            s = s.where(iwl.c.iwl_title.in_(title))

        # order by
        if params["dir"] == "ascending":
            s = s.order_by(iwl.c.iwl_prefix, iwl.c.iwl_title.asc())
        else:
            s = s.order_by(iwl.c.iwl_prefix, iwl.c.iwl_title.desc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if row["iwl_title"] is not None:
            iwlinks = page.setdefault("iwlinks", [])
            entry = {
                "prefix": row["iwl_prefix"],
                "*": row["iwl_title"],
            }
            iwlinks.append(entry)
