#!/usr/bin/env python3

from ..SelectBase import SelectBase

__all__ = ["Redirects"]

class Redirects(SelectBase):
    """
    Returns all redirects to the given pages.
    """

    API_PREFIX = "rd"
    DB_PREFIX = "rd_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("prop", {"pageid", "title"})

    @classmethod
    def sanitize_params(klass, params):
        # MW incompatibility: unsupported parameters: prop, url
        assert set(params) <= {"prop", "namespace", "show", "continue", "limit"}
        assert params["prop"] <= {"pageid", "title", "fragment"}
        if "namespace" in params:
            assert isinstance(params["namespace"], (int, set))
        if "show" in params:
            assert isinstance(params["show"], set)
            assert params["show"] <= {"fragment", "!fragment"}

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        rd = self.db.redirect
        page = self.db.page
        src_page = self.db.page.alias()
        nss = self.db.namespace_starname.alias()

        tail = tail.outerjoin(rd, (rd.c.rd_namespace == page.c.page_namespace) &
                                  (rd.c.rd_title == page.c.page_title))
        tail = tail.outerjoin(src_page, src_page.c.page_id == rd.c.rd_from)
        if "title" in params["prop"]:
            tail = tail.outerjoin(nss, src_page.c.page_namespace == nss.c.nss_id)

        if "pageid" in params["prop"]:
            s = s.column(rd.c.rd_from.label("src_pageid"))
        else:
            # used to check for null entries from outer join
            s = s.column(rd.c.rd_from)
        if "title" in params["prop"]:
            s = s.column(src_page.c.page_namespace.label("src_namespace"))
            s = s.column(src_page.c.page_title.label("src_title"))
            s = s.column(nss.c.nss_name.label("src_nss_name"))
        if "fragment" in params["prop"]:
            s = s.column(rd.c.rd_fragment)

        # restrictions
        if "namespace" in params:
            namespace = params["namespace"]
            if not isinstance(namespace, set):
                namespace = {namespace}
            s = s.where(src_page.c.page_namespace.in_(namespace))
        if "show" in params:
            if "fragment" in params["show"]:
                s = s.where(rd.c.rd_fragment != None)
            elif "!fragment" in params["show"]:
                s = s.where(rd.c.rd_fragment == None)

        # order by
        s = s.order_by(rd.c.rd_from.asc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if ("src_pageid" in row and row["src_pageid"] is not None) or ("rd_from" in row and row["rd_from"] is not None):
            redirects = page.setdefault("redirects", [])
            entry = {}
            if "src_pageid" in row:
                entry["pageid"] = row["src_pageid"]
            if "src_title" in row:
                entry["ns"] = row["src_namespace"]
                if row["src_nss_name"]:
                    entry["title"] = "{}:{}".format(row["src_nss_name"], row["src_title"])
                else:
                    entry["title"] = row["src_title"]
            if "rd_fragment" in row and row["rd_fragment"] is not None:
                entry["fragment"] = row["rd_fragment"]
            # stupid MediaWiki defaults to empty lists, even though all entries containing something are dicts...
            if not entry:
                entry = []
            redirects.append(entry)
