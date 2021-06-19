#!/usr/bin/env python3

from ..SelectBase import SelectBase

__all__ = ["Sections"]

class Sections(SelectBase):
    """
    Returns all sections on the given pages.
    """

    API_PREFIX = "sec"
    DB_PREFIX = "sec_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("prop", {"number", "level", "title"})

    @classmethod
    def sanitize_params(klass, params):
        assert set(params) <= {"prop"}
        assert isinstance(params["prop"], set)
        assert params["prop"] <= {"number", "level", "title", "anchor"}

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        sec = self.db.section
        page = self.db.page

        tail = tail.outerjoin(sec, page.c.page_id == sec.c.sec_page)

        prop = params["prop"]
        if "number" in prop:
            s = s.column(sec.c.sec_number)
        if "level" in prop:
            s = s.column(sec.c.sec_level)
        if "title" in prop:
            s = s.column(sec.c.sec_title)
        if "anchor" in prop:
            s = s.column(sec.c.sec_anchor)

        # order by
        s = s.order_by(sec.c.sec_number.asc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        entry = {}
        if "sec_number" in row and row["sec_number"] is not None:
            entry["number"] = row["sec_number"]
        if "sec_level" in row and row["sec_level"] is not None:
            entry["level"] = row["sec_level"]
        if "sec_title" in row and row["sec_title"] is not None:
            entry["title"] = row["sec_title"]
        if "sec_anchor" in row and row["sec_anchor"] is not None:
            entry["anchor"] = row["sec_anchor"]
        if entry:
            sections = page.setdefault("sections", [])
            sections.append(entry)
