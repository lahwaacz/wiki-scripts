#!/usr/bin/env python3

import sqlalchemy as sa

from ..SelectBase import SelectBase

__all__ = ["LinksHere"]

class LinksHere(SelectBase):
    """
    Find all pages that link to the given pages.
    """

    API_PREFIX = "lh"
    DB_PREFIX = "pl_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("prop", {"pageid", "title", "redirect"})

    @classmethod
    def sanitize_params(klass, params):
        assert set(params) <= {"prop", "namespace", "show", "continue", "limit"}
        assert params["prop"] <= {"pageid", "title", "redirect"}
        if "namespace" in params:
            assert isinstance(params["namespace"], (int, set))
        if "show" in params:
            assert isinstance(params["show"], set)
            assert params["show"] <= {"redirect", "!redirect"}

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        pl = self.db.pagelinks
        page = self.db.page
        src_page = self.db.page.alias()
        nss = self.db.namespace_starname.alias()

        tail = tail.outerjoin(pl, (pl.c.pl_namespace == page.c.page_namespace) &
                                  (pl.c.pl_title == page.c.page_title))
        tail = tail.outerjoin(src_page, src_page.c.page_id == pl.c.pl_from)
        if "title" in params["prop"]:
            tail = tail.outerjoin(nss, src_page.c.page_namespace == nss.c.nss_id)

        if "pageid" in params["prop"]:
            s = s.column(pl.c.pl_from.label("src_pageid"))
        else:
            # used to check for null entries from outer join
            s = s.column(pl.c.pl_from)
        if "title" in params["prop"]:
            s = s.column(src_page.c.page_namespace.label("src_namespace"))
            s = s.column(src_page.c.page_title.label("src_title"))
            s = s.column(nss.c.nss_name.label("src_nss_name"))
        if "redirect" in params["prop"]:
            s = s.column(src_page.c.page_is_redirect.label("src_page_is_redirect"))

        # restrictions
        if "namespace" in params:
            namespace = params["namespace"]
            if not isinstance(namespace, set):
                namespace = {namespace}
            s = s.where(src_page.c.page_namespace.in_(namespace))
        if "show" in params:
            if "redirect" in params["show"]:
                s = s.where(src_page.c.page_is_redirect == True)
            elif "!redirect" in params["show"]:
                s = s.where(src_page.c.page_is_redirect == False)

        # order by
        s = s.order_by(pl.c.pl_from.asc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if ("src_pageid" in row and row["src_pageid"] is not None) or ("pl_from" in row and row["pl_from"] is not None):
            linkshere = page.setdefault("linkshere", [])
            entry = {}
            if "src_pageid" in row:
                entry["pageid"] = row["src_pageid"]
            if "src_title" in row:
                entry["ns"] = row["src_namespace"]
                if row["src_nss_name"]:
                    entry["title"] = "{}:{}".format(row["src_nss_name"], row["src_title"])
                else:
                    entry["title"] = row["src_title"]
            if "src_page_is_redirect" in row:
                if row["src_page_is_redirect"]:
                    entry["redirect"] = ""
            # stupid MediaWiki defaults to empty lists, even though all entries containing something are dicts...
            if not entry:
                entry = []
            linkshere.append(entry)
