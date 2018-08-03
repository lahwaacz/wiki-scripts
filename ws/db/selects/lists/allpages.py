#!/usr/bin/env python3

import datetime

import sqlalchemy as sa

import ws.db.mw_constants as mwconst

from .GeneratorBase import GeneratorBase

__all__ = ["AllPages"]

class AllPages(GeneratorBase):

    API_PREFIX = "ap"
    DB_PREFIX = "page_"

    @classmethod
    def set_defaults(klass, params):
        params.setdefault("dir", "ascending")
        params.setdefault("namespace", 0)
        params.setdefault("filterredir", "all")
        params.setdefault("prexpiry", "all")
        params.setdefault("prfiltercascade", "all")
#        params.setdefault("filterlanglinks", "all")

    @classmethod
    def sanitize_params(klass, params):
        assert set(params) <= {"from", "to", "dir", "prefix", "namespace", "filterredir", "minsize", "maxsize", "prtype", "prlevel", "prexpiry", "prfiltercascade", "filterlanglinks", "limit", "continue"}

        # TODO: convert the 'from', 'to' and 'prefix' fields to the database canonical format

        # sanitize limits
        assert params["dir"] in {"ascending", "descending"}
        if params["dir"] == "ascending":
            start = params.get("from")
            end = params.get("to")
        else:
            start = params.get("to")
            end = params.get("from")

        assert params["filterredir"] in {"all", "redirects", "nonredirects"}
        if "minsize" in params:
            assert isinstance(params["minsize"], int)
        if "maxsize" in params:
            assert isinstance(params["maxsize"], int)
        if "prtype" in params:
            assert params["prtype"] <= {"edit", "move", "upload"}
        if "prlevel" in params:
            assert "prtype" in params, "prlevel may not be used without prtype"
            # MW incompatibility: MediaWiki accepts even "" and "*", but discards them
            # TODO: check against levels in siprop=restrictions
            assert params["prlevel"] <= {"autoconfirmed", "sysop"}
        assert params["prexpiry"] in {"all", "definite", "indefinite"}
        assert params["prfiltercascade"] in {"all", "cascading", "noncascading"}
#        assert params["filterlanglinks"] in {"all", "withlanglinks", "withoutlanglinks"}

    def get_select(self, params):
        """
        .. note::
            Parameters ...TODO... require joins with other tables,
            so that information will not be present during mirroring.
        """
        if {"filterlanglinks", "limit", "continue"} & set(params):
            raise NotImplementedError

        page = self.db.page
        s = sa.select([page.c.page_id, page.c.page_namespace, page.c.page_title])

        # join to get the namespace prefix
        nss = self.db.namespace_starname
        tail = page.outerjoin(nss, page.c.page_namespace == nss.c.nss_id)
        s.append_column(nss.c.nss_name)

        # page protection filtering
        if "prtype" in params or params["prexpiry"] != "all":
            pr = self.db.page_restrictions
            tail = tail.outerjoin(pr, page.c.page_id == pr.c.pr_page)
            # skip expired protections
            s = s.where(sa.or_(pr.c.pr_expiry > datetime.datetime.utcnow(), pr.c.pr_expiry == None))
            if "prtype" in params:
                s = s.where(pr.c.pr_type.in_(params["prtype"]))
                if "prlevel" in params:
                    s = s.where(pr.c.pr_level.in_(params["prlevel"]))
                if params["prfiltercascade"] == "cascading":
                    s = s.where(pr.c.pr_cascade == 1)
                elif params["prfiltercascade"] == "noncascading":
                    s = s.where(pr.c.pr_cascade == 0)
            if params["prexpiry"] == "indefinite":
                s = s.where(sa.or_(pr.c.pr_expiry == "infinity", pr.c.pr_expiry == None))
            elif params['prexpiry'] == "definite":
                s = s.where(pr.c.pr_expiry != "infinity")
            # TODO: check that adding DISTINCT like in MediaWiki is useless for our database

        s = s.select_from(tail)

        # restrictions
        if params["dir"] == "ascending":
            start = params.get("from")
            end = params.get("to")
        else:
            start = params.get("to")
            end = params.get("from")
        if start:
            s = s.where(page.c.page_title >= start)
        if end:
            s = s.where(page.c.page_title <= end)
        s = s.where(page.c.page_namespace == params["namespace"])

        # order by
        if params["dir"] == "ascending":
            s = s.order_by(page.c.page_title.asc())
        else:
            s = s.order_by(page.c.page_title.desc())

        return s

    @classmethod
    def db_to_api(klass, row):
        flags = {
            "page_id": "pageid",
            "page_namespace": "ns",
        }
        bool_flags = {
        }
        # subset of flags for which 0 should be used instead of None
        zeroable_flags = {}

        api_entry = {}
        for key, value in row.items():
            if key in flags:
                api_key = flags[key]
                # normal keys are not added if the value is None
                if value is not None:
                    api_entry[api_key] = value
                # some keys produce 0 instead of None
                elif key in zeroable_flags:
                    api_entry[api_key] = 0
            elif key in bool_flags:
                if value:
                    api_key = bool_flags[key]
                    api_entry[api_key] = ""

        # add special values
        if "nss_name" in row:
            if row["nss_name"]:
                api_entry["title"] = "{}:{}".format(row["nss_name"], row["page_title"])
            else:
                api_entry["title"] = row["page_title"]

        return api_entry
