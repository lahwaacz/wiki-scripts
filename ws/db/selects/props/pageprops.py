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

    def add_props(self, s, tail, prop):
        pp = self.db.page_props
        page = self.db.page

        # Note: nested select is needed because ppprop=invalid should not hide
        # rows with non-NULL in the pp_propname column.
        nested_sel = pp.select()
        if prop:
            nested_sel = nested_sel.where(pp.c.pp_propname.in_(prop))
        nested_sel = nested_sel.alias("requested_page_props")
        tail = tail.outerjoin(nested_sel, page.c.page_id == nested_sel.c.pp_page)

        s.append_column(nested_sel.c.pp_propname)
        s.append_column(nested_sel.c.pp_value)

        return s, tail

    # TODO: should be grouped per page and properties turned into a Python dictionary
    @classmethod
    def db_to_api(klass, row):
        flags = {
            "pp_propname": "propname",
            "pp_value": "propvalue",
            "page_id": "pageid",
            "page_namespace": "ns",
        }
        bool_flags = set()
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
