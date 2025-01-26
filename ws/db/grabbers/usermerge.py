#!/usr/bin/env python3

import sqlalchemy as sa

from .GrabberBase import GrabberBase


class GrabberUserMerge(GrabberBase):

    def __init__(self, api, db):
        super().__init__(api, db)

        self.sql = {
            ("delete", "user"):
                db.user.delete()
                    .where(db.user.c.user_id == sa.bindparam("b_oldid")),
            ("update", "logging"):
                db.logging.update()
                    .where(db.logging.c.log_user == sa.bindparam("b_oldid")),
            ("update", "ipb"):
                db.ipblocks.update()
                    .where(db.ipblocks.c.ipb_by == sa.bindparam("b_oldid")),
            ("update", "archive"):
                db.archive.update()
                    .where(db.archive.c.ar_user == sa.bindparam("b_oldid")),
            ("update", "revision"):
                db.revision.update()
                    .where(db.revision.c.rev_user == sa.bindparam("b_oldid")),
        }

    def gen_insert(self):
        yield from self.gen_update(None)

    def gen_update(self, since):
        # mapping of merged users
        # (we rely on dict keeping the insertion order, this is a Python 3.7
        # feature: https://stackoverflow.com/a/39980744 )
        merged_users = {}
        # users deleted after merge
        deleted_users = set()

        # collect merged users
        # (note that usermerge events are not recorded in the recentchanges
        # table, see https://phabricator.wikimedia.org/T253726 )
        le_params = {
            "list": "logevents",
            "letype": "usermerge",
            "leprop": {"type", "details"},
            "ledir": "newer",
        }
        if since is not None:
            le_params["lestart"] = since
        for logevent in self.db.query(le_params):
            if logevent["action"] == "mergeuser":
                oldid = logevent["params"]["oldId"]
                newid = logevent["params"]["newId"]
                newname = logevent["params"]["newName"]
                merged_users[oldid] = (newid, newname)
            elif logevent["action"] == "deleteuser":
                deleted_users.add(logevent["params"]["oldId"])

        # merge users
        for oldid, new in merged_users.items():
            newid, newname = new
            yield self.sql["update", "logging"], {"b_oldid": oldid, "log_user": newid, "log_user_text": newname}
            yield self.sql["update", "ipb"], {"b_oldid": oldid, "ipb_by": newid, "ipb_by_text": newname}
            yield self.sql["update", "archive"], {"b_oldid": oldid, "ar_user": newid, "ar_user_text": newname}
            yield self.sql["update", "revision"], {"b_oldid": oldid, "rev_user": newid, "rev_user_text": newname}

        # delete users
        for oldid in deleted_users:
            yield self.sql["delete", "user"], {"b_oldid": oldid}
