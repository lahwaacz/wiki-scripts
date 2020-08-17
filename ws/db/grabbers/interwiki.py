#!/usr/bin/env python3

import sqlalchemy as sa

from .GrabberBase import GrabberBase

class GrabberInterwiki(GrabberBase):

    INSERT_PREDELETE_TABLES = ["interwiki"]

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_iw = sa.dialects.postgresql.insert(db.interwiki)

        self.sql = {
            ("insert", "interwiki"):
                db.interwiki.insert(),
            ("delete", "interwiki"):
                db.interwiki.delete().where(db.interwiki.c.iw_prefix == sa.bindparam("b_iw_prefix")),
            # iw_api is not visible in the logs so it is not updated
            ("update", "interwiki"):
                ins_iw.on_conflict_do_update(
                    index_elements=[db.interwiki.c.iw_prefix],
                    set_={
                        "iw_url":   ins_iw.excluded.iw_url,
                        "iw_local": ins_iw.excluded.iw_local,
                        "iw_trans": ins_iw.excluded.iw_trans,
                    }),
        }

    def gen_insert(self):
        for iw in self.api.site.interwikimap.values():
            db_entry = {
                "iw_prefix": iw["prefix"],
                "iw_url": iw["url"],
                "iw_api": iw.get("api"),
                "iw_local": "local" in iw,
                "iw_trans": "trans" in iw,
            }
            yield self.sql["insert", "interwiki"], db_entry

    def _transform_logevent_params(self, params):
        # see extensions/Interwiki/Interwiki_body.php line with "$log->addEntry" for the format of the data
        db_entry = {
            "iw_prefix": params.get("0"),
            "iw_url": params.get("1"),
            "iw_trans": bool(int(params["2"])) if "2" in params else None,
            "iw_local": bool(int(params["3"])) if "3" in params else None,
        }
        return db_entry

    def gen_update(self, since):
        # The interwiki can change also by direct manipulation with the database,
        # in which case there won't be any logevents. We don't care much about that...

        le_params = {
            "list": "logevents",
            "leprop": {"type", "details"},
            "ledir": "newer",
            "lestart": since,
        }
        for le in self.db.query(le_params):
            if le["type"] == "interwiki":
                db_entry = self._transform_logevent_params(le["params"])
                if le["action"] in {"iw_add", "iw_edit"}:
                    yield self.sql["update", "interwiki"], db_entry
                elif le["action"] == "iw_delete":
                    yield self.sql["delete", "interwiki"], {"b_iw_prefix": db_entry["iw_prefix"]}
