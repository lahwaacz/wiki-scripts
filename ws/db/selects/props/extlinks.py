#!/usr/bin/env python3

from ..SelectBase import SelectBase

__all__ = ["ExternalLinks"]

class ExternalLinks(SelectBase):
    """
    Returns all interwiki links from the given pages.
    """

    API_PREFIX = "el"
    DB_PREFIX = "el_"

    @classmethod
    def set_defaults(klass, params):
        pass

    @classmethod
    def sanitize_params(klass, params):
        # MW incompatibility: unsupported parameter: expandurl
        assert set(params) <= {"protocol", "query", "offset", "limit"}
        if "protocol" in params:
            assert isinstance(params["protocol"], str)
        if "query" in params:
            assert isinstance(params["query"], str)

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        el = self.db.externallinks
        page = self.db.page

        tail = tail.outerjoin(el, page.c.page_id == el.c.el_from)

        s = s.column(el.c.el_to)

        # restrictions
        if "protocol" in params:
            protocol = params["protocol"] + "://"
        else:
            protocol = "http://"
        if "query" in params:
            # TODO: MediaWiki does some normalization to match the el_to column
            query = params["query"]
        else:
            query = ""
        if "protocol" in params or "query" in params:
            s = s.where(el.c.el_to.like("{}%{}%".format(protocol, query)))

        # order by
        s = s.order_by(el.c.el_to.asc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if row["el_to"] is not None:
            extlinks = page.setdefault("extlinks", [])
            entry = {
                "*": row["el_to"],
            }
            extlinks.append(entry)
