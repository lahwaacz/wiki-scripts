#!/usr/bin/env python3

import logging

from ..SelectBase import SelectBase

logger = logging.getLogger(__name__)

__all__ = ["Categories"]

class Categories(SelectBase):
    """
    List all categories the pages belong to.
    """

    API_PREFIX = "cl"
    DB_PREFIX = "cl_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("dir", "ascending")

    @classmethod
    def sanitize_params(klass, params):
        # TODO: implement prop and show parameters
        assert set(params) <= {"categories", "dir", "continue", "limit"}
        assert params["dir"] in {"ascending", "descending"}
        if "categories" in params:
            assert isinstance(params["categories"], (str, set))

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        cl = self.db.categorylinks
        page = self.db.page
        target_page = self.db.page.alias()
        nss = self.db.namespace_starname.alias()

        tail = tail.outerjoin(cl, page.c.page_id == cl.c.cl_from)
        tail = tail.outerjoin(target_page, (target_page.c.page_namespace == 14) &
                                           (cl.c.cl_to == target_page.c.page_title))
        tail = tail.outerjoin(nss, nss.c.nss_id == 14)

        s = s.column(cl.c.cl_to)
        s = s.column(nss.c.nss_name.label("target_nss_name"))

        # restrictions
        if "categories" in params:
            categories = params["images"]
            if not isinstance(images, set):
                images = {images}
            basenames = set()
            for category in categories:
                category = self.db.Title(category)
                if category.namespacenumber != 14:
                    logger.warn("prop=categories: title '{}' is not a category".format(category))
                basenames.add(title.pagename)
            s = s.where(cl.c.cl_to.in_(basenames))

        # order by
        if params["dir"] == "ascending":
            s = s.order_by(cl.c.cl_to.asc())
        else:
            s = s.order_by(cl.c.cl_to.desc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if row["cl_to"] is not None:
            categories = page.setdefault("categories", [])
            title = "{}:{}".format(row["target_nss_name"], row["cl_to"])
            entry = {
                "ns": 14,
                "title": title,
            }
            categories.append(entry)
