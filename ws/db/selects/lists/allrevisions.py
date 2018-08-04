#!/usr/bin/env python3

import sqlalchemy as sa

from ..props.revisions import Revisions
from .GeneratorBase import GeneratorBase

__all__ = ["AllRevisions"]

class AllRevisions(Revisions, GeneratorBase):

    API_PREFIX = "arv"
    DB_PREFIX = "rev_"

    @classmethod
    def sanitize_params(klass, params):
        # MW incompatibility: parameters related to content parsing are not supported (they are deprecated anyway)
        assert set(params) <= {"start", "end", "dir", "namespace", "user", "excludeuser", "prop", "limit", "continue",
                               "section", "generatetitles"}
        klass.sanitize_common_params(params)

    def get_select(self, params):
        """
        .. note::
            Parameters ...TODO... require joins with other tables,
            so that information will not be present during mirroring.
        """
        if {"section", "generatetitles", "continue"} & set(params):
            raise NotImplementedError
        if "limit" in params and params["limit"] != "max":
            raise NotImplementedError

        rev = self.db.revision
        nss = self.db.namespace_starname
        page = self.db.page
        tail = rev.join(page, rev.c.rev_page == page.c.page_id)
        tail = tail.join(nss, page.c.page_namespace == nss.c.nss_id)
        s = sa.select([page.c.page_id, page.c.page_namespace, page.c.page_title, nss.c.nss_name, rev.c.rev_deleted])

        # props
        s, tail = self.add_props(s, tail, params["prop"])

        # restrictions
        if params["dir"] == "older":
            newest = params.get("start")
            oldest = params.get("end")
        else:
            newest = params.get("end")
            oldest = params.get("start")
        if newest:
            s = s.where(rev.c.rev_timestamp <= newest)
        if oldest:
            s = s.where(rev.c.rev_timestamp >= oldest)
        if "namespace" in params:
            # FIXME: namespace can be a '|'-delimited list
            s = s.where(page.c.page_namespace == params["namespace"])
        if params.get("user"):
            s = s.where(rev.c.rev_user_text == params.get("user"))
        if params.get("excludeuser"):
            s = s.where(rev.c.rev_user_text != params.get("excludeuser"))

        # order by
        if params["dir"] == "older":
            s = s.order_by(rev.c.rev_timestamp.desc(), rev.c.rev_id.desc())
        else:
            s = s.order_by(rev.c.rev_timestamp.asc(), rev.c.rev_id.asc())

        return s.select_from(tail)
