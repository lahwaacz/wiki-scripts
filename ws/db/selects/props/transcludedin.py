#!/usr/bin/env python3

from ..SelectBase import SelectBase

__all__ = ["TranscludedIn"]

class TranscludedIn(SelectBase):
    """
    Find all pages that transclude the given pages.
    """

    API_PREFIX = "ti"
    DB_PREFIX = "tl_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("prop", {"pageid", "title", "redirect"})

    @classmethod
    def sanitize_params(klass, params):
        assert set(params) <= {"prop", "namespace", "show", "continue", "limit"}
        if "namespace" in params:
            assert isinstance(params["namespace"], (int, set))
        if "show" in params:
            assert params["show"] in {"redirect", "!redirect"}

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        tl = self.db.templatelinks
        page = self.db.page
        src_page = self.db.page.alias()
        nss = self.db.namespace_starname.alias()

        tail = tail.outerjoin(tl, (tl.c.tl_namespace == page.c.page_namespace) &
                                  (tl.c.tl_title == page.c.page_title))
        tail = tail.outerjoin(src_page, src_page.c.page_id == tl.c.tl_from)
        if "title" in params["prop"]:
            tail = tail.outerjoin(nss, src_page.c.page_namespace == nss.c.nss_id)

        if "pageid" in params["prop"]:
            s = s.column(tl.c.tl_from.label("src_pageid"))
        else:
            # used to check for null entries from outer join
            s = s.column(tl.c.tl_from)
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
            if params["show"] == "redirect":
                s = s.where(src_page.c.page_is_redirect.is_(True))
            else:
                s = s.where(src_page.c.page_is_redirect.is_(False))

        # order by
        s = s.order_by(tl.c.tl_from.asc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if ("src_pageid" in row and row["src_pageid"] is not None) or ("tl_from" in row and row["tl_from"] is not None):
            transcludedin = page.setdefault("transcludedin", [])
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
            transcludedin.append(entry)
