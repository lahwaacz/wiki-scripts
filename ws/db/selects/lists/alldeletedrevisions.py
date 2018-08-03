#!/usr/bin/env python3

import sqlalchemy as sa

from ..props.deletedrevisions import DeletedRevisions
from .GeneratorBase import GeneratorBase

__all__ = ["AllDeletedRevisions"]

class AllDeletedRevisions(DeletedRevisions, GeneratorBase):

    API_PREFIX = "adr"
    DB_PREFIX = "ar_"

    @classmethod
    def sanitize_params(klass, params):
        # MW incompatibility: parameters related to content parsing are not supported (they are deprecated anyway)
        assert set(params) <= {"start", "end", "dir", "namespace", "user", "excludeuser", "prop", "limit", "continue",
                               "section", "generatetitles",
                               "from", "to", "prefix", "tag"}  # these four are in addition to list=allrevisions
        klass.sanitize_common_params(params)

    def get_select(self, params):
        """
        .. note::
            Parameters ...TODO... require joins with other tables,
            so that information will not be present during mirroring.
        """
        if {"section", "generatetitles", "limit", "continue", "prefix"} & set(params):
            raise NotImplementedError

        ar = self.db.archive
        nss = self.db.namespace_starname
        tail = ar.join(nss, ar.c.ar_namespace == nss.c.nss_id)
        s = sa.select([ar.c.ar_page_id, ar.c.ar_namespace, ar.c.ar_title, nss.c.nss_name, ar.c.ar_deleted])

        # props
        s, tail = self.add_props(s, tail, params["prop"])

        # joins
        if "tag" in params:
            tag = self.db.tag
            tgar = self.db.tagged_archived_revision
            tail = tail.join(tgar, ar.c.ar_rev_id == tgar.c.tgar_rev_id)
            s = s.where(tgar.c.tgar_tag_id == sa.select([tag.c.tag_id]).where(tag.c.tag_name == params["tag"]))

        # restrictions
        if params["dir"] == "older":
            newest = params.get("start")
            oldest = params.get("end")
        else:
            newest = params.get("end")
            oldest = params.get("start")
        if newest:
            s = s.where(ar.c.ar_timestamp <= newest)
        if oldest:
            s = s.where(ar.c.ar_timestamp >= oldest)
        if "from" in params:
            s = s.where(ar.c.ar_title >= params["from"])
        if "end" in params:
            s = s.where(ar.c.ar_title <= params["to"])
        if "namespace" in params:
            # FIXME: namespace can be a '|'-delimited list
            s = s.where(ar.c.ar_namespace == params["namespace"])
        if params.get("user"):
            s = s.where(ar.c.ar_user_text == params.get("user"))
        if params.get("excludeuser"):
            s = s.where(ar.c.ar_user_text != params.get("excludeuser"))

        # order by
        if params["dir"] == "older":
            s = s.order_by(ar.c.ar_timestamp.desc(), ar.c.ar_rev_id.desc())
        else:
            s = s.order_by(ar.c.ar_timestamp.asc(), ar.c.ar_rev_id.asc())

        return s.select_from(tail)
