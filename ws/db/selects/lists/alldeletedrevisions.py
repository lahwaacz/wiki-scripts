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
                               "section", "generatetitles", "slots",
                               "from", "to", "prefix", "tag"}  # these four are in addition to list=allrevisions
        klass.sanitize_common_params(params)

    def get_select(self, params):
        """
        .. note::
            Parameters ...TODO... require joins with other tables,
            so that information will not be present during mirroring.
        """
        if {"section", "generatetitles", "continue", "prefix"} & set(params):
            raise NotImplementedError
        if "limit" in params and params["limit"] != "max":
            raise NotImplementedError

        ar = self.db.archive
        nss = self.db.namespace_starname
        page = self.db.page
        # the page table has to be always joined with - the "pageid" field is not taken from ar_page_id,
        # but from the existing page which might have been created without undeleting previous revisions
        tail = ar.outerjoin(page, (ar.c.ar_namespace == page.c.page_namespace) &
                                  (ar.c.ar_title == page.c.page_title))
        tail = tail.join(nss, ar.c.ar_namespace == nss.c.nss_id)
        s = sa.select(page.c.page_id, ar.c.ar_namespace, ar.c.ar_title, nss.c.nss_name, ar.c.ar_deleted)

        # handle parameters common with prop=deletedrevisions
        s, tail = self.get_select_prop(s, tail, params)

        # extra restrictions
        if "namespace" in params:
            # FIXME: namespace can be a '|'-delimited list
            s = s.where(ar.c.ar_namespace == params["namespace"])

        return s.select_from(tail)
