#!/usr/bin/env python3

import sqlalchemy as sa

from .GrabberBase import GrabberBase


class GrabberNamespaces(GrabberBase):

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
                        "ns_protection":          ins_ns.excluded.ns_protection,
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
        # entries for the namespace_name table must be deduplicated
        nsn_id_to_name = {}

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
                "ns_protection": ns.get("namespaceprotection"),
            }
            yield self.sql["insert", "namespace"], ns_entry

            nsn_id_to_name[ns["id"]] = ns["*"]

            nss_entry = {
                "nss_id": ns["id"],
                "nss_name": ns["*"],
            }
            yield self.sql["insert", "namespace_starname"], nss_entry

            if "canonical" in ns:
                nsn_id_to_name[ns["id"]] = ns["canonical"]
                nsc_entry = {
                    "nsc_id": ns["id"],
                    "nsc_name": ns["canonical"],
                }
                yield self.sql["insert", "namespace_canonical"], nsc_entry

        for alias in self.api.site.namespacealiases.values():
            nsn_id_to_name[alias["id"]] = alias["*"]

        # insert deduplicated entries for the namespace_name table
        for nsn_id, nsn_name in nsn_id_to_name.items():
            nsn_entry = {
                "nsn_id": nsn_id,
                "nsn_name": nsn_name,
            }
            yield self.sql["insert", "namespace_name"], nsn_entry

    def gen_update(self, since):
        yield from self.gen_insert()
        # TODO: delete namespaces that ceased to exist
