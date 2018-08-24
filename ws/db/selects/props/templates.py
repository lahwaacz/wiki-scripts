#!/usr/bin/env python3

import sqlalchemy as sa

from ..SelectBase import SelectBase

__all__ = ["Templates"]

class Templates(SelectBase):
    """
    Returns all pages transcluded on the given pages.
    """

    API_PREFIX = "tl"
    DB_PREFIX = "tl_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("dir", "ascending")

    @classmethod
    def sanitize_params(klass, params):
        assert set(params) <= {"namespace", "templates", "dir", "continue", "limit"}
        assert params["dir"] in {"ascending", "descending"}
        if "namespace" in params:
            assert isinstance(params["namespace"], (int, set))
        if "templates" in params:
            assert isinstance(params["templates"], (str, set))

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        tl = self.db.templatelinks
        page = self.db.page
        target_page = self.db.page.alias()
        nss = self.db.namespace_starname.alias()

        tail = tail.outerjoin(tl, page.c.page_id == tl.c.tl_from)
        tail = tail.outerjoin(target_page, (tl.c.tl_namespace == target_page.c.page_namespace) &
                                           (tl.c.tl_title == target_page.c.page_title))
        tail = tail.outerjoin(nss, tl.c.tl_namespace == nss.c.nss_id)

        s = s.column(tl.c.tl_namespace)
        s = s.column(tl.c.tl_title)
        s = s.column(nss.c.nss_name.label("target_nss_name"))

        # restrictions
        if "namespace" in params:
            namespace = params["namespace"]
            if not isinstance(namespace, set):
                namespace = {namespace}
            s = s.where(tl.c.tl_namespace.in_(namespace))
        if "templates" in params:
            templates = params["templates"]
            if not isinstance(templates, set):
                templates = {templates}
            pairs = set()
            for template in templates:
                template = self.db.Title(template)
                pairs.add( (template.namespacenumber, template.pagename) )
            s = s.where(sa.tuple_(tl.c.tl_namespace, tl.c.tl_title).in_(pairs))

        # order by
        if params["dir"] == "ascending":
            s = s.order_by(tl.c.tl_namespace.asc(), tl.c.tl_title.asc())
        else:
            s = s.order_by(tl.c.tl_namespace.desc(), tl.c.tl_title.desc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if row["tl_title"] is not None:
            templates = page.setdefault("templates", [])
            if row["target_nss_name"]:
                title = "{}:{}".format(row["target_nss_name"], row["tl_title"])
            else:
                title = row["tl_title"]
            entry = {
                "ns": row["tl_namespace"],
                "title": title,
            }
            templates.append(entry)
