#!/usr/bin/env python3

import logging

from ..SelectBase import SelectBase

logger = logging.getLogger(__name__)

__all__ = ["Images"]

class Images(SelectBase):
    """
    Returns all files contained on the given pages.
    """

    API_PREFIX = "im"
    DB_PREFIX = "il_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("dir", "ascending")

    @classmethod
    def sanitize_params(klass, params):
        assert set(params) <= {"images", "dir", "continue", "limit"}
        assert params["dir"] in {"ascending", "descending"}
        if "images" in params:
            assert isinstance(params["images"], (str, set))

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        il = self.db.imagelinks
        page = self.db.page
        target_page = self.db.page.alias()
        nss = self.db.namespace_starname.alias()

        tail = tail.outerjoin(il, page.c.page_id == il.c.il_from)
        tail = tail.outerjoin(target_page, (target_page.c.page_namespace == 6) &
                                           (il.c.il_to == target_page.c.page_title))
        tail = tail.outerjoin(nss, nss.c.nss_id == 6)

        s = s.column(il.c.il_to)
        s = s.column(nss.c.nss_name.label("target_nss_name"))

        # restrictions
        if "images" in params:
            images = params["images"]
            if not isinstance(images, set):
                images = {images}
            basenames = set()
            for title in images:
                title = self.db.Title(title)
                if title.namespacenumber != 6:
                    logger.warn("prop=images: title '{}' is not a file".format(title))
                basenames.add(title.pagename)
            s = s.where(il.c.il_to.in_(basenames))

        # order by
        if params["dir"] == "ascending":
            s = s.order_by(il.c.il_to.asc())
        else:
            s = s.order_by(il.c.il_to.desc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if row["il_to"] is not None:
            images = page.setdefault("images", [])
            title = "{}:{}".format(row["target_nss_name"], row["il_to"])
            entry = {
                "ns": 6,
                "title": title,
            }
            images.append(entry)
