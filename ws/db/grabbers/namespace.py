#!/usr/bin/env python3

import sqlalchemy as sa

from . import Grabber

class GrabberNamespaces(Grabber):

    def __init__(self, api, db):
        super().__init__(api, db)

        ins_ns = sa.dialects.postgresql.insert(db.namespace)
        ins_nsn = sa.dialects.postgresql.insert(db.namespace_name)
        ins_nss = sa.dialects.postgresql.insert(db.namespace_starname)
        ins_nsc = sa.dialects.postgresql.insert(db.namespace_canonical)

        self.sql = {
            ("insert", "namespace"):
                ins_ns.on_conflict_do_update(
                    constraint=db.namespace.primary_key,
                    set_={
                        "ns_case":                ins_ns.excluded.ns_case,
                        "ns_content":             ins_ns.excluded.ns_content,
                        "ns_subpages":            ins_ns.excluded.ns_subpages,
                        "ns_nonincludable":       ins_ns.excluded.ns_nonincludable,
                        "ns_defaultcontentmodel": ins_ns.excluded.ns_defaultcontentmodel,
                    }),
            ("insert", "namespace_name"):
                ins_nsn.on_conflict_do_update(
                    index_elements=[db.namespace_name.c.nsn_name],
                    set_={
                        "nsn_id": ins_nsn.excluded.nsn_id,
                    }),
            ("insert", "namespace_starname"):
                ins_nss.on_conflict_do_update(
                    index_elements=[db.namespace_starname.c.nss_id],
                    set_={
                        "nss_name": ins_nss.excluded.nss_name,
                    }),
            ("insert", "namespace_canonical"):
                ins_nsc.on_conflict_do_update(
                    index_elements=[db.namespace_canonical.c.nsc_id],
                    set_={
                        "nsc_name": ins_nsc.excluded.nsc_name,
                    }),
        }

    def gen_insert(self):
        for ns in self.api.site.namespaces.values():
            # don't store special namespaces in the database
#            if ns["id"] < 0:
#                continue

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
