#!/usr/bin/env python3

from . import Grabber

class GrabberNamespaces(Grabber):

    TARGET_TABLES = ["namespace", "namespace_name", "namespace_starname", "namespace_canonical"]

    def __init__(self, api, db):
        super().__init__(api, db)

        self.sql = {
            ("insert", "namespace"):
                db.namespace.insert(mysql_on_duplicate_key_update=[
                    db.namespace.c.ns_case,
                    db.namespace.c.ns_content,
                    db.namespace.c.ns_subpages,
                    db.namespace.c.ns_nonincludable,
                    db.namespace.c.ns_defaultcontentmodel,
                ]),
            ("insert", "namespace_name"):
                db.namespace_name.insert(mysql_on_duplicate_key_update=[
                    db.namespace_name.c.nsn_id,
                ]),
            ("insert", "namespace_starname"):
                db.namespace_starname.insert(mysql_on_duplicate_key_update=[
                    db.namespace_starname.c.nss_name,
                ]),
            ("insert", "namespace_canonical"):
                db.namespace_canonical.insert(mysql_on_duplicate_key_update=[
                    db.namespace_canonical.c.nsc_name,
                ]),
        }

    def gen_insert(self):
        for ns in self.api.site.namespaces.values():
            # don't store special namespaces in the database
            if ns["id"] < 0:
                continue

            ns_entry = {
                "ns_id": ns["id"],
                "ns_case": ns["case"],
                "ns_content": "content" in ns,
                "ns_subpages": "subpages" in ns,
                "ns_nonincludable": "nonincludable" in ns,
                # TODO: is this even available from the API?
                "ns_defaultcontentmodel": None,
            }
            yield self.sql["insert", "namespace"], ns_entry

            nsn_entry = {
                "nsn_id": ns["id"],
                "nsn_name": ns["*"],
            }
            yield self.sql["insert", "namespace_name"], nsn_entry
            nss_entry = {
                "nss_id": ns["id"],
                "nss_name": ns["*"],
            }
            yield self.sql["insert", "namespace_starname"], nss_entry

            if "canonical" in ns:
                nsn_entry = {
                    "nsn_id": ns["id"],
                    "nsn_name": ns["canonical"],
                }
                yield self.sql["insert", "namespace_name"], nsn_entry
                nsc_entry = {
                    "nsc_id": ns["id"],
                    "nsc_name": ns["canonical"],
                }
                yield self.sql["insert", "namespace_canonical"], nsc_entry

        for alias in self.api.site.namespacealiases.values():
            nsn_entry = {
                "nsn_id": alias["id"],
                "nsn_name": alias["*"],
            }
            yield self.sql["insert", "namespace_name"], nsn_entry

    def gen_update(self, since):
        yield from self.gen_insert()
        # TODO: delete namespaces that ceased to exist

def select(db):
    ns_sel = db.namespace.select()
    nss_sel = db.namespace_starname.select()
    nsc_sel = db.namespace_canonical.select()

    conn = db.engine.connect()
    result = conn.execute(ns_sel)

    namespaces = {}

    for row in result:
        ns = {
            "id": row.ns_id,
            "case": row.ns_case,
        }
        if row.ns_content:
            ns["content"] = ""
        if row.ns_subpages:
            ns["subpages"] = ""
        if row.ns_nonincludable:
            ns["nonincludable"] = ""
        namespaces[row.ns_id] = ns

    result = conn.execute(nss_sel)
    for row in result:
        namespaces[row.nss_id]["*"] = row.nss_name

    result = conn.execute(nsc_sel)
    for row in result:
        namespaces[row.nsc_id]["canonical"] = row.nsc_name

    return namespaces
