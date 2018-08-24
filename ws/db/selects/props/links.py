#!/usr/bin/env python3

import sqlalchemy as sa

from ..SelectBase import SelectBase

__all__ = ["Links"]

class Links(SelectBase):
    """
    Returns all links from the given pages.
    """

    API_PREFIX = "pl"
    DB_PREFIX = "pl_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("dir", "ascending")

    @classmethod
    def sanitize_params(klass, params):
        assert set(params) <= {"namespace", "titles", "dir", "continue", "limit"}
        assert params["dir"] in {"ascending", "descending"}
        if "namespace" in params:
            assert isinstance(params["namespace"], (int, set))
        if "titles" in params:
            assert isinstance(params["titles"], (str, set))

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        pl = self.db.pagelinks
        page = self.db.page
        target_page = self.db.page.alias()
        nss = self.db.namespace_starname.alias()

        tail = tail.outerjoin(pl, page.c.page_id == pl.c.pl_from)
        tail = tail.outerjoin(target_page, (pl.c.pl_namespace == target_page.c.page_namespace) &
                                           (pl.c.pl_title == target_page.c.page_title))
        tail = tail.outerjoin(nss, pl.c.pl_namespace == nss.c.nss_id)

        s = s.column(pl.c.pl_namespace)
        s = s.column(pl.c.pl_title)
        s = s.column(nss.c.nss_name.label("target_nss_name"))

        # restrictions
        if "namespace" in params:
            namespace = params["namespace"]
            if not isinstance(namespace, set):
                namespace = {namespace}
            s = s.where(pl.c.pl_namespace.in_(namespace))
        if "titles" in params:
            titles = params["titles"]
            if not isinstance(titles, set):
                titles = {titles}
            pairs = set()
            for title in titles:
                title = self.db.Title(title)
                pairs.add( (title.namespacenumber, title.pagename) )
            s = s.where(sa.tuple_(pl.c.pl_namespace, pl.c.pl_title).in_(pairs))

        # order by
        if params["dir"] == "ascending":
            s = s.order_by(pl.c.pl_namespace.asc(), pl.c.pl_title.asc())
        else:
            s = s.order_by(pl.c.pl_namespace.desc(), pl.c.pl_title.desc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if row["pl_title"] is not None:
            links = page.setdefault("links", [])
            if row["target_nss_name"]:
                title = "{}:{}".format(row["target_nss_name"], row["pl_title"])
            else:
                title = row["pl_title"]
            entry = {
                "ns": row["pl_namespace"],
                "title": title,
            }
            links.append(entry)
