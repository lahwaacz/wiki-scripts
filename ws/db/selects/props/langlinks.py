#!/usr/bin/env python3

from ..SelectBase import SelectBase

__all__ = ["LanguageLinks"]

class LanguageLinks(SelectBase):
    """
    Returns all interlanguage links from the given pages.
    """

    API_PREFIX = "ll"
    DB_PREFIX = "ll_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("dir", "ascending")

    @classmethod
    def sanitize_params(klass, params):
        # MW incompatibility: unsupported parameters: prop, inlanguagecode, url
        assert set(params) <= {"lang", "title", "dir", "continue", "limit"}
        assert params["dir"] in {"ascending", "descending"}
        # MW incompatibility: lang and title can be used separately and they can be sets
        if "lang" in params:
            assert isinstance(params["lang"], (str, set))
        if "title" in params:
            assert isinstance(params["title"], (str, set))

    # prop-specific methods
    # TODO: create an abstract class which specifies them

    def join_with_pageset(self, pageset):
        return pageset

    def get_select_prop(self, s, tail, params):
        ll = self.db.langlinks
        page = self.db.page

        tail = tail.outerjoin(ll, page.c.page_id == ll.c.ll_from)

        s = s.column(ll.c.ll_lang)
        s = s.column(ll.c.ll_title)

        # restrictions
        if "lang" in params:
            lang = params["lang"]
            if not isinstance(lang, set):
                lang = {lang}
            s = s.where(ll.c.ll_lang.in_(lang))
        if "title" in params:
            title = params["title"]
            if not isinstance(title, set):
                title = {title}
            s = s.where(ll.c.ll_title.in_(title))

        # order by
        if params["dir"] == "ascending":
            s = s.order_by(ll.c.ll_lang, ll.c.ll_title.asc())
        else:
            s = s.order_by(ll.c.ll_lang, ll.c.ll_title.desc())

        return s, tail

    @classmethod
    def db_to_api_subentry(klass, page, row):
        if row["ll_title"] is not None:
            langlinks = page.setdefault("langlinks", [])
            entry = {
                "lang": row["ll_lang"],
                "*": row["ll_title"],
            }
            langlinks.append(entry)
