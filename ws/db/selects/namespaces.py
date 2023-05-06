#!/usr/bin/env python3

def get_namespaces(db):
    ns_sel = db.namespace.select()
    nss_sel = db.namespace_starname.select()
    nsc_sel = db.namespace_canonical.select()

    namespaces = {}

    with db.engine.connect() as conn:
        for row in conn.execute(ns_sel):
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
            if row.ns_protection:
                ns["namespaceprotection"] = row.ns_protection
            namespaces[row.ns_id] = ns

        result = conn.execute(nss_sel)
        for row in result:
            namespaces[row.nss_id]["*"] = row.nss_name

        result = conn.execute(nsc_sel)
        for row in result:
            namespaces[row.nsc_id]["canonical"] = row.nsc_name

    return namespaces

def get_namespacenames(db):
    namespacenames = {}

    with db.engine.connect() as conn:
        for row in conn.execute(db.namespace_name.select()):
            namespacenames[row.nsn_name] = row.nsn_id

    return namespacenames
