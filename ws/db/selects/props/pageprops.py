#!/usr/bin/env python3

from ..SelectBase import SelectBase

__all__ = ["PageProps"]

class PageProps(SelectBase):

    API_PREFIX = "pp"
    DB_PREFIX = "pp_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("prop", set())

    @classmethod
    def sanitize_params(klass, params):
        assert set(params) <= {"continue", "prop"}
        if "prop" in params:
            assert isinstance(params["prop"], set)

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        pp = self.db.page_props
        page = self.db.page

        # Note: nested select is needed because ppprop=invalid should not hide
        # rows with non-NULL in the pp_propname column.
        nested_sel = pp.select()
        if params["prop"]:
            nested_sel = nested_sel.where(pp.c.pp_propname.in_(params["prop"]))
        nested_sel = nested_sel.alias("requested_page_props")
        tail = tail.outerjoin(nested_sel, page.c.page_id == nested_sel.c.pp_page)

        s = s.column(nested_sel.c.pp_propname)
        s = s.column(nested_sel.c.pp_value)

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if row["pp_propname"] is not None:
            pageprops = page.setdefault("pageprops", {})
            pageprops[row["pp_propname"]] = row["pp_value"]
